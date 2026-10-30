"""List lifecycle, projection and query-local indexing regressions."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from . import test_list_summary as fixtures
from . import test_list_legacy as legacy_fixtures
from .test_run_guard import binding
from .test_cadra import contract

reader = fixtures.reader


class CountingList(list):
    def __init__(self, items):
        super().__init__(items)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()


class ListOptimizationTests(unittest.TestCase):
    def fixture(self, protocol='0.11'):
        cls, method = ((fixtures.ListSummaryTests, 'test_source_order_is_not_filename_order') if protocol == '0.11'
                       else (legacy_fixtures.LegacyListTests, 'test_native_legacy_query_keeps_source_protocol_and_serial_model'))
        case = cls(method)
        case.setUp()
        self.addCleanup(case.doCleanups)
        return case

    def test_unfinished_predecessor_cannot_be_followed_by_a_terminal_run(self):
        for protocol in reader.READ_PROTOCOLS:
            for status in ('running', 'interrupted', 'stopped'):
                with self.subTest(protocol=protocol, status=status):
                    c = self.fixture(protocol)
                    task = c.task()
                    first = c.make_run(task, state='completed' if status != 'stopped' else 'queued', status=status)
                    c.make_run(task, rid='run-20261025-02', previous=first['run_id'], state='failed', status='completed')
                    before = {p: p.read_bytes() for p in c.root.rglob('*.md')}
                    result = c.summary(slugs=['camera'])
                    c.assert_unknown(result, 'Run lifecycle contradiction')
                    self.assertIn(first['run_id'], json.dumps(result['issues']))
                    self.assertEqual(before, {p: p.read_bytes() for p in c.root.rglob('*.md')})
                    old = c.summary(run_id='run-20261025-02')
                    self.assertEqual(old['counts'], {'failed': 1})
                    self.assertEqual(old['current_counts'], {'unknown': 1})
                    self.assertTrue(old['issues'])

    def test_completed_predecessor_and_closed_stopped_predecessor_remain_legal(self):
        for protocol in reader.READ_PROTOCOLS:
            for status in ('completed', 'stopped'):
                c = self.fixture(protocol)
                task = c.task()
                first = c.make_run(task, state='completed', status=status)
                c.make_run(task, rid='run-20261025-02', previous=first['run_id'], state='failed', status='completed')
                self.assertEqual(c.summary()['counts'], {'failed': 1})
                self.assertEqual(c.summary()['issues'], [])

    def test_invalid_filtered_task_still_reports_lifecycle_gap(self):
        c = self.fixture()
        task = c.task()
        first = c.make_run(task, state='completed', status='running')
        c.make_run(task, rid='run-20261025-02', previous=first['run_id'], state='completed', status='completed')
        result = c.summary(states=['completed'])
        self.assertEqual(result['total'], 0)
        self.assertIn('Run lifecycle contradiction', json.dumps(result['issues']))

    def test_role_identity_is_stored_once_per_run_without_losing_agent_ids(self):
        for protocol in reader.READ_PROTOCOLS:
            c = self.fixture(protocol)
            data = c.make_run(state='completed', status='completed')
            base = data['tasks'][0]
            base['agents'] = [binding()]
            second_task = c.task('second')
            second = deepcopy(base)
            second.update(slug='second', definition={**second_task, 'requirement': 'preserve camera dependency'})
            second['agents'] = [binding(agent_id='second-worker')]
            data['tasks'].append(second)
            data['preflight'].append({**data['preflight'][1], 'slug': 'second'})
            if protocol == '0.11':
                data = fixtures.finalized_fixture(data, 'second')
            c.write(c.runs / (data['run_id'] + '.md'), data)
            result = c.summary(roles=True, history=True)
            identities = result['role_details'][data['run_id']]
            self.assertEqual(set(identities['agents']), {'camera', 'second'})
            self.assertEqual(identities['agents']['camera'][0]['agent_id'], 'agent-worker')
            self.assertEqual(identities['agents']['second'][0]['agent_id'], 'second-worker')
            raw = json.dumps(result)
            self.assertEqual(raw.count('"instance_id"'), 1)
            self.assertNotIn('executor', result['runs'][0])
            self.assertEqual(result['runs'][0]['roles_ref'], data['run_id'])

    def test_compact_result_retains_decisions_sources_and_marks_omitted_payload(self):
        c = self.fixture()
        data = c.make_run(state='failed', status='completed')
        delivery = contract('code', 'review', 'stage_completed')
        delivery['task'] = 'camera'
        result = dict(state='failed', reason='mandatory failure', candidate=dict(snapshot='fixed', inputs={'A.swift':'a'*64}),
                      findings={'blocking': 1}, acceptance={'status': 'blocked'}, next='human decision',
                      human_intervention='decide scope', source='original-source.md', at=data['created_at'],
                      last_delivery=dict(contract=delivery, handoff='code-01.md', index_sync=True), raw_log='large log' * 1000)
        data['tasks'][0]['result'] = result
        data['tasks'][0]['checkpoint']['last_delivery'] = result['last_delivery']
        c.write(c.runs / (data['run_id'] + '.md'), data)
        compact = c.summary(run_id=data['run_id'])['runs'][0]['queue'][0]['result']
        for key in ('state','reason','findings','acceptance','next','human_intervention','source','at'):
            self.assertEqual(compact[key], result[key])
        self.assertEqual(compact['last_delivery']['stage_result'], delivery['stage_result'])
        self.assertEqual(compact['last_delivery']['handoff'], 'code-01.md')
        self.assertIn('contract', compact['last_delivery']['omitted_fields'])
        self.assertIn('raw_log', compact['omitted_fields'])
        self.assertEqual(compact['candidate']['inputs_count'], 1)
        self.assertNotIn('inputs', compact['candidate'])
        full = c.summary(run_id=data['run_id'], full_results=True)
        self.assertEqual(full['runs'][0]['queue'][0]['result'], result)
        single = c.summary(slugs=['camera'], full_results=True)
        self.assertEqual(single['groups'][0]['tasks'][0]['details']['result'], result)
        self.assertLess(len(json.dumps(compact)), len(json.dumps(result)) // 4)

    def test_explicit_historical_detail_does_not_include_later_roles_or_checkpoint(self):
        c = self.fixture()
        task = c.task()
        first = c.make_run(task, state='completed', status='completed')
        c.make_run(task, rid='run-20261025-02', previous=first['run_id'], state='failed', status='completed')
        result = c.summary(run_id=first['run_id'], slugs=['camera'])
        self.assertEqual(set(result['role_details']), {first['run_id']})
        self.assertEqual(result['runs'][0]['queue'][0]['details']['roles_ref'], first['run_id'])

    def test_preflight_scans_are_constant_and_missing_task_evidence_still_fails(self):
        for protocol in reader.READ_PROTOCOLS:
            c = self.fixture(protocol)
            data = c.make_run()
            data['preflight'] = CountingList(data['preflight'])
            for n in range(80):
                item = deepcopy(data['tasks'][0])
                item['slug'] = item['definition']['slug'] = f'task-{n}'
                data['tasks'].append(item)
                data['preflight'].append({**data['preflight'][1], 'slug': item['slug']})
            rules = reader.record_reader(protocol)
            rules.validate(data)
            self.assertLessEqual(data['preflight'].iterations, 4)
            data['preflight'] = [p for p in data['preflight'] if p.get('slug') != 'task-79']
            with self.assertRaisesRegex(ValueError, 'task preflight required'):
                rules.validate(data)

    def test_query_reuses_validated_scheduler_view_and_writer_default_stays_strict(self):
        c = self.fixture()
        data = c.make_run()
        with patch.object(reader.guard.scheduler, 'replay', wraps=reader.guard.scheduler.replay) as replay:
            c.summary()
            self.assertEqual(replay.call_count, 1)
        self.assertIsNone(reader.guard.validate(data))
        data['tasks'][0]['checkpoint']['pending_call'] = 99
        with self.assertRaisesRegex(ValueError, 'checkpoint mismatch'):
            reader.guard.validate(data)

    def test_stopped_run_with_open_group_remains_unfinished_without_replaying_twice(self):
        c = self.fixture()
        data = c.make_run(state='failed', status='stopped')
        data['scheduler'] = fixtures.example()['scheduler']
        c.write(c.runs / (data['run_id'] + '.md'), data)
        with patch.object(reader.guard.scheduler, 'replay', wraps=reader.guard.scheduler.replay) as replay:
            result = c.summary()
            self.assertEqual(replay.call_count, 1)
            self.assertEqual(result['runs'][0]['status'], 'stopped')
        c.make_run(c.task(), rid='run-20261025-02', previous=data['run_id'], state='completed', status='completed')
        c.assert_unknown(c.summary(), 'Run lifecycle contradiction')


if __name__ == '__main__':
    unittest.main()

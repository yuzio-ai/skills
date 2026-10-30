"""Native 0.10 list queries, without mutation or a legacy execution path."""
from copy import deepcopy
import json
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from . import test_list_summary as summary_fixtures
from .test_run_guard import example, pending, binding, guard

SCRIPT = summary_fixtures.SCRIPT
reader = summary_fixtures.reader


class LegacyListTests(unittest.TestCase):
    setUp = summary_fixtures.ListSummaryTests.setUp
    write = summary_fixtures.ListSummaryTests.write
    summary = summary_fixtures.ListSummaryTests.summary
    rows = summary_fixtures.ListSummaryTests.rows
    assert_unknown = summary_fixtures.ListSummaryTests.assert_unknown

    def task(self, slug='camera', **updates):
        data = summary_fixtures.ListSummaryTests.task(self, slug, protocol='0.10', **updates)
        del data['ready_scope']
        self.write(self.tasks / (slug + '.md'), data, '# Task\n\n## Requirement\n\npreserve camera dependency\n')
        return data

    def make_run(self, task=None, rid='run-20261025-01', state='queued', previous=None, status='running'):
        task = task or self.task()
        data = example()
        data.pop('scheduler')
        data.update(protocol='0.10', run_id=rid, status=status, skill_version='0.10.0')
        item = data['tasks'][0]
        item.update(slug=task['slug'], revision=task['revision'], previous_run=previous,
                    definition={**deepcopy(task), 'requirement': 'preserve camera dependency'}, state=state,
                    result={'state': state, 'reason': 'original outcome'} if state in reader.END else None)
        data['preflight'][1]['slug'] = task['slug']
        reader.legacy.validate(data)
        self.write(self.runs / (rid + '.md'), data)
        return data

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def test_native_legacy_query_keeps_source_protocol_and_serial_model(self):
        self.make_run()
        result = self.summary()
        self.assertEqual(result['counts'], {'queued': 1})
        self.assertEqual(result['protocol'], '0.10')
        self.assertEqual(result['execution_protocol'], '0.11')
        self.assertEqual(result['protocols'], {'0.10': 2})
        self.assertTrue(result['legacy_read_only'])
        queue = result['queues'][0]
        self.assertEqual(queue['protocol'], '0.10')
        self.assertTrue(queue['legacy_read_only'])
        self.assertNotIn('scheduling', queue)
        self.assertEqual(queue['queue'][0]['protocol'], '0.10')
        self.assertEqual(result['issues'], [])

    def test_no_migration_locks_cache_or_bytecode_for_query_options(self):
        data = self.make_run(state='completed', status='completed')
        original = self.snapshot()
        for options in ({}, {'history': True}, {'slugs': ['camera']}, {'roles': True},
                        {'states': ['completed']}, {'run_id': data['run_id']}):
            with self.subTest(options=options), patch.object(reader.guard, 'writer_lock', side_effect=AssertionError('no locks')):
                result = self.summary(**options)
                self.assertEqual(result['counts'], {'completed': 1})
                self.assertEqual(self.snapshot(), original)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'tasks', 'runs'})

    def test_completed_skipped_and_changed_revision_keep_original_meaning(self):
        task = self.task()
        self.make_run(task, state='completed', status='completed')
        self.assertEqual(self.summary()['counts'], {'completed': 1})
        self.make_run(task, rid='run-20261025-02', previous='run-20261025-01', state='skipped', status='stopped')
        self.assertEqual(self.summary()['counts'], {'ready': 1})
        self.task(revision=2, preparation='draft')
        self.assertEqual(self.summary()['counts'], {'draft': 1})
        old = self.summary(run_id='run-20261025-01')
        self.assertEqual(old['counts'], {'completed': 1})
        self.assertEqual(old['current_counts'], {'draft': 1})

    def test_legacy_source_chain_and_snapshot_anomalies_are_not_hidden(self):
        data = self.make_run()
        data['tasks'][0]['previous_run'] = 'run-20261024-01'
        self.write(self.runs / (data['run_id'] + '.md'), data)
        self.assert_unknown(self.summary(), 'missing source Run')
        data['tasks'][0]['previous_run'] = None
        data['tasks'][0]['definition']['source_document'] = 'conflicting original'
        self.write(self.runs / (data['run_id'] + '.md'), data)
        self.assert_unknown(self.summary(), 'definition/revision differs')
        data['tasks'][0]['definition']['source_document'] = (self.tasks / 'camera.md').read_text()
        self.write(self.runs / (data['run_id'] + '.md'), data)
        self.assertEqual(self.summary()['counts'], {'queued': 1})

    def test_legacy_prepared_dispatched_and_action_only_gaps(self):
        data = self.make_run()
        item = data['tasks'][0]
        item['agents'] = [binding()]
        pending(data)
        path = self.runs / (data['run_id'] + '.md')
        self.write(path, data)
        self.assertEqual(self.summary()['queues'][0]['current'][0]['action'], '待派发实现')
        call = item['calls'][0]
        call.update(dispatch='dispatched', dispatch_evidence={'agent_id': 'agent-worker', 'source': 'original', 'at': data['created_at']})
        self.write(path, data)
        self.assertIn('交付待核对', self.summary()['queues'][0]['current'][0]['action'])
        item.pop('checkpoint')
        self.write(path, data)
        result = self.summary(slugs=['camera'])
        self.assertEqual(result['counts'], {'running': 1})
        self.assertIn('checkpoint mismatch', result['queues'][0]['current'][0]['action'])
        self.assertEqual(result['queues'][0]['activity'], 'unknown')
        with self.assertRaisesRegex(ValueError, 'checkpoint mismatch'):
            reader.legacy.validate(data)

    def test_legacy_budgets_results_and_snapshot_protocol_remain_checked(self):
        original = self.make_run()
        for field, error in (('budget', 'budget mismatch'), ('result', 'result/state mismatch'),
                             ('definition', 'definition protocol/identity mismatch')):
            data = deepcopy(original)
            item = data['tasks'][0]
            if field == 'budget':
                item['budget']['calls'] = 1
            elif field == 'result':
                item['state'] = 'completed'
            else:
                item['definition']['protocol'] = '0.11'
            self.write(self.runs / (data['run_id'] + '.md'), data)
            with self.subTest(field=field):
                self.assert_unknown(self.summary(), error)

    def test_legacy_rejects_waiting_and_two_running_tasks(self):
        data = self.make_run()
        path = self.runs / (data['run_id'] + '.md')
        data['tasks'][0]['state'] = 'waiting'
        self.write(path, data)
        self.assert_unknown(self.summary(), 'invalid task state')
        data['tasks'][0]['state'] = 'running'
        other = self.task('second')
        second = deepcopy(data['tasks'][0])
        second.update(slug='second', definition={**other, 'requirement': 'preserve camera dependency'})
        data['tasks'].append(second)
        self.write(path, data)
        self.assert_unknown(self.summary(), 'multiple running tasks')

    def test_independent_versions_can_be_listed_without_stitching_chains(self):
        self.make_run(state='completed', status='completed')
        new_task = summary_fixtures.ListSummaryTests.task(self, 'current')
        summary_fixtures.ListSummaryTests.make_run(self, new_task, rid='run-20261025-02')
        result = self.summary(history=True)
        self.assertEqual(result['counts'], {'completed': 1, 'queued': 1})
        self.assertIsNone(result['protocol'])
        self.assertEqual(result['protocols'], {'0.10': 2, '0.11': 2})
        self.assertEqual(result['issues'], [])
        self.assertNotIn('scheduling', result['runs'][0])
        self.assertIn('scheduling', result['queues'][0])

    def test_cross_protocol_chain_is_unknown_without_rewriting_either_version(self):
        self.make_run(state='completed', status='completed')
        new_task = summary_fixtures.ListSummaryTests.task(self, 'camera')
        summary_fixtures.ListSummaryTests.make_run(self, new_task, rid='run-20261025-02', previous='run-20261025-01')
        before = self.snapshot()
        self.assert_unknown(self.summary(), 'cross-protocol source chain')
        self.assertEqual(self.snapshot(), before)

    def test_legacy_completion_cannot_supply_current_protocol_dependency_evidence(self):
        self.make_run(state='completed', status='completed')
        current = summary_fixtures.ListSummaryTests.task(self, 'current', dependencies=['camera'])
        summary_fixtures.ListSummaryTests.make_run(self, current, rid='run-20261025-02')
        result = self.summary(slugs=['current'])
        row = self.rows(result)[0]
        self.assertEqual(row['details']['dependencies'], {'camera': 'unknown'})
        self.assertEqual(row['details']['dependency_protocols'], {'camera': '0.10'})
        self.assertIn('cross-protocol dependency', json.dumps(result['issues']))
        self.write(self.tasks / 'camera.md', [])
        self.assertEqual(self.rows(self.summary(slugs=['current']))[0]['details']['dependencies'], {'camera': 'unknown'})

    def test_unversioned_and_other_protocols_still_fail_closed(self):
        for protocol in (None, '0.9', '0.8', '0.99', '1.0'):
            self.task()
            path = self.tasks / 'camera.md'
            data = json.loads(guard.split_document(path.read_bytes())[0])
            if protocol is None:
                del data['protocol']
            else:
                data['protocol'] = protocol
            self.write(path, data)
            with self.subTest(protocol=protocol):
                self.assert_unknown(self.summary(), 'unsupported Cadra protocol')

    def test_execution_guard_and_all_publication_modes_reject_legacy(self):
        data = self.make_run()
        path = self.runs / (data['run_id'] + '.md')
        raw = path.read_bytes()
        before = self.snapshot()
        for operation in ('header', 'current', 'validate'):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'unsupported Cadra protocol'):
                getattr(guard, operation)(data if operation == 'validate' else raw)
        with self.assertRaisesRegex(ValueError, 'unsupported Cadra protocol'):
            guard.normalize_flow('code', '0.10')
        for mode in ('create', 'update', 'append', 'takeover', 'report'):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'unsupported Cadra protocol'):
                guard.publish(path, raw, guard.digest(raw), 'first', 1, mode)
            self.assertEqual(self.snapshot(), before)
        self.assertFalse(hasattr(reader.legacy, 'publish'))
        self.assertFalse(hasattr(reader.legacy, 'writer_lock'))
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT.with_name('run_guard.py')), 'inspect', '--run', str(path)],
                              capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_legacy_cli_runs_from_an_independent_package_copy(self):
        self.make_run()
        installed = self.project / 'installed/cadra'
        shutil.copytree(SCRIPT.parents[1], installed)
        before = self.snapshot()
        proc = subprocess.run([sys.executable, '-B', str(installed / 'scripts/list_summary.py'), '--project', str(self.project)],
                              cwd=self.project, capture_output=True, text=True, check=True)
        result = json.loads(proc.stdout)
        self.assertEqual(result['counts'], {'queued': 1})
        self.assertTrue(result['legacy_read_only'])
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(list(installed.rglob('__pycache__')))

    def test_current_protocol_proposal_cannot_convert_an_old_run_or_admit_new_execution(self):
        data = self.make_run(state='completed', status='completed')
        path = self.runs / (data['run_id'] + '.md')
        raw = path.read_bytes()
        proposal = example()
        with self.assertRaisesRegex(ValueError, 'unsupported Cadra protocol'):
            guard.publish(path, summary_fixtures.raw_document(proposal), guard.digest(raw), 'first', 1, 'update')
        self.assertEqual(path.read_bytes(), raw)
        proposal['run_id'] = 'run-20261025-02'
        new_path = self.runs / (proposal['run_id'] + '.md')
        with self.assertRaisesRegex(ValueError, 'unsupported Cadra protocol'):
            guard.publish(new_path, summary_fixtures.raw_document(proposal), None, 'first', 1, 'create')
        self.assertFalse(new_path.exists())
        self.assertEqual(path.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()

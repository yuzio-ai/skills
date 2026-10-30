"""Exercise the shipped list reader against temporary Task/Run containers."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from .test_run_guard import example, binding, pending, raw_document, guard
from .test_cadra import contract

SCRIPT = Path(__file__).resolve().parents[2] / 'cadra/scripts/list_summary.py'
spec = importlib.util.spec_from_file_location('cadra_list_summary', SCRIPT)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def finalized_fixture(data, slug):
    """Record a synthetic singleton close for reader fixtures, using the shipped reducer."""
    schedule = guard.scheduler
    task = next(t for t in data['tasks'] if t['slug'] == slug)
    when = data['created_at']
    candidate = dict(snapshot='synthetic-reader-candidate', sha256='a' * 64, inputs={})
    data = schedule.append_event(data, 'group', when, members=[slug],
                                 before={slug: {}}, before_refs={slug: 'synthetic-reader-before'})
    data = schedule.append_event(data, 'wait', when, slug=slug, call_id=None, resource='finalization',
                                 scope=task['definition']['ready_scope']['scope'], candidate=candidate,
                                 stop=dict(agent_id=None, host_id=None, tools_stopped=True,
                                           observed_at=when, source='synthetic no-call reader fixture'))
    data = schedule.append_event(data, 'close', when, candidate=candidate)
    next(t for t in data['tasks'] if t['slug'] == slug)['state'] = 'completed'
    return data


class ListSummaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        self.root = self.project / '.yuzio/cadra'
        self.tasks = self.root / 'tasks'
        self.runs = self.root / 'runs'
        self.tasks.mkdir(parents=True)
        self.runs.mkdir()

    def task(self, slug='camera', **updates):
        d = dict(protocol=guard.PROTOCOL, slug=slug, title='Task ' + slug, revision=1,
                 preparation='ready', priority='medium', dependencies=[], flow='code',
                 cohestra_task=f'.yuzio/cohestra/handoffs/{slug}/',
                 ready_scope={'revision': 1, 'scope': {'mode': 'exclusive', 'files': [], 'dirs': []}, 'inputs': {}},
                 created_at='2026-10-29T08:00:00+08:00')
        d.update(updates)
        d['ready_scope']['revision'] = d['revision']
        self.write(self.tasks / (slug + '.md'), d, '# Task\n\n## Requirement\n\npreserve camera dependency\n')
        return d

    def write(self, path, data, body=''):
        path.write_bytes(raw_document(data) + body.encode())

    def make_run(self, task=None, rid='run-20261025-01', state='queued', previous=None, status='running'):
        task = task or self.task()
        d = example()
        d.update(run_id=rid, status=status, scheduler=guard.scheduler.initial())
        t = d['tasks'][0]
        t.update(slug=task['slug'], revision=task['revision'], previous_run=previous,
                 definition={**deepcopy(task), 'requirement': 'preserve camera dependency'}, state=state,
                 result={'state': state, 'reason': 'fixture outcome'} if state in reader.END else None)
        d['preflight'][1]['slug'] = task['slug']
        if state == 'completed':
            d = finalized_fixture(d, task['slug'])
        guard.validate(d)
        self.write(self.runs / (rid + '.md'), d)
        return d

    def summary(self, **kwargs):
        return reader.summarize(self.project, **kwargs)

    def rows(self, result):
        return [r for g in result['groups'] for r in g.get('tasks', [])] + [
            r for q in result['queues'] + result['runs'] for r in q.get('queue', [])]

    def assert_unknown(self, result, text):
        self.assertGreater(result['counts'].get('unknown', 0), 0)
        self.assertIn(text, json.dumps(result['issues']))

    def test_uninitialized_is_read_only_and_distinct_from_partial_container(self):
        other = self.project / 'other'
        other.mkdir()
        result = reader.summarize(other)
        self.assertFalse(result['initialized'])
        self.assertFalse((other / '.yuzio').exists())
        self.tasks.rmdir()
        self.assertIn('missing container directory', json.dumps(self.summary()['issues']))

    def test_current_revision_skipped_and_old_revision_semantics(self):
        task = self.task()
        self.make_run(task, state='completed', status='completed')
        self.assertEqual(self.summary()['counts'], {'completed': 1})
        self.make_run(task, rid='run-20261025-02', previous='run-20261025-01', state='skipped', status='stopped')
        self.assertEqual(self.summary()['counts'], {'ready': 1})
        self.make_run(task, rid='run-20261025-02', previous='run-20261025-01', state='blocked', status='stopped')
        self.task(revision=2, preparation='draft')
        self.assertEqual(self.summary()['counts'], {'draft': 1})

    def test_source_order_is_not_filename_order(self):
        task = self.task()
        self.make_run(task, rid='run-20261025-99', state='completed', status='completed')
        self.make_run(task, rid='run-20261025-01', previous='run-20261025-99', state='failed', status='stopped')
        self.assertEqual(self.summary()['counts'], {'failed': 1})

    def test_source_chain_gaps_forks_cycles_and_future_revision(self):
        task = self.task()
        first = self.make_run(task, state='completed', status='completed')
        path = self.runs / (first['run_id'] + '.md')
        variants = [('absent', 1, 'missing source Run'), (first['run_id'], 1, 'cyclic'),
                    (None, 2, 'exceeds Task')]
        for previous, rev, error in variants:
            with self.subTest(error=error):
                d = deepcopy(first)
                d['tasks'][0].update(previous_run=previous, revision=rev)
                d['tasks'][0]['definition']['revision'] = rev
                d['tasks'][0]['definition']['ready_scope']['revision'] = rev
                self.write(path, d)
                self.assert_unknown(self.summary(), error)
        self.write(path, first)
        self.make_run(task, rid='run-20261025-02', state='blocked', status='stopped')
        self.assert_unknown(self.summary(), 'branched')

    def test_revision_regression_and_disconnected_cycle(self):
        task = self.task(revision=2)
        first = self.make_run(task, state='completed', status='completed')
        second = self.make_run(self.task(revision=1), rid='run-20261025-02', previous=first['run_id'], state='failed', status='stopped')
        self.task(revision=2)
        self.assert_unknown(self.summary(), 'revision regressed')
        first['tasks'][0]['previous_run'] = second['run_id']
        self.write(self.runs / (first['run_id'] + '.md'), first)
        self.assert_unknown(self.summary(), 'cyclic')

    def test_active_snapshot_mismatch_and_missing_task(self):
        self.make_run()
        self.task(title='changed concurrently')
        self.assert_unknown(self.summary(), 'definition/revision differs')
        self.tasks.joinpath('camera.md').unlink()
        self.assert_unknown(self.summary(), 'Task missing')

    def test_requirement_body_change_is_checked_when_active(self):
        self.make_run()
        p = self.tasks / 'camera.md'
        p.write_text(p.read_text().replace('preserve camera dependency', 'changed requirement'))
        self.assert_unknown(self.summary(), 'definition/revision differs')

    def test_full_definition_record_snapshot_is_compared_without_guessing_shape(self):
        d = self.make_run()
        item = d['tasks'][0]
        del item['definition']['requirement']
        item['definition']['definition_record'] = (self.tasks / 'camera.md').read_text()
        self.write(self.runs / (d['run_id'] + '.md'), d)
        self.assertEqual(self.summary()['counts'], {'queued': 1})
        item['definition']['source_document'] = 'conflicting snapshot'
        self.write(self.runs / (d['run_id'] + '.md'), d)
        self.assert_unknown(self.summary(), 'definition/revision differs')

    def test_hidden_history_errors_and_unrelated_filter_do_not_skip_checks(self):
        task = self.task()
        d = self.make_run(task, state='completed', status='completed')
        d['tasks'][0]['result'] = None
        self.write(self.runs / (d['run_id'] + '.md'), d)
        self.task('unrelated')
        result = self.summary(slugs=['unrelated'])
        self.assert_unknown(result, 'result/state mismatch')
        self.assertEqual(result['total'], 1)
        self.assertEqual(self.summary(states=['ready'])['total'], 0)

    def test_multiple_unfinished_runs_are_reported_globally(self):
        self.make_run()
        self.make_run(self.task('other'), rid='run-20261025-02')
        self.assert_unknown(self.summary(), 'multiple unfinished')

    def test_protocol_rejection_json_corruption_and_duplicate_keys(self):
        task = self.task()
        d = self.make_run(task)
        path = self.runs / (d['run_id'] + '.md')
        d['protocol'] = '0.6'
        self.write(path, d)
        self.assert_unknown(self.summary(), 'unsupported Cadra protocol')
        path.write_text('---\n{"protocol":"0.11","protocol":"0.11"}\n---\n')
        self.assert_unknown(self.summary(), 'duplicate JSON key')
        path.write_text('---\n{broken}\n---\n')
        self.assert_unknown(self.summary(), 'Expecting')

    def test_yaml_task_batch_safe_load_and_no_parser_is_unknown(self):
        for slug in ('camera', 'other'):
            task = self.task(slug)
            raw = '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in task.items())
            (self.tasks / (slug + '.md')).write_text('---\n' + raw + '\n---\n')
        with patch.object(reader.subprocess, 'run', wraps=subprocess.run) as proc:
            self.assertEqual(self.summary()['counts'], {'ready': 2})
            self.assertEqual(proc.call_count, 1)
        with patch.object(reader.shutil, 'which', return_value=None):
            self.assert_unknown(self.summary(), 'YAML parser unavailable')
        for raw in ('protocol: "0.11"\nprotocol: "0.11"', 'slug: &x camera\ntitle: *x',
                    'slug: !!python/object:bad {}', 'slug: [unterminated'):
            (self.tasks / 'camera.md').write_text('---\n' + raw + '\n---\n')
            self.assert_unknown(self.summary(), 'invalid YAML')

    def test_archive_reports_scratch_and_temporary_files_are_excluded(self):
        self.task()
        for directory, filename in ((self.runs, 'run-20261025-01-report-01.md'),
                                    (self.runs, '.run-20261025-01.md'),
                                    (self.runs / 'archive', 'run-20261025-01.md'),
                                    (self.tasks / 'archive', 'bad.md')):
            directory.mkdir(exist_ok=True)
            (directory / filename).write_text('deliberately invalid')
        self.assertEqual(self.summary()['counts'], {'ready': 1})
        self.assertEqual(self.summary()['issues'], [])

    def test_unexpected_run_filename_is_not_silently_dropped(self):
        self.task()
        (self.runs / 'unexpected.md').write_text('---\n{broken}\n---\n')
        self.assert_unknown(self.summary(), 'Expecting')

    def test_created_time_offset_precision_missing_conflict_and_group_order(self):
        self.task('late', created_at='2026-10-29T00:00:00.2Z')
        self.task('early', created_at='2026-10-29T08:00:00.1+08:00')
        self.task('unknown', created_at='2026-10-29T08:00:00')
        self.task('body')
        p = self.tasks / 'body.md'
        d = reader.guard.read_json(reader.guard.split_document(p.read_bytes())[0])
        del d['created_at']
        self.write(p, d, '- 创建：agent，2026-10-28T00:00:00Z；版本 0.11.0\n')
        self.task('conflict')
        p = self.tasks / 'conflict.md'
        p.write_text(p.read_text() + '- 创建：2026-10-28T00:00:00Z\n')
        rows = self.rows(self.summary())
        self.assertEqual([r['slug'] for r in rows], ['body', 'early', 'late', 'conflict', 'unknown'])
        self.assertEqual(rows[1]['created_at'], '2026-10-29 08:00')
        self.assertIsNone(rows[-1]['created_at'])
        self.assertEqual(self.summary()['counts'], {'ready': 5})

    def test_completed_collapses_expands_and_does_not_expand_historical_runs(self):
        self.make_run(state='completed', status='completed')
        result = self.summary()
        self.assertEqual(result['groups'], [dict(state='completed', count=1, collapsed=True)])
        self.assertEqual(result['runs'], [])
        for args in ({'expand_completed': True}, {'states': ['completed']}, {'slugs': ['camera']}):
            result = self.summary(**args)
            self.assertEqual(len(self.rows(result)), 1)
            self.assertEqual(result['runs'], [])
        self.assertEqual(len(self.summary(history=True)['runs']), 1)

    def test_completed_without_group_is_unknown_and_never_collapsed(self):
        data = self.make_run(state='completed', status='completed')
        data['scheduler'] = guard.scheduler.initial()
        path = self.runs / (data['run_id'] + '.md')
        self.write(path, data)
        before = path.read_bytes()
        result = self.summary()
        self.assert_unknown(result, 'completed task requires stable group close')
        self.assertEqual(result['counts'], {'unknown': 1})
        self.assertEqual(self.rows(result)[0]['state'], 'unknown')
        self.assertEqual(path.read_bytes(), before)

    def test_queue_preserves_positions_and_counts_and_details_are_scoped(self):
        first = self.make_run()
        second_task = self.task('second', created_at='2026-10-28T08:00:00+08:00')
        second = self.make_run(second_task, rid='run-20261025-02')
        first['tasks'] += second['tasks']
        first['preflight'] += second['preflight'][1:]
        self.runs.joinpath('run-20261025-02.md').unlink()
        self.write(self.runs / (first['run_id'] + '.md'), first)
        result = self.summary(slugs=['second'])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['queues'][0]['total'], 2)
        self.assertEqual(result['queues'][0]['queue'][0]['position'], 2)
        self.assertEqual(result['groups'], [])
        self.assertIn('details', self.rows(result)[0])
        result = self.summary()
        self.assertNotIn('executor', result['queues'][0])
        self.assertTrue(all('details' not in row for row in self.rows(result)))

    def test_current_action_prepared_dispatched_and_checkpoint_corruption(self):
        d = example()
        task = self.task()
        d['tasks'][0]['definition'] = {**task, 'requirement': 'preserve camera dependency'}
        d['tasks'][0]['agents'] = [binding()]
        pending(d)
        path = self.runs / (d['run_id'] + '.md')
        self.write(path, d)
        result = self.summary()
        self.assertEqual(result['queues'][0]['activity'], 'unknown')
        self.assertEqual(result['queues'][0]['current'][0]['action'], '待派发实现')
        call = d['tasks'][0]['calls'][0]
        call.update(dispatch='dispatched', dispatch_evidence={'agent_id': 'agent-worker', 'source': 'fixture', 'at': d['created_at']})
        self.write(path, d)
        self.assertIn('交付待核对', self.summary()['queues'][0]['current'][0]['action'])
        d['tasks'][0]['checkpoint']['pending_call'] = 999
        self.write(path, d)
        result = self.summary()
        self.assertEqual(result['counts'], {'running': 1})
        self.assertIn('未知：checkpoint mismatch', result['queues'][0]['current'][0]['action'])
        # The reader's projection mode never weakens the publication guard.
        with self.assertRaisesRegex(ValueError, 'checkpoint mismatch'):
            guard.validate(d)
        d['tasks'][0]['checkpoint']['pending_call'] = 1
        call['dispatch_evidence'] = None
        self.write(path, d)
        result = self.summary()
        self.assertEqual(result['counts'], {'running': 1})
        self.assertIn('dispatched call requires evidence', result['queues'][0]['current'][0]['action'])
        d['tasks'][0]['budget']['calls'] = 0
        self.write(path, d)
        self.assert_unknown(self.summary(), 'budget mismatch')

    def test_specific_run_keeps_old_result_after_new_revision(self):
        self.make_run(state='failed', status='stopped')
        self.task(revision=2, preparation='draft', title='Renamed current Task')
        result = self.summary(run_id='run-20261025-01')
        row = result['runs'][0]['queue'][0]
        self.assertEqual(row['state'], 'failed')
        self.assertEqual(row['current_state'], 'draft')
        self.assertEqual(row['run_state'], 'failed')
        self.assertEqual(row['result']['state'], 'failed')
        self.assertEqual(result['counts'], {'failed': 1})
        self.assertEqual(result['current_counts'], {'draft': 1})
        self.assertEqual(row['title'], 'Task camera')
        result = self.summary(run_id='run-20261025-01', slugs=['camera'], states=['failed'])
        row = result['runs'][0]['queue'][0]
        self.assertEqual(row['details']['revision'], 1)
        self.assertEqual(row['details']['run'], 'run-20261025-01')
        self.assertEqual(row['source'], str(self.runs / 'run-20261025-01.md'))
        self.assertEqual(self.summary(run_id='run-20261025-01', states=['draft'])['total'], 0)

    def test_role_request_includes_latest_roles_from_collapsed_history(self):
        d = self.make_run(state='completed', status='completed')
        d['tasks'][0]['agents'] = [binding()]
        self.write(self.runs / (d['run_id'] + '.md'), d)
        result = self.summary(roles=True)
        role_run = result['role_details'][d['run_id']]
        self.assertEqual(role_run['protocol'], '0.11')
        self.assertEqual(role_run['agents']['camera'][0]['agent_id'], 'agent-worker')
        self.assertEqual(result['runs'], [])
        self.assertEqual(result['groups'][0]['collapsed'], True)

    def test_missing_checkpoint_keeps_single_slug_query_available(self):
        d = example()
        task = self.task()
        d['tasks'][0]['definition'] = {**task, 'requirement': 'preserve camera dependency'}
        d['tasks'][0]['state'] = 'running'
        del d['tasks'][0]['checkpoint']
        self.write(self.runs / (d['run_id'] + '.md'), d)
        result = self.summary(slugs=['camera'])
        self.assertEqual(result['counts'], {'running': 1})
        self.assertIn('checkpoint mismatch', result['queues'][0]['current'][0]['action'])
        self.assertIsNone(self.rows(result)[0]['details']['checkpoint'])

    def test_missing_or_invalid_specific_run_retains_diagnostics(self):
        self.make_run()
        path = self.runs / 'run-20261025-01.md'
        path.write_text('---\n{broken}\n---\n')
        result = self.summary(run_id='run-20261025-01')
        self.assertIn('Expecting', json.dumps(result['issues']))
        self.assertIn('requested Run', json.dumps(result['issues']))

    def test_waiting_projection_keeps_checkpoint_and_omits_candidate_input_hashes(self):
        task = self.task()
        d = example()
        d['tasks'][0]['definition'] = {**task, 'requirement': 'preserve camera dependency'}
        candidate = dict(snapshot='fixed-snapshot', sha256='a' * 64,
                         inputs={f'file-{n}.swift': 'b' * 64 for n in range(500)})
        d = guard.scheduler.append_event(d, 'wait', d['created_at'], slug='camera',
            call_id=None, resource='finalization', candidate=candidate,
            scope=task['ready_scope']['scope'],
            stop=dict(agent_id=None, host_id=None, tools_stopped=True,
                      observed_at=d['created_at'], source='synthetic stop'))
        d['tasks'][0]['state'] = 'waiting'
        guard.validate(d)
        self.write(self.runs / (d['run_id'] + '.md'), d)
        result = self.summary()
        self.assertEqual(result['counts'], {'waiting': 1})
        r = result['queues'][0]['scheduling']['requests'][0]
        self.assertEqual((r['call_id'], r['kind']), (None, 'finalization'))
        self.assertIsNone(r['queue_seconds'])
        self.assertNotIn('inputs', r['candidate'])
        self.assertNotIn('file-499', json.dumps(result))

    def test_actions_for_all_four_stages_and_verified_next(self):
        task = self.task()
        d = example()
        d['tasks'][0]['definition'] = {**task, 'requirement': 'preserve camera dependency'}
        pending(d)
        item = d['tasks'][0]
        for stage, label in reader.LABELS.items():
            with self.subTest(stage=stage):
                role = 'reviewer' if stage == 'review' else 'worker'
                item['agents'] = [binding(role)]
                item['calls'][0]['stage'] = stage
                self.write(self.runs / (d['run_id'] + '.md'), d)
                self.assertEqual(self.summary()['queues'][0]['current'][0]['action'], '待派发' + label)
        item['agents'] = [binding()]
        delivery = contract('code', 'review', 'stage_completed')
        delivery['task'] = 'camera'
        item['calls'][0].update(stage='code', closed=True, result={'contract': delivery})
        item['checkpoint']['pending_call'] = None
        self.write(self.runs / (d['run_id'] + '.md'), d)
        self.assertEqual(self.summary()['queues'][0]['current'][0]['action'], '等待评审')

    def test_malformed_or_wrong_task_delivery_is_action_unknown_without_crash(self):
        task = self.task()
        d = example()
        d['tasks'][0]['definition'] = {**task, 'requirement': 'preserve camera dependency'}
        d['tasks'][0]['agents'] = [binding()]
        pending(d)
        item = d['tasks'][0]
        delivery = contract('code', 'review', 'stage_completed')
        delivery['task'] = 'camera'
        item['calls'][0].update(closed=True, result={'contract': delivery})
        item['checkpoint']['pending_call'] = None
        for changes in ({'next': None}, {'next': []}, {'task': 'different-task'}, {'execution_mode': 'attended'},
                        {'candidate': []}, {'blocked': None}, {'status': 'bad'}, {'acceptance': None},
                        {'findings': {'blocking': -1, 'non_blocking': 0}}):
            with self.subTest(changes=changes):
                item['calls'][0]['result']['contract'] = {**delivery, **changes}
                self.write(self.runs / (d['run_id'] + '.md'), d)
                result = self.summary()
                self.assertEqual(result['counts'], {'running': 1})
                self.assertTrue(result['queues'][0]['current'][0]['action'].startswith('未知：'))

    def test_completed_queue_entry_with_unknown_task_is_never_collapsed(self):
        d = self.make_run(state='completed', status='running')
        (self.tasks / 'camera.md').write_text('---\n{broken}\n---\n')
        result = self.summary()
        self.assertEqual(result['counts'], {'unknown': 1})
        self.assertEqual(result['queues'][0]['completed_hidden'], 0)
        self.assertEqual(self.rows(result)[0]['state'], 'unknown')

    def test_isolated_installed_copy_has_no_repository_runtime_dependency(self):
        self.make_run()
        installed = self.project / 'installation/cadra'
        shutil.copytree(SCRIPT.parents[1], installed)
        proc = subprocess.run([sys.executable, '-B', str(installed / 'scripts/list_summary.py'),
                               '--project', str(self.project)], capture_output=True, text=True, check=True,
                              cwd=self.project)
        self.assertEqual(json.loads(proc.stdout)['counts'], {'queued': 1})

    def test_linked_container_is_not_traversed(self):
        self.runs.rmdir()
        self.runs.symlink_to(self.project)
        with self.assertRaisesRegex(ValueError, 'linked container'):
            self.summary()

    def test_readonly_cli_and_projection_size_with_large_snapshots(self):
        # Large completed history remains locally checked without model context.
        for n in range(30):
            slug = f'task-{n}'
            task = self.task(slug)
            d = self.make_run(task, rid=f'run-20261025-{n+1:02}', state='completed', status='completed')
            d['tasks'][0]['definition']['source_document'] = 'Requirement ' * 3000
            self.write(self.runs / (d['run_id'] + '.md'), d)
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()}
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT), '--project', str(self.project)],
                              text=True, capture_output=True, check=True)
        result = json.loads(proc.stdout)
        self.assertEqual(result['counts'], {'completed': 30})
        self.assertEqual(result['issues'], [])
        self.assertLess(len(proc.stdout.encode()), sum(len(v[0]) for v in before.values()) // 100)
        after = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(list(self.root.rglob('.writer.lock')))

    def test_concurrent_mutation_invalidates_summary(self):
        self.task()
        original = reader.guard.digest
        calls = []
        def mutate(raw):
            calls.append(None)
            return original(raw) if len(calls) == 1 else 'changed'
        with patch.object(reader.guard, 'digest', side_effect=mutate):
            result = self.summary()
        self.assertFalse(result['scan']['stable'])
        self.assert_unknown(result, 'changed during query')


if __name__ == '__main__':
    unittest.main()

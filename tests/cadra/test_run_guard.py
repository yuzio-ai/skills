"""Exercise the shipped guard against real temporary Run files and processes."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'cadra/scripts/run_guard.py'
spec = importlib.util.spec_from_file_location('cadra_run_guard', SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

AT = '2026-10-25T10:00:00+08:00'
LATER = '2026-10-25T11:00:00+08:00'


def example(protocol='0.10', flow='code'):
    return {
        'protocol': protocol, 'run_id': 'run-20261025-01', 'status': 'running',
        'created_at': AT, 'execution_mode': 'unattended',
        'skill_version': '0.10.0',
        'executor': {'instance_id': 'first', 'generation': 1, 'host_id': 'local',
                     'thread_id': 'chat-1', 'turn_id': 'turn-1', 'claimed_at': AT,
                     'progress': {'at': AT, 'event': 'run_created'}},
        'ownership_history': [], 'reports': [], 'append_history': [],
        'preflight': [dict(scope='project', status='passed', at=AT, inputs={}, evidence='project check'),
                      dict(scope='task', slug='camera', status='passed', at=AT, inputs={}, evidence='inputs and commands')],
        'tasks': [{'slug': 'camera', 'revision': 1, 'previous_run': None,
                   'definition': {'protocol': protocol, 'slug': 'camera', 'revision': 1,
                                  'requirement': 'preserve camera dependency', 'flow': flow, 'preparation': 'ready'},
                   'start_action': {'kind': 'first_start', 'stage': guard.normalize_flow(flow, protocol)[0]},
                   'authorization_consumed': False, 'state': 'queued',
                   'budget': {'calls': 0, 'remediation': 0, 'retries': {}},
                   'checkpoint': {'pending_call': None, 'last_delivery': None},
                   'calls': [], 'agents': [], 'result': None}],
    }


def document(data):
    return ('---\n' + json.dumps(data, ensure_ascii=False, indent=2) + '\n---\n\n# Run\n').encode()


def binding(role='worker', agent_id='agent-worker', id_='worker-1'):
    return dict(id=id_, role=role, agent_id=agent_id, host_id='local', created_at=AT,
                source='host spawn response', supersedes=None, stop_observation=None)


def pending(data):
    task = data['tasks'][0]
    task['state'] = 'running'
    task['calls'] = [{'id': 1, 'stage': 'code', 'execution_mode': 'unattended', 'reason': 'first_start',
                      'agent_ref': 'worker-1', 'dispatch_evidence': None, 'before': None, 'dispatch': 'prepared', 'closed': False, 'result': None,
                      'charged': {'calls': 1, 'remediation': 0, 'retry_stage': None}, 'prepared_at': AT}]
    task['budget']['calls'] = 1
    task['checkpoint']['pending_call'] = 1


class RunGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.runs = self.root / '.yuzio/cadra/runs'
        self.runs.mkdir(parents=True)
        self.path = self.runs / 'run-20261025-01.md'
        self.data = example(getattr(self, 'protocol', '0.10'), getattr(self, 'configured_flow', 'code'))
        self.sha = guard.publish(self.path, document(self.data), None, 'first', 1, 'create')

    def bind_worker(self):
        self.data['tasks'][0]['agents'] = [binding()]
        self.sha = guard.publish(self.path, document(self.data), self.sha, 'first', 1)

    def close_run(self, status='completed', task_state='completed'):
        self.bind_worker()
        pending(self.data)
        self.sha = guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        task = self.data['tasks'][0]
        task['calls'][0].update(dispatch='dispatched', dispatch_evidence={
            'agent_id': 'agent-worker', 'source': 'fixture dispatch', 'at': AT})
        self.sha = guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        delivery = {'handoff': 'code-01.md'}
        task['calls'][0].update(closed=True, result=delivery)
        task['checkpoint'].update(pending_call=None, last_delivery=delivery)
        task.update(state=task_state, result={
            'state': task_state, 'last_delivery': delivery,
            'candidate': {'commit': None, 'snapshot': 'candidate-01'},
            'findings': ['fixture finding'], 'acceptance': {'status': 'pending'},
            'human_action': 'verify runtime', 'next': 'manual acceptance'})
        self.sha = guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        self.data['status'] = status
        self.data['executor']['progress'] = {'at': LATER, 'event': 'run_closed'}
        self.sha = guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        self.assertFalse(guard.unfinished(guard.current(self.path.read_bytes())[0]))

    def observation(self, state='stopped', tools=True):
        return {'instance_id': 'first', 'generation': 1, 'observed_at': LATER,
                'host_id': 'local', 'thread_id': 'chat-1', 'turn_id': 'turn-1', 'source_kind': 'host',
                'source': 'host exact turn and tool completion result', 'state': state, 'tools_stopped': tools,
                'children': [dict(agent_id=b['agent_id'], host_id=b['host_id'], observed_at=LATER,
                                  state=state, tools_stopped=tools, source='host child tools stopped')
                             for t in self.data['tasks'] for b in t['agents']]}

    def takeover(self, observation=None, instance='second'):
        observation = observation or self.observation()
        new = deepcopy(self.data)
        new['ownership_history'].append({'previous': self.data['executor'], 'observation': observation})
        new['executor'].update(instance_id=instance, generation=2, claimed_at=LATER,
                               turn_id='turn-2',
                               progress={'at': LATER, 'event': 'takeover'})
        return new

    def test_inspect_is_readonly_and_prepared_does_not_mean_stopped(self):
        self.bind_worker()
        pending(self.data)
        guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        before = self.path.read_bytes()
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT), 'inspect', '--run', str(self.path)],
                              capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(proc.stdout)['activity'], 'unknown')
        self.assertEqual(self.path.read_bytes(), before)

    def test_active_unknown_idle_and_old_observations_never_allow_takeover(self):
        observations = [self.observation('active'), self.observation('notLoaded'),
                        self.observation('idle'), self.observation(tools=False),
                        {**self.observation(), 'generation': 0},
                        {**self.observation(), 'observed_at': '2026-10-24T10:00:00+08:00'},
                        {**self.observation(), 'source': ''}]
        before = self.path.read_bytes()
        for obs in observations:
            with self.subTest(observation=obs), self.assertRaises(ValueError):
                guard.publish(self.path, document(self.takeover(obs)), self.sha, 'second', 2, 'takeover', obs)
            self.assertEqual(self.path.read_bytes(), before)

    def test_long_running_tool_does_not_expire_owner(self):
        obs = {**self.observation('active', False), 'observed_at': '2027-01-01T00:00:00+08:00'}
        self.assertEqual(guard.activity(self.data['executor'], obs), 'active')
        self.assertEqual(guard.activity(self.data['executor'], None), 'unknown')

    def test_takeover_preserves_call_and_closes_delivered_result_without_charging_twice(self):
        self.bind_worker()
        pending(self.data)
        self.sha = guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        obs = self.observation()
        new = self.takeover(obs)
        sha = guard.publish(self.path, document(new), self.sha, 'second', 2, 'takeover', obs)
        self.assertEqual(new['tasks'], self.data['tasks'])
        # A complete matching Cohestra result has been independently verified.
        task = new['tasks'][0]
        task['calls'][0].update(closed=True, dispatch='dispatched', dispatch_evidence={'agent_id': 'agent-worker', 'source': 'host call result', 'at': AT}, result={'handoff': 'code-01.md', 'contract': {'stage_result': {'stage': 'code', 'round': 1}}})
        task['checkpoint']['pending_call'] = None
        guard.publish(self.path, document(new), sha, 'second', 2)
        actual, _ = guard.current(self.path.read_bytes())
        self.assertEqual(actual['tasks'][0]['budget']['calls'], 1)
        self.assertEqual(len(actual['tasks'][0]['calls']), 1)

    def test_two_resume_processes_cannot_both_claim_same_generation(self):
        obs = self.observation()
        obs_path = self.root / 'observation.json'
        obs_path.write_text(json.dumps(obs))
        processes = []
        for who in ('second', 'third'):
            proposal = self.root / (who + '.md')
            proposal.write_bytes(document(self.takeover(obs, who)))
            processes.append(subprocess.Popen([
                sys.executable, '-B', str(SCRIPT), 'takeover', '--run', str(self.path),
                '--proposal', str(proposal), '--expected-sha256', self.sha, '--instance', who,
                '--generation', '2', '--observation', str(obs_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        for proc in processes:
            proc.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 1])
        actual, _ = guard.current(self.path.read_bytes())
        self.assertEqual(actual['executor']['generation'], 2)
        self.assertEqual(len(actual['ownership_history']), 1)

    def test_stale_writer_and_definition_change_rejected(self):
        new = self.takeover()
        sha = guard.publish(self.path, document(new), self.sha, 'second', 2, 'takeover', self.observation())
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(new), sha, 'first', 1)
        new['tasks'][0]['definition']['requirement'] = 'different requirement'
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(new), sha, 'second', 2)

    def test_preflight_missing_failed_or_mislabelled_deferred_rejected(self):
        for checks in ([], self.data['preflight'][:1],
                       [{**c, 'status': 'failed'} for c in self.data['preflight']],
                       [{**c, 'status': 'deferred', 'produced_by': 'code'} for c in self.data['preflight']]):
            new = deepcopy(self.data)
            new['preflight'] = checks
            with self.assertRaises(ValueError):
                guard.validate(new)
        new = deepcopy(self.data)
        new['preflight'].append(dict(scope='task', slug='camera', status='deferred', at=AT,
                                     inputs={}, evidence='generated asset checked before adoption', produced_by='code'))
        guard.validate(new)

    def test_closed_call_budget_and_report_history_are_protected(self):
        self.bind_worker()
        pending(self.data)
        self.sha = guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        self.data['tasks'][0]['calls'][0].update(closed=True, result={'handoff': 'code-01.md'})
        self.data['tasks'][0]['checkpoint']['pending_call'] = None
        self.sha = guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        new = deepcopy(self.data)
        new['tasks'][0]['calls'][0]['result']['handoff'] = 'invented.md'
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(new), self.sha, 'first', 1)
        new = deepcopy(self.data)
        new['tasks'][0]['budget']['calls'] = 0
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(new), self.sha, 'first', 1)
        new = deepcopy(self.data)
        new['reports'].append({'path': 'run-20261025-01-report-01.md'})
        guard.publish(self.path, document(new), self.sha, None, None, 'report')

    def assert_closed_report_preserves_execution(self, status, task_state):
        self.close_run(status, task_state)
        before, body = guard.current(self.path.read_bytes())
        report = self.runs / 'run-20261025-01-report-01.md'
        report.write_text('# Saved report\n', encoding='utf-8')
        proposed = deepcopy(before)
        proposed['reports'].append({'path': report.name})
        guard.publish(self.path, document(proposed), self.sha, None, None, 'report')
        after, after_body = guard.current(self.path.read_bytes())
        self.assertEqual(after['reports'], [{'path': report.name}])
        self.assertEqual({k: v for k, v in after.items() if k != 'reports'},
                         {k: v for k, v in before.items() if k != 'reports'})
        self.assertEqual(after_body, body)
        self.assertEqual(report.read_text(encoding='utf-8'), '# Saved report\n')
        self.assertFalse(guard.unfinished(after))

    def test_completed_run_report_preserves_execution(self):
        self.assert_closed_report_preserves_execution('completed', 'completed')

    def test_completed_run_with_failed_task_accepts_report(self):
        self.assert_closed_report_preserves_execution('completed', 'failed')

    def test_closed_stopped_run_report_preserves_execution(self):
        self.assert_closed_report_preserves_execution('stopped', 'blocked')

    def test_closed_run_report_cannot_change_execution_or_body(self):
        self.close_run()
        original = self.path.read_bytes()
        variants = []
        for key, value in [('status', 'stopped'), ('executor', {
                **self.data['executor'], 'progress': {'at': LATER, 'event': 'report'}})]:
            changed = deepcopy(self.data)
            changed[key] = value
            variants.append(document(changed))
        for key, value in [('result', {'state': 'completed', 'acceptance': {'status': 'passed'}}),
                           ('budget', {'calls': 0, 'remediation': 0, 'retries': {}})]:
            changed = deepcopy(self.data)
            changed['tasks'][0][key] = value
            variants.append(document(changed))
        changed = deepcopy(self.data)
        changed['tasks'][0]['calls'][0]['result'] = {'handoff': 'replacement.md'}
        variants.extend([document(changed), original.replace(b'# Run', b'# Rewritten')])
        for proposed in variants:
            with self.subTest(proposed=proposed), self.assertRaises(ValueError):
                guard.publish(self.path, proposed, self.sha, None, None, 'report')
            self.assertEqual(self.path.read_bytes(), original)

    def test_stale_report_registration_rebases_without_losing_existing_link(self):
        self.close_run()
        closed, body = guard.current(self.path.read_bytes())
        reports = [self.runs / f'run-20261025-01-report-{n:02d}.md' for n in (1, 2)]
        for report in reports:
            report.write_text(f'# {report.stem}\n', encoding='utf-8')
        saved_reports = {report: report.read_bytes() for report in reports}
        first, stale = deepcopy(closed), deepcopy(closed)
        first['reports'].append({'path': reports[0].name})
        stale['reports'].append({'path': reports[1].name})
        guard.publish(self.path, document(first), self.sha, None, None, 'report')
        registered = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Run changed; reread before writing'):
            guard.publish(self.path, document(stale), self.sha, None, None, 'report')
        self.assertEqual(self.path.read_bytes(), registered)
        latest, _ = guard.current(registered)
        latest['reports'].append({'path': reports[1].name})
        guard.publish(self.path, document(latest), guard.digest(registered), None, None, 'report')
        final, final_body = guard.current(self.path.read_bytes())
        self.assertEqual(final['reports'], [{'path': report.name} for report in reports])
        self.assertEqual({k: v for k, v in final.items() if k != 'reports'},
                         {k: v for k, v in closed.items() if k != 'reports'})
        self.assertEqual(final_body, body)
        self.assertEqual({report: report.read_bytes() for report in reports}, saved_reports)

    def test_report_registration_write_failure_preserves_closed_run_and_report(self):
        from unittest.mock import patch
        self.close_run()
        original = self.path.read_bytes()
        report = self.runs / 'run-20261025-01-report-01.md'
        report.write_text('# Saved report\n', encoding='utf-8')
        saved = report.read_bytes()
        proposed = deepcopy(self.data)
        proposed['reports'].append({'path': report.name})
        with patch.object(guard.os, 'replace', side_effect=OSError('injected report failure')):
            with self.assertRaises(OSError):
                guard.publish(self.path, document(proposed), self.sha, None, None, 'report')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(report.read_bytes(), saved)
        self.assertFalse(list(self.runs.glob('.run-*')))


    def test_new_run_does_not_overwrite_or_bypass_active_run(self):
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(self.data), None, 'first', 1, 'create')
        new = deepcopy(self.data)
        new['run_id'] = 'run-20261025-02'
        with self.assertRaises(ValueError):
            guard.publish(self.runs / (new['run_id'] + '.md'), document(new), None, 'first', 1, 'create')

    def test_duplicate_fields_and_legacy_definition_cannot_be_published(self):
        field = ('"protocol": "' + self.data['protocol'] + '",').encode()
        raw = document(self.data).replace(field, field + b' ' + field, 1)
        with self.assertRaises(ValueError):
            guard.publish(self.path, raw, self.sha, 'first', 1)
        new = deepcopy(self.data)
        new['tasks'][0]['definition']['protocol'] = '0.6'
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(new), self.sha, 'first', 1)

    def test_report_cannot_rewrite_execution_and_unknown_observation_is_readonly(self):
        before = self.path.read_bytes()
        changed = document(self.data).replace(b'# Run', b'# Rewritten history')
        with self.assertRaises(ValueError):
            guard.publish(self.path, changed, self.sha, None, None, 'report')
        self.assertEqual(guard.activity(self.data['executor'], []), 'unknown')
        self.assertEqual(self.path.read_bytes(), before)

    def test_failure_before_replace_preserves_run_and_cleans_temporary(self):
        from unittest.mock import patch
        self.bind_worker()
        before = self.path.read_bytes()
        new = deepcopy(self.data)
        pending(new)
        with patch.object(guard.os, 'replace', side_effect=OSError('injected write failure')):
            with self.assertRaises(OSError):
                guard.publish(self.path, document(new), self.sha, 'first', 1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.runs.glob('.run-*')), [])

    def test_observation_binds_host_chat_and_turn_and_requires_source_kind(self):
        before = self.path.read_bytes()
        for key in ('host_id', 'thread_id', 'turn_id', 'source_kind'):
            for value in (None, 'different'):
                obs = {**self.observation(), key: value}
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    guard.publish(self.path, document(self.takeover(obs)), self.sha, 'second', 2, 'takeover', obs)
        obs = self.observation()
        del obs['turn_id']
        self.assertEqual(guard.activity(self.data['executor'], obs), 'unknown')
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_host_identity_requires_explicit_human_handoff(self):
        owner = deepcopy(self.data['executor'])
        owner['turn_id'] = None
        obs = {**self.observation(), 'turn_id': None}
        self.assertEqual(guard.activity(owner, obs), 'unknown')
        obs.update(source_kind='human_handoff', source='user message confirms this instance and its tools stopped')
        self.assertEqual(guard.activity(owner, obs), 'stopped')
        for change in ({'tools_stopped': False}, {'generation': 2}, {'thread_id': 'other'}, {'source': ''}):
            self.assertEqual(guard.activity(owner, {**obs, **change}), 'unknown')

    def test_takeover_cannot_rewrite_body_or_pending_work(self):
        before = self.path.read_bytes()
        changed = document(self.takeover()).replace(b'# Run', b'# Rewritten history')
        with self.assertRaises(ValueError):
            guard.publish(self.path, changed, self.sha, 'second', 2, 'takeover', self.observation())
        self.assertEqual(self.path.read_bytes(), before)

    def test_new_call_requires_separate_prepared_publication(self):
        self.bind_worker()
        for closed, dispatch in ((True, 'dispatched'), (True, 'prepared'), (False, 'dispatched')):
            new = deepcopy(self.data)
            pending(new)
            task = new['tasks'][0]
            task['calls'][0].update(closed=closed, dispatch=dispatch, result={'handoff': 'code-01.md'} if closed else None)
            task['checkpoint']['pending_call'] = None if closed else 1
            with self.subTest(closed=closed, dispatch=dispatch), self.assertRaises(ValueError):
                guard.publish(self.path, document(new), self.sha, 'first', 1)

    def test_pending_call_cannot_be_bypassed_even_when_closed_in_same_update(self):
        self.bind_worker()
        pending(self.data)
        self.sha = guard.publish(self.path, document(self.data), self.sha, 'first', 1)
        for close_old in (False, True):
            new = deepcopy(self.data)
            task = new['tasks'][0]
            second = deepcopy(task['calls'][0])
            second['id'] = 2
            second['before'] = {'stage_result': {'stage': 'code', 'status': 'completed', 'round': 1},
                                'next': {'stage': 'review', 'allowed': True, 'reason': 'stage_completed'}}
            if close_old:
                task['calls'][0].update(closed=True, result={'handoff': 'code-01.md'})
            else:
                second.update(closed=True, result={'handoff': 'review-01.md'})
            task['calls'].append(second)
            task['budget']['calls'] = 2
            task['checkpoint']['pending_call'] = 2 if close_old else 1
            with self.subTest(close_old=close_old), self.assertRaises(ValueError):
                guard.publish(self.path, document(new), self.sha, 'first', 1)
        # Closing the original call and then persisting the next intent is valid.
        closed = deepcopy(self.data)
        closed['tasks'][0]['calls'][0].update(closed=True, result={'handoff': 'code-01.md'})
        closed['tasks'][0]['checkpoint']['pending_call'] = None
        sha = guard.publish(self.path, document(closed), self.sha, 'first', 1)
        guard.publish(self.path, document(new), sha, 'first', 1)
        self.assertEqual(guard.current(self.path.read_bytes())[0]['tasks'][0]['budget']['calls'], 2)



    def test_old_json_and_yaml_are_rejected_without_writes(self):
        before = self.path.read_bytes()
        for protocol in ('0.6', '0.7', '0.8', '0.9', '0.99', None):
            old = deepcopy(self.data)
            old['protocol'] = protocol
            raw = document(old)
            with self.subTest(protocol=protocol):
                with self.assertRaisesRegex(ValueError, 'archive'):
                    guard.current(raw)
                with self.assertRaises(ValueError):
                    guard.publish(self.path, raw, self.sha, 'first', 1)
                self.assertEqual(self.path.read_bytes(), before)
                self.path.write_bytes(raw)
                proc = subprocess.run([sys.executable, '-B', str(SCRIPT), 'inspect', '--run', str(self.path)],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 1)
                self.assertIn('archive', proc.stderr)
                self.assertEqual(self.path.read_bytes(), raw)
                self.path.write_bytes(before)
        with self.assertRaisesRegex(ValueError, 'archive'):
            guard.header(b"---\nprotocol: '0.6'\nstatus: completed\n---\n")

    def test_old_run_in_active_container_blocks_create_until_archived(self):
        self.path.unlink()
        old = self.runs / 'run-20261024-01.md'
        raw = b"---\nprotocol: '0.6'\nstatus: completed\n---\n"
        old.write_bytes(raw)
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(self.data), None, 'first', 1, 'create')
        self.assertFalse(self.path.exists())
        self.assertEqual(old.read_bytes(), raw)
        archive = self.root / '.yuzio/cadra-archive/test/runs'
        archive.mkdir(parents=True)
        old.rename(archive / old.name)
        guard.publish(self.path, document(self.data), None, 'first', 1, 'create')
        self.assertEqual((archive / old.name).read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()

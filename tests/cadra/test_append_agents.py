"""Exercise 0.11 queue and agent invariants through the shipped publication guard."""
from copy import deepcopy
import json
import subprocess
import sys
import unittest

from . import test_run_guard as fixtures
from .test_run_guard import AT, LATER, SCRIPT, binding, document, example, guard, pending


def appended(data, slugs=('second',)):
    new = deepcopy(data)
    batch = []
    for slug in slugs:
        task = deepcopy(example(data['protocol'])['tasks'][0])
        task['slug'] = task['definition']['slug'] = slug
        new['tasks'].append(task)
        new['preflight'].append(dict(scope='task', slug=slug, status='passed', at=LATER,
                                     inputs={}, evidence='Ready Gate and source rechecked'))
        batch.append(dict(slug=slug, revision=1))
    new['append_history'].append(dict(at=LATER, source='explicit user append request', tasks=batch))
    return new


class AppendAgentTests(unittest.TestCase):
    setUp = fixtures.RunGuardTests.setUp
    bind_worker = fixtures.RunGuardTests.bind_worker
    observation = fixtures.RunGuardTests.observation
    takeover = fixtures.RunGuardTests.takeover

    def publish(self, data, mode='update', sha=None):
        return guard.publish(self.path, document(data), sha or self.sha,
                             'first' if mode == 'update' else None, 1 if mode == 'update' else None, mode)

    def assert_rejected(self, data, mode='update'):
        before = self.path.read_bytes()
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.publish(data, mode)
        self.assertEqual(self.path.read_bytes(), before)

    def test_append_by_foreign_caller_preserves_pending_stage_and_owner(self):
        self.bind_worker()
        pending(self.data)
        self.sha = self.publish(self.data)
        new = appended(self.data)
        self.publish(new, 'append')
        actual, _ = guard.current(self.path.read_bytes())
        self.assertEqual(actual['tasks'][0], self.data['tasks'][0])
        self.assertEqual(actual['executor'], self.data['executor'])
        self.assertEqual(actual['append_history'], new['append_history'])

    def test_append_rejects_nonready_removed_flow_missing_preflight_and_duplicate_atomically(self):
        for fault in ('draft', 'flow', 'preflight', 'duplicate'):
            new = appended(self.data, ('second', 'third'))
            if fault == 'draft': new['tasks'][-1]['definition']['preparation'] = 'draft'
            if fault == 'flow': new['tasks'][-1]['definition']['flow'] = 'small-change'
            if fault == 'preflight': new['preflight'].pop()
            if fault == 'duplicate':
                new['tasks'][-1]['slug'] = new['tasks'][-1]['definition']['slug'] = 'camera'
            with self.subTest(fault=fault): self.assert_rejected(new, 'append')

    def test_append_cannot_change_prefix_owner_budget_body_or_other_fields(self):
        for fault in ('definition', 'state', 'executor', 'reports', 'preflight'):
            new = appended(self.data)
            if fault == 'definition': new['tasks'][0]['definition']['requirement'] = 'changed'
            if fault == 'state': new['tasks'][0]['state'] = 'running'
            if fault == 'executor': new['executor']['generation'] += 1
            if fault == 'reports': new['reports'].append('unrelated')
            if fault == 'preflight': new['preflight'][0]['evidence'] = 'changed'
            with self.subTest(fault=fault): self.assert_rejected(new, 'append')
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(appended(self.data)).replace(b'# Run', b'# changed'),
                          self.sha, None, None, 'append')
        self.assertEqual(before, self.path.read_bytes())

    def test_append_requires_exact_audit_suffix_and_sorted_batch(self):
        new = appended(self.data, ('z', 'a'))
        self.assert_rejected(new, 'append')
        new = appended(self.data)
        new['append_history'][0]['tasks'][0]['revision'] = 2
        self.assert_rejected(new, 'append')
        new = appended(self.data)
        new['append_history'] = []
        self.assert_rejected(new, 'append')

    def test_duplicate_request_does_not_append_twice(self):
        new = appended(self.data)
        self.sha = self.publish(new, 'append')
        self.assert_rejected(appended(new), 'append')
        self.assert_rejected(new, 'append')

    def test_normal_update_cannot_append_or_reorder(self):
        self.assert_rejected(appended(self.data))
        new = appended(self.data)
        self.sha = self.publish(new, 'append')
        new['tasks'].reverse()
        self.assert_rejected(new)

    def test_stale_stage_update_cannot_erase_append_and_can_rebase(self):
        self.bind_worker()
        stage = deepcopy(self.data)
        pending(stage)
        new = appended(self.data)
        latest = self.publish(new, 'append')
        self.assert_rejected(stage)
        new['tasks'][0] = stage['tasks'][0]
        self.publish(new, sha=latest)
        actual, _ = guard.current(self.path.read_bytes())
        self.assertEqual([t['slug'] for t in actual['tasks']], ['camera', 'second'])
        self.assertEqual(actual['tasks'][0]['budget']['calls'], 1)

    def completed(self):
        new = deepcopy(self.data)
        new['tasks'][0].update(state='completed', result={'state': 'completed', 'last_delivery': 'adopted evidence'})
        new['status'] = 'completed'
        return new

    def test_closeout_wins_then_append_is_rejected(self):
        close = self.completed()
        self.sha = self.publish(close)
        self.assert_rejected(appended(self.data), 'append')
        self.assert_rejected(appended(close), 'append')

    def test_append_wins_then_old_closeout_is_rejected(self):
        self.publish(appended(self.data), 'append')
        self.assert_rejected(self.completed())

    def test_interrupted_or_stopped_run_cannot_append(self):
        for state in ('interrupted', 'stopped'):
            new = deepcopy(self.data)
            new['status'] = state
            self.sha = self.publish(new)
            self.assert_rejected(appended(new), 'append')
            self.sha = self.publish(self.data)

    def test_two_append_processes_cannot_overwrite_each_other(self):
        processes = []
        for slug in ('a', 'b'):
            proposal = self.root / (slug + '.md')
            proposal.write_bytes(document(appended(self.data, (slug,))))
            processes.append(subprocess.Popen([sys.executable, '-B', str(SCRIPT), 'append',
                '--run', str(self.path), '--proposal', str(proposal), '--expected-sha256', self.sha],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        for process in processes: process.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 1])
        actual, _ = guard.current(self.path.read_bytes())
        self.assertEqual(len(actual['tasks']), 2)
        self.assertEqual(len(actual['append_history']), 1)

    def test_append_and_closeout_processes_have_one_winner(self):
        processes = []
        for mode, data in (('append', appended(self.data)), ('update', self.completed())):
            proposal = self.root / (mode + '.md')
            proposal.write_bytes(document(data))
            args = [sys.executable, '-B', str(SCRIPT), mode, '--run', str(self.path),
                    '--proposal', str(proposal), '--expected-sha256', self.sha]
            if mode == 'update': args += ['--instance', 'first', '--generation', '1']
            processes.append(subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        for process in processes: process.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 1])
        actual, _ = guard.current(self.path.read_bytes())
        self.assertIn((actual['status'], len(actual['tasks'])), [('running', 2), ('completed', 1)])

    def test_append_does_not_reuse_stale_preflight_for_future_slug(self):
        self.data['preflight'].append(dict(scope='task', slug='second', status='passed', at=AT,
                                           inputs={}, evidence='old unrelated check'))
        self.sha = self.publish(self.data)
        new = appended(self.data)
        new['preflight'].pop()
        self.assert_rejected(new, 'append')

    def test_takeover_cannot_predate_child_observation(self):
        self.bind_worker()
        obs = self.observation()
        obs['children'][0]['observed_at'] = '2026-10-25T12:00:00+08:00'
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(self.takeover(obs)), self.sha, 'second', 2, 'takeover', obs)

    def test_binding_must_be_persisted_before_call(self):
        new = deepcopy(self.data)
        new['tasks'][0]['agents'] = [binding()]
        pending(new)
        self.assert_rejected(new)
        self.bind_worker()
        pending(self.data)
        self.publish(self.data)

    def test_worker_cannot_perform_review(self):
        self.bind_worker()
        new = deepcopy(self.data)
        pending(new)
        new['tasks'][0]['calls'][0]['stage'] = 'review'
        self.assert_rejected(new)

    def test_agent_cannot_be_reused_for_another_role_or_task(self):
        self.bind_worker()
        new = deepcopy(self.data)
        new['tasks'][0]['agents'].append(binding('reviewer', 'agent-worker', 'reviewer-1'))
        self.assert_rejected(new)
        new = appended(self.data)
        self.sha = self.publish(new, 'append')
        new['tasks'][1]['agents'] = [binding()]
        self.assert_rejected(new)

    def test_replacement_requires_stop_proof_and_preserves_history(self):
        self.bind_worker()
        new = deepcopy(self.data)
        second = binding(agent_id='worker-new', id_='worker-2')
        second.update(supersedes='worker-1', created_at=LATER)
        new['tasks'][0]['agents'].append(second)
        self.assert_rejected(new)
        second['stop_observation'] = self.observation()['children'][0]
        self.sha = self.publish(new)
        actual, _ = guard.current(self.path.read_bytes())
        self.assertEqual(actual['tasks'][0]['agents'][0], binding())
        pending(new)
        self.assert_rejected(new)  # cannot use superseded worker
        new['tasks'][0]['calls'][0].update(agent_ref='worker-2', prepared_at=LATER)
        self.publish(new)

    def test_replacement_rejects_stop_proof_from_before_later_call(self):
        self.bind_worker()
        pending(self.data)
        self.data['tasks'][0]['calls'][0]['prepared_at'] = LATER
        self.sha = self.publish(self.data)
        call = self.data['tasks'][0]['calls'][0]
        call.update(closed=True, result={'handoff': 'code-01.md'})
        self.data['tasks'][0]['checkpoint']['pending_call'] = None
        self.sha = self.publish(self.data)
        new = deepcopy(self.data)
        second = binding(agent_id='replacement', id_='worker-2')
        second.update(supersedes='worker-1', created_at=LATER,
                      stop_observation=dict(agent_id='agent-worker', host_id='local', state='stopped',
                                            tools_stopped=True, observed_at=AT, source='stale stop proof'))
        new['tasks'][0]['agents'].append(second)
        self.assert_rejected(new)

    def test_pending_call_prevents_agent_replacement_or_binding_rewrite(self):
        self.bind_worker()
        pending(self.data)
        self.sha = self.publish(self.data)
        new = deepcopy(self.data)
        new['tasks'][0]['agents'][0]['agent_id'] = 'invented'
        self.assert_rejected(new)
        new = deepcopy(self.data)
        new['tasks'][0]['agents'].append(binding('reviewer', 'reviewer', 'reviewer-1'))
        self.assert_rejected(new)

    def test_dispatch_evidence_required_and_immutable(self):
        self.bind_worker()
        pending(self.data)
        self.sha = self.publish(self.data)
        new = deepcopy(self.data)
        new['tasks'][0]['calls'][0]['dispatch'] = 'dispatched'
        self.assert_rejected(new)
        new['tasks'][0]['calls'][0]['dispatch_evidence'] = dict(agent_id='agent-worker', at=AT, source='host call handle')
        self.sha = self.publish(new)
        new['tasks'][0]['calls'][0]['dispatch_evidence']['source'] = 'replacement handle'
        self.assert_rejected(new)

    def test_stopped_parent_with_active_unknown_or_stale_child_cannot_takeover(self):
        self.bind_worker()
        pending(self.data)
        self.sha = self.publish(self.data)
        for change in ({'state': 'active'}, {'tools_stopped': False}, {'agent_id': 'other'},
                       {'observed_at': '2026-10-24T00:00:00+08:00'}):
            obs = self.observation()
            obs['children'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                guard.publish(self.path, document(self.takeover(obs)), self.sha, 'second', 2, 'takeover', obs)
        obs = self.observation()
        del obs['children']
        with self.assertRaises(ValueError):
            guard.publish(self.path, document(self.takeover(obs)), self.sha, 'second', 2, 'takeover', obs)

    def test_append_rejects_old_definition_without_modifying_run(self):
        for protocol in ('0.6', '0.7', '0.8', '0.9', '0.10'):
            new = appended(self.data)
            new['tasks'][-1]['definition']['protocol'] = protocol
            self.assert_rejected(new, 'append')

    def test_current_flow_acceptance_and_removed_names(self):
        self.assertEqual(guard.normalize_flow('code'), guard.normalize_flow(['code', 'validate', 'fix', 'review']))
        self.assertEqual(guard.normalize_flow('fix')[0], 'fix')
        for value in ('implementation', 'bugfix', 'review-only', 'full', 'feature', 'small-change', ['need', 'code'], ['code', 'design'], [], None):
            with self.subTest(value=value), self.assertRaises(ValueError): guard.normalize_flow(value)


if __name__ == '__main__': unittest.main()

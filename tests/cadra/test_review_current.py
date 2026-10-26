"""Protocol-specific flow and real-file publication tests, not live agents."""
from copy import deepcopy
import json
import subprocess
import sys
import unittest

from . import test_append_agents as append_fixtures
from . import test_run_guard as fixtures
from .model import new_item, prepare
from .model_current import decision
from .test_cadra import contract, closed_call

guard = fixtures.guard


class ReviewFlowTests(unittest.TestCase):
    def test_new_presets_and_default(self):
        for name, stages in (('code', ['code', 'review', 'fix', 'validate']),
                             ('fix', ['fix', 'review', 'validate']),
                             ('review', ['review', 'fix', 'validate'])):
            self.assertEqual(guard.normalize_flow(name), guard.normalize_flow(stages))
        self.assertEqual(guard.normalize_flow(), guard.normalize_flow('code'))
        for protocol in ('0.6', '0.7', '0.8', '0.9', '0.99', None):
            with self.subTest(protocol=protocol), self.assertRaises(ValueError):
                guard.normalize_flow('code', protocol)

    def test_review_fix_rereview_or_direct_validation(self):
        for state in (contract('review', 'fix', 'blocking_findings'),
                      contract('fix', 'review', 'stage_completed'),
                      contract('review', 'validate', 'stage_completed')):
            self.assertEqual(decision(state, 'review', '0.10'), 'call')
            self.assertEqual(decision(state, 'review', '0.10'),
                             decision(state, ['review', 'fix', 'validate'], '0.10'))
        self.assertEqual(decision(contract(), ['review'], '0.10'), 'blocked')
        self.assertEqual(decision(contract('review', 'validate', 'stage_completed'), ['review'], '0.10'), 'completed')

    def test_review_requires_validation_acceptance(self):
        for stage in ('review', 'validate'):
            for acceptance in (None, 'pending', 'blocked', 'failed'):
                state = contract(stage, None, 'task_completed')
                state.update(status='completed', next={'stage': None, 'allowed': False, 'reason': 'task_completed'})
                if acceptance:
                    state['acceptance'] = {'status': acceptance}
                with self.subTest(stage=stage, acceptance=acceptance):
                    self.assertEqual(decision(state, 'review', '0.10'), 'blocked')
        state['acceptance'] = {'status': 'passed'}
        self.assertEqual(decision(state, 'review', '0.10'), 'completed')

    def test_missing_input_permission_or_candidate_blocks_without_advancing(self):
        for reason in ('missing_input', 'missing_permission', 'candidate_unavailable', 'environment_blocked'):
            state = contract('review', None, 'blocked')
            state.update(status='blocked', blocked={'value': True, 'reason': reason},
                         next={'stage': None, 'allowed': False, 'reason': 'blocked'})
            state['stage_result']['status'] = 'blocked'
            self.assertEqual(decision(state, 'review', '0.10'), 'blocked')

    def test_existing_remediation_budget_applies_to_review_preset(self):
        # The legacy budget oracle consumes a normalized list; no new budget rule.
        start, allowed = guard.normalize_flow('review', '0.10')
        configured = [start, *sorted(allowed - {start})]
        item = new_item()
        for _ in range(3):
            self.assertEqual(prepare(item, contract(), configured), 'prepared')
            closed_call(item, contract())
            self.assertEqual(prepare(item, contract('fix', 'review', 'stage_completed'), configured), 'prepared')
            closed_call(item, contract('fix', 'review', 'stage_completed'))
        before = deepcopy(item)
        self.assertEqual(prepare(item, contract(), configured), 'failed')
        self.assertEqual(item, before)


class ReviewRunTests(unittest.TestCase):
    protocol = '0.10'
    configured_flow = 'review'
    setUp = fixtures.RunGuardTests.setUp
    observation = fixtures.RunGuardTests.observation
    takeover = fixtures.RunGuardTests.takeover

    def save(self, mode='update', observation=None):
        owner = self.data['executor']
        self.sha = guard.publish(self.path, fixtures.document(self.data), self.sha,
                                 owner['instance_id'], owner['generation'], mode, observation)

    def stage(self, stage, remediation=0, close=True, next_stage=None):
        task = self.data['tasks'][0]
        role = 'reviewer' if stage == 'review' else 'worker'
        ref = role + '-1'
        if not any(b['id'] == ref for b in task['agents']):
            task['agents'].append(fixtures.binding(role, 'agent-' + role, ref))
            self.save()
        task['state'] = 'running'
        number = len(task['calls']) + 1
        before = deepcopy(task['calls'][-1]['result']['contract']) if task['calls'] else None
        call = dict(id=number, stage=stage, execution_mode='unattended', reason='fixture stage',
                    agent_ref=ref, dispatch_evidence=None, before=before, dispatch='prepared', closed=False,
                    result=None, prepared_at=fixtures.LATER,
                    charged=dict(calls=1, remediation=remediation, retry_stage=None))
        task['calls'].append(call)
        task['budget']['calls'] += 1
        task['budget']['remediation'] += remediation
        task['checkpoint']['pending_call'] = number
        self.save()
        call.update(dispatch='dispatched', dispatch_evidence=dict(
            agent_id='agent-' + role, source='fixture dispatch handle', at=fixtures.LATER))
        self.save()
        if close:
            self.close_pending(next_stage)

    def close_pending(self, next_stage=None):
        task = self.data['tasks'][0]
        call = task['calls'][-1]
        if next_stage is None:
            next_stage = {'review': 'validate', 'fix': 'review', 'validate': None}[call['stage']]
        round_ = sum(c['stage'] == call['stage'] for c in task['calls'])
        state = contract(call['stage'], next_stage,
                         'blocking_findings' if call['stage'] == 'review' and next_stage == 'fix' else 'stage_completed', round_)
        state['task'] = task['slug']
        state['next']['allowed'] = next_stage is not None
        call.update(closed=True, result={'handoff': f"{call['stage']}-{round_:02d}.md", 'contract': state})
        task['checkpoint'].update(pending_call=None, last_delivery=call['result'])
        self.save()

    def test_review_run_persists_native_preset_and_role_handoffs(self):
        self.assertEqual(self.data['tasks'][0]['start_action']['stage'], 'review')
        self.stage('review', next_stage='fix')
        self.assertEqual([b['role'] for b in self.data['tasks'][0]['agents']], ['reviewer'])
        self.stage('fix', remediation=1)
        self.stage('review')
        self.stage('validate')
        task = self.data['tasks'][0]
        task.update(state='completed', result=dict(state='completed', acceptance={'status': 'passed'},
                                                 last_delivery=task['checkpoint']['last_delivery']))
        self.data['status'] = 'completed'
        self.save()
        actual, _ = guard.current(self.path.read_bytes())
        self.assertEqual(actual['tasks'][0]['definition']['flow'], 'review')
        self.assertEqual([c['agent_ref'] for c in actual['tasks'][0]['calls']],
                         ['reviewer-1', 'worker-1', 'reviewer-1', 'worker-1'])

    def test_direct_validation_creates_worker_only_after_review(self):
        self.stage('review')
        self.stage('validate')
        self.assertEqual([c['stage'] for c in self.data['tasks'][0]['calls']], ['review', 'validate'])

    def test_review_calls_cannot_exceed_existing_total_budget(self):
        for _ in range(16):
            self.stage('review')
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'budget limit exceeded'):
            self.stage('review')
        self.assertEqual(self.path.read_bytes(), before)

    def test_review_recovery_keeps_pending_call_snapshot_and_budget(self):
        self.stage('review', close=False)
        self.data['status'] = 'interrupted'
        self.save()
        before = deepcopy(self.data['tasks'])
        obs = self.observation()
        self.data = self.takeover(obs)
        self.save('takeover', obs)
        self.assertEqual(self.data['tasks'], before)
        self.data['status'] = 'running'
        self.close_pending()
        self.stage('validate')
        self.assertEqual(self.data['tasks'][0]['budget']['calls'], 2)
        self.assertEqual(self.data['tasks'][0]['definition']['flow'], 'review')

    def test_inspect_does_not_trust_parent_stop_without_child_stop(self):
        self.stage('review', close=False)
        obs = self.observation()
        obs['children'][0]['state'] = 'active'
        path = self.root / 'observation.json'
        path.write_text(json.dumps(obs))
        before = self.path.read_bytes()
        result = subprocess.run([sys.executable, '-B', str(fixtures.SCRIPT), 'inspect', '--run', str(self.path),
                                 '--observation', str(path)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['activity'], 'unknown')
        self.assertEqual(self.path.read_bytes(), before)


    def test_draft_definition_cannot_bypass_new_gate(self):
        original = self.path.read_bytes()
        changed = deepcopy(self.data)
        changed['tasks'][0]['definition']['preparation'] = 'draft'
        with self.assertRaisesRegex(ValueError, 'definition must have passed Ready Gate'):
            guard.publish(self.path, fixtures.document(changed), self.sha, 'first', 1)
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()

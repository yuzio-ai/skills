"""Stop, budget and delivery regressions through actual atomic Run writes."""
from copy import deepcopy
import unittest

from . import test_run_guard as fixtures
from .model_current import result_valid
from .test_cadra import contract

guard = fixtures.guard


def delivery(stage, next_stage=None, reason='stage_completed', round_=1, failed=False):
    state = contract(stage, next_stage, reason, round_)
    state['task'] = 'camera'
    state['next']['allowed'] = next_stage is not None
    if failed:
        state['stage_result']['status'] = 'failed'
    return state


class GuardSafetyTests(unittest.TestCase):
    setUp = fixtures.RunGuardTests.setUp

    def save(self):
        self.sha = guard.publish(self.path, fixtures.document(self.data), self.sha, 'first', 1)

    def reload(self):
        self.data, _ = guard.current(self.path.read_bytes())

    def start(self, stage, before=None, remediation=0, retry_stage=None):
        task = self.data['tasks'][0]
        role = 'reviewer' if stage == 'review' else 'worker'
        ref = role + '-1'
        if not any(b['id'] == ref for b in task['agents']):
            task['agents'].append(fixtures.binding(role, 'agent-' + role, ref))
            self.save()
        task['state'] = 'running'
        number = len(task['calls']) + 1
        task['calls'].append(dict(
            id=number, stage=stage, reason='audit regression', execution_mode='unattended',
            agent_ref=ref, before=deepcopy(before), dispatch='prepared', dispatch_evidence=None,
            prepared_at=fixtures.AT, closed=False, result=None,
            charged=dict(calls=1, remediation=remediation, retry_stage=retry_stage)))
        task['budget']['calls'] += 1
        task['budget']['remediation'] += remediation
        if retry_stage is not None:
            retries = task['budget']['retries']
            retries[retry_stage] = retries.get(retry_stage, 0) + 1
        task['checkpoint']['pending_call'] = number
        self.save()

    def dispatch(self):
        call = self.data['tasks'][0]['calls'][-1]
        role = 'reviewer' if call['stage'] == 'review' else 'worker'
        call.update(dispatch='dispatched', dispatch_evidence=dict(
            agent_id='agent-' + role, at=fixtures.AT, source='synthetic dispatch fixture'))
        self.save()

    def close(self, state, wrapped=True):
        task = self.data['tasks'][0]
        call = task['calls'][-1]
        result = {'contract': deepcopy(state), 'handoff': 'fixture.md'} if wrapped else deepcopy(state)
        call.update(closed=True, result=result)
        task['checkpoint'].update(pending_call=None, last_delivery=deepcopy(call['result']))
        self.save()

    def assert_rejected(self, message):
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, message):
            self.save()
        self.assertEqual(self.path.read_bytes(), raw)
        self.reload()

    def test_started_tasks_cannot_be_skipped_at_any_call_boundary(self):
        self.start('code')
        for boundary in ('prepared', 'dispatched', 'closed'):
            if boundary == 'dispatched':
                self.dispatch()
            if boundary == 'closed':
                self.close(delivery('code', 'review'))
            self.data['tasks'][0].update(state='skipped', result={'state': 'skipped'})
            self.data['status'] = 'stopped'
            with self.subTest(boundary=boundary):
                self.assert_rejected('skipped task cannot contain execution evidence')

    def test_running_without_calls_cannot_be_skipped(self):
        self.data['tasks'][0]['state'] = 'running'
        self.save()
        self.data['tasks'][0].update(state='skipped', result={'state': 'skipped'})
        self.assert_rejected('only queued task may become skipped')

    def test_queued_skip_preserves_binding_and_allows_next_run(self):
        task = self.data['tasks'][0]
        task['agents'].append(fixtures.binding())
        self.save()
        task.update(state='skipped', result={'state': 'skipped', 'reason': 'queue stopped'})
        self.data['status'] = 'stopped'
        self.save()
        self.assertFalse(guard.unfinished(self.data))
        new = fixtures.example()
        new['run_id'] = 'run-20261025-02'
        guard.publish(self.path.with_name(new['run_id'] + '.md'), fixtures.document(new), None, 'first', 1, 'create')

    def test_skipped_requires_no_authorization_or_delivery_evidence(self):
        for field in ('authorization', 'checkpoint', 'result'):
            self.reload()
            task = self.data['tasks'][0]
            task.update(state='skipped', result={'state': 'skipped'})
            if field == 'authorization':
                task['authorization_consumed'] = True
            elif field == 'checkpoint':
                task['checkpoint']['last_delivery'] = {'stage': 'code'}
            else:
                task['result']['last_delivery'] = {'stage': 'code'}
            with self.subTest(field=field):
                self.assert_rejected('skipped task cannot contain execution evidence')

    def test_invalid_skipped_history_blocks_inspect_and_new_run(self):
        self.start('code')
        bad = deepcopy(self.data)
        bad['tasks'][0].update(state='skipped', result={'state': 'skipped'})
        bad['status'] = 'stopped'
        raw = fixtures.document(bad)
        self.path.write_bytes(raw)  # Simulate an already malformed historical record.
        with self.assertRaisesRegex(ValueError, 'skipped task cannot contain execution evidence'):
            guard.current(raw)
        new = fixtures.example()
        new['run_id'] = 'run-20261025-02'
        target = self.path.with_name(new['run_id'] + '.md')
        with self.assertRaisesRegex(ValueError, 'skipped task cannot contain execution evidence'):
            guard.publish(target, fixtures.document(new), None, 'first', 1, 'create')
        self.assertFalse(target.exists())
        self.assertEqual(self.path.read_bytes(), raw)

    def test_failed_may_preserve_pending_call_for_recovery(self):
        self.start('code')
        task = self.data['tasks'][0]
        task.update(state='failed', result={'state': 'failed', 'reason': 'unconfirmed delivery'})
        self.data['status'] = 'stopped'
        self.save()
        self.reload()
        self.assertEqual(self.data['tasks'][0]['checkpoint']['pending_call'], 1)
        self.assertFalse(self.data['tasks'][0]['calls'][0]['closed'])

    def test_invalid_retry_labels_and_false_retry_charges_rejected(self):
        # Bind first so a rejection is compared to the exact pre-intent bytes.
        self.data['tasks'][0]['agents'].append(fixtures.binding(agent_id='agent-worker'))
        self.save()
        raw = self.path.read_bytes()
        for retry_stage in ('made-up-stage', 'review', '', False, 0, 'code'):
            self.reload()
            with self.subTest(retry_stage=retry_stage), self.assertRaises(ValueError):
                self.start('code', retry_stage=retry_stage)
            self.assertEqual(self.path.read_bytes(), raw)

    def test_blocking_findings_fix_cannot_be_undercharged(self):
        self.start('review')
        before = delivery('review', 'fix', 'blocking_findings')
        self.close(before)
        self.data['tasks'][0]['agents'].append(fixtures.binding(agent_id='agent-worker'))
        self.save()
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'budget charge disagrees with call basis'):
            self.start('fix', before=before)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_followup_cannot_hide_the_prior_budget_basis(self):
        self.start('review')
        before = delivery('review', 'fix', 'blocking_findings')
        self.close(before)
        self.data['tasks'][0]['agents'].append(fixtures.binding(agent_id='agent-worker'))
        self.save()
        raw = self.path.read_bytes()
        changed = deepcopy(before)
        changed['next']['reason'] = 'stage_completed'
        for basis in (None, changed):
            self.reload()
            with self.subTest(basis=basis), self.assertRaisesRegex(ValueError, 'before contract'):
                self.start('fix', before=basis)
            self.assertEqual(self.path.read_bytes(), raw)

    def test_direct_contract_preserves_prior_budget_basis(self):
        self.start('review')
        before = delivery('review', 'fix', 'blocking_findings')
        self.close(before, wrapped=False)
        self.data['tasks'][0]['agents'].append(fixtures.binding(agent_id='agent-worker'))
        self.save()
        raw = self.path.read_bytes()
        changed = deepcopy(before)
        changed['next']['reason'] = 'stage_completed'
        with self.assertRaisesRegex(ValueError, 'before contract'):
            self.start('fix', before=changed, remediation=0)
        self.assertEqual(self.path.read_bytes(), raw)
        self.reload()
        self.start('fix', before=before, remediation=1)

    def test_direct_contract_preserves_round_across_fix(self):
        self.start('review')
        review = delivery('review', 'fix', 'blocking_findings')
        self.close(review, wrapped=False)
        self.start('fix', before=review, remediation=1)
        fix = delivery('fix', 'review')
        self.close(fix, wrapped=False)
        self.start('review', before=fix)
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'delivery round must advance'):
            self.close(review, wrapped=False)
        self.assertEqual(self.path.read_bytes(), raw)
        self.reload()
        self.close(delivery('review', 'validate', round_=2), wrapped=False)

    def test_three_remediations_allow_rereview_but_block_fourth_fix(self):
        before = None
        for round_ in range(1, 4):
            self.start('review', before=before)
            before = delivery('review', 'fix', 'blocking_findings', round_)
            self.close(before)
            self.start('fix', before=before, remediation=1)
            before = delivery('fix', 'review', round_=round_)
            self.close(before)
        self.start('review', before=before)
        before = delivery('review', 'fix', 'blocking_findings', 4)
        self.close(before)
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'budget limit exceeded'):
            self.start('fix', before=before, remediation=1)
        self.assertEqual(self.path.read_bytes(), raw)
        self.reload()
        self.assertEqual(self.data['tasks'][0]['budget']['remediation'], 3)

    def test_acceptance_failure_fix_is_not_review_remediation(self):
        before = delivery('validate', 'fix', 'acceptance_failed', 8)
        self.start('fix', before=before)
        self.close(delivery('fix', 'review', round_=1))
        self.assertEqual(self.data['tasks'][0]['budget']['remediation'], 0)

    def test_failed_stage_retry_cannot_be_undercharged_or_exceed_two(self):
        before = delivery('code', 'code', 'stage_failed', failed=True)
        self.data['tasks'][0]['agents'].append(fixtures.binding(agent_id='agent-worker'))
        self.save()
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'budget charge disagrees with call basis'):
            self.start('code', before=before)
        self.assertEqual(self.path.read_bytes(), raw)
        self.reload()
        for round_ in (2, 3):
            self.start('code', before=before, retry_stage='code')
            before = delivery('code', 'code', 'stage_failed', round_, failed=True)
            self.close(before)
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'budget limit exceeded'):
            self.start('code', before=before, retry_stage='code')
        self.assertEqual(self.path.read_bytes(), raw)

    def test_revision_restart_does_not_consume_old_next_budget(self):
        # Modify the fresh fixture before create to model a newly admitted Run.
        self.path.unlink()
        task = self.data['tasks'][0]
        task['definition'].update(flow='fix', changed_fields=['requirement'])
        task['start_action'] = {'stage': 'fix', 'source': 'admitted definition restart'}
        self.sha = guard.publish(self.path, fixtures.document(self.data), None, 'first', 1, 'create')
        task['agents'].append(fixtures.binding(agent_id='agent-worker'))
        self.save()
        task['authorization_consumed'] = True
        self.start('fix', before=delivery('review', 'fix', 'blocking_findings'))
        self.assertEqual(self.data['tasks'][0]['budget']['remediation'], 0)

    def test_first_call_budget_exception_requires_frozen_revision_evidence(self):
        for missing in ('authorization', 'changed_fields', 'start'):
            self.path.unlink()
            self.data = fixtures.example(flow='fix')
            task = self.data['tasks'][0]
            if missing != 'changed_fields':
                task['definition']['changed_fields'] = ['requirement']
            if missing == 'start':
                task['start_action']['stage'] = 'review'
            self.sha = guard.publish(self.path, fixtures.document(self.data), None, 'first', 1, 'create')
            task['agents'].append(fixtures.binding(agent_id='agent-worker'))
            self.save()
            task['authorization_consumed'] = missing != 'authorization'
            raw = self.path.read_bytes()
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, 'budget charge disagrees'):
                self.start('fix', before=delivery('review', 'fix', 'blocking_findings'))
            self.assertEqual(self.path.read_bytes(), raw)

    def test_restart_label_cannot_waive_later_remediation(self):
        self.path.unlink()
        task = self.data['tasks'][0]
        task['definition'].update(flow='fix', changed_fields=['flow'])
        task['start_action'] = {'kind': 'revision_restart', 'stage': 'fix'}
        self.sha = guard.publish(self.path, fixtures.document(self.data), None, 'first', 1, 'create')
        task['agents'].append(fixtures.binding(agent_id='agent-worker'))
        self.save()
        task['authorization_consumed'] = True
        self.start('fix', before=delivery('review', 'fix', 'blocking_findings'))
        before = delivery('fix', 'review')
        self.close(before)
        self.start('review', before=before)
        before = delivery('review', 'fix', 'blocking_findings', 2)
        self.close(before)
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'budget charge disagrees with call basis'):
            self.start('fix', before=before)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_cross_stage_old_review_result_rejected_but_next_round_passes(self):
        self.start('review')
        before = delivery('review', 'fix', 'blocking_findings')
        self.close(before)
        self.start('fix', before=before, remediation=1)
        before = delivery('fix', 'review')
        self.close(before)
        self.start('review', before=before)
        self.dispatch()
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'delivery round must advance its own stage'):
            self.close(delivery('review', 'validate', round_=1))
        self.assertEqual(self.path.read_bytes(), raw)
        self.reload()
        self.close(delivery('review', 'validate', round_=2))

    def test_revalidation_after_fix_and_review_requires_a_new_validate_round(self):
        self.start('validate')
        before = delivery('validate', 'fix', 'acceptance_failed')
        before['acceptance'] = {'status': 'failed'}
        self.close(before)
        self.start('fix', before=before)
        before = delivery('fix', 'review')
        self.close(before)
        self.start('review', before=before)
        before = delivery('review', 'validate')
        self.close(before)
        self.start('validate', before=before)
        self.dispatch()
        passed = delivery('validate', reason='task_completed')
        passed.update(status='completed', acceptance={'status': 'passed'})
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'delivery round must advance its own stage'):
            self.close(passed)
        self.assertEqual(self.path.read_bytes(), raw)
        self.reload()
        passed['stage_result']['round'] = 2
        self.close(passed)


class CurrentRoundOracleTests(unittest.TestCase):
    def test_cross_stage_rereview_and_revalidation_use_target_stage_history(self):
        for target, intermediate in (('review', 'fix'), ('validate', 'fix')):
            with self.subTest(target=target):
                history = [contract(target, round_=8)]
                before = contract(intermediate, round_=1)
                self.assertFalse(result_valid(contract(target, round_=8), target, before, history=history))
                self.assertTrue(result_valid(contract(target, round_=9), target, before, history=history))

    def test_resume_and_cross_run_admission_can_supply_prior_delivery_history(self):
        # Prior Run history comes from explicit source-chain verification, not
        # from round numbers of another stage or the new Run's call IDs.
        old = contract('review', round_=2)
        before = contract('fix', round_=20)
        self.assertFalse(result_valid(old, 'review', before, history=[old]))
        self.assertTrue(result_valid(contract('review', round_=3), 'review', before, history=[old]))
        self.assertFalse(result_valid(contract('review', round_=3), 'review', before,
                                      synced=False, history=[old]))


if __name__ == '__main__':
    unittest.main()

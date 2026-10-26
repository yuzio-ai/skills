"""Current contract scenarios alongside preserved historical regression cases."""
import unittest
from .model_v08 import decision
from .test_cadra import contract


class CurrentFlowTests(unittest.TestCase):
    def test_adopt_completed_code_or_fix_without_review_is_blocked(self):
        # Legal standalone endpoints do not establish Cadra's required review.
        # This also covers recovery closeout through the same terminal mapping.
        for stage in ('code', 'fix'):
            for flow in ([stage, 'review'], [stage], 'review-only', 'implementation', 'bugfix'):
                for acceptance in (None, 'pending', 'blocked', 'failed', 'passed'):
                    state = contract(stage, None, 'task_completed')
                    state['status'] = 'completed'
                    state['next']['allowed'] = False
                    state['candidate']['snapshot'] = 'fixed-candidate'
                    if acceptance is not None:
                        state['acceptance'] = {'status': acceptance}
                    with self.subTest(stage=stage, flow=flow, acceptance=acceptance):
                        self.assertEqual(decision(state, flow), 'blocked')
                        self.assertEqual(state['status'], 'completed')
                        self.assertEqual(state['next'], {
                            'stage': None, 'allowed': False, 'reason': 'task_completed'})

    def test_existing_review_and_validation_endpoints_remain_usable(self):
        # Source identity, candidate and independent review evidence are checked
        # by the caller; the model exercises the resulting control contract.
        reviewed = contract('review', None, 'task_completed')
        reviewed['status'] = 'completed'
        reviewed['next']['allowed'] = False
        self.assertEqual(decision(reviewed, 'review-only'), 'completed')
        self.assertEqual(decision(reviewed, ['code', 'review']), 'completed')
        self.assertEqual(decision(reviewed, 'implementation'), 'blocked')
        validated = contract('validate', None, 'task_completed')
        validated['status'] = 'completed'
        validated['next']['allowed'] = False
        validated['acceptance'] = {'status': 'passed'}
        self.assertEqual(decision(validated), 'completed')

    def test_published_review_after_old_code_endpoint_can_continue(self):
        # A separate, authorized Cohestra review publishes this new contract;
        # Cadra must consume its next, not manufacture one from the old endpoint.
        for stage, reason, expected in (
                ('fix', 'blocking_findings', 'call'),
                ('validate', 'stage_completed', 'call')):
            reviewed = contract('review', stage, reason)
            self.assertEqual(decision(reviewed), expected)

    def test_invalid_or_failed_delivery_precedes_review_closeout_guard(self):
        state = contract('code', None, 'task_completed')
        state['status'] = 'completed'
        state['next']['allowed'] = False
        state['execution_mode'] = 'invalid'
        self.assertEqual(decision(state, ['code', 'review']), 'failed')
        state['execution_mode'] = 'unattended'
        state['status'] = 'failed'
        self.assertEqual(decision(state, ['code', 'review']), 'failed')

    def test_implementation_review_fix_rereview_validate(self):
        for state in (contract('code', 'review', 'stage_completed'),
                      contract('review', 'fix', 'blocking_findings'),
                      contract('fix', 'review', 'stage_completed'),
                      contract('review', 'validate', 'stage_completed')):
            self.assertEqual(decision(state), 'call')
        passed = contract('validate', None, 'task_completed')
        passed['status'] = 'completed'
        passed['next']['allowed'] = False
        passed['acceptance'] = {'status': 'passed'}
        self.assertEqual(decision(passed), 'completed')

    def test_human_stages_never_become_normal_boundary_completion(self):
        for stage in ('need', 'design'):
            for reason in ('stage_completed', 'acceptance_failed'):
                state = contract('validate', stage, reason)
                self.assertEqual(decision(state), 'blocked')
                state['status'] = 'completed'
                state['acceptance'] = {'status': 'passed'}
                self.assertEqual(decision(state), 'blocked')

    def test_explicit_list_cannot_waive_required_review(self):
        self.assertEqual(decision(contract('code', 'review', 'stage_completed'), ['code']), 'blocked')
        self.assertEqual(decision(contract('fix', 'review', 'stage_completed'), ['fix', 'validate']), 'blocked')

    def test_bugfix_and_review_only_do_not_expand_allowed_scope(self):
        self.assertEqual(decision(contract('fix', 'review', 'stage_completed'), 'bugfix'), 'call')
        self.assertEqual(decision(contract('review', 'fix', 'blocking_findings'), 'review-only'), 'blocked')
        self.assertEqual(decision(contract('review', 'validate', 'stage_completed'), 'review-only'), 'completed')

    def test_removed_presets_rejected_without_reinterpreting_history(self):
        for name in ('small-change', 'full', 'feature'):
            with self.subTest(name=name), self.assertRaises(ValueError): decision(contract(), name)


if __name__ == '__main__': unittest.main()

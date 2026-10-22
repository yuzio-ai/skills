"""Behavioral invariants for the test-only v0.6 model, not agent execution."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from . import model

from .model import (PRESETS, chain, decision, execution_basis, flow,
                            new_item, prepare, recover_call, result_valid,
                            status, unfinished, revision_action, revision_fields)


def task(revision=1, preparation='ready'):
    return {'protocol': '0.6', 'slug': 'a', 'revision': revision,
            'preparation': preparation, 'definition': {'requirement': f'R{revision}'}}


def run(key='r1', previous=None, revision=1, state='completed', run_state='completed'):
    return {'protocol': '0.6', 'run_id': key, 'status': run_state,
            'tasks': [{'slug': 'a', 'revision': revision, 'previous_run': previous,
                       'definition': task(revision)['definition'], 'state': state,
                       'calls': [{'id': 1, 'stage': 'code', 'dispatch': 'dispatched'}]
                       if state in {'completed', 'failed', 'blocked'} else [],
                       'authorization_consumed': False,
                       'result': {'state': state} if state in {'completed', 'failed', 'blocked', 'skipped'} else None}]}


def contract(stage='review', next_stage='fix', reason='blocking_findings', round_=1):
    return {'contract': '0.8', 'task': 'a', 'execution_mode': 'unattended',
            'status': 'in_progress', 'stage_result': {'stage': stage, 'status': 'completed', 'round': round_},
            'candidate': {'commit': None, 'snapshot': None},
            'next': {'stage': next_stage, 'allowed': True, 'reason': reason},
            'blocked': {'value': False, 'reason': None}}


def closed_call(item, state):
    call = item['calls'][-1]
    live = deepcopy(state)
    live['stage_result'] = {'stage': call['stage'], 'status': 'completed', 'round': len(item['calls']) + 1}
    assert recover_call(item, live, 'complete') == 'closed'


class FlowTests(unittest.TestCase):
    def test_changed_start_is_a_flow_revision(self):
        before, after = ['code', 'review'], ['review', 'code']
        self.assertNotEqual(flow(before), flow(after))
        self.assertEqual(flow(before)[1], flow(after)[1])
        current = task(2)
        current['changed_fields'] = ['flow'] if flow(before) != flow(after) else []
        self.assertEqual(revision_action(current, [run()]), 'start')
        self.assertEqual(flow(after)[0], 'review')

    def test_presets_equal_lists(self):
        for name, values in PRESETS.items():
            with self.subTest(name=name): self.assertEqual(flow(name), flow(values))

    def test_non_initial_order_is_not_execution_order(self):
        self.assertEqual(flow('small-change'), flow(['code', 'validate', 'fix', 'review']))

    def test_duplicate_review_has_no_extra_semantics(self):
        self.assertEqual(flow(['review', 'fix', 'review']), flow(['review', 'fix']))

    def test_invalid_empty_or_unknown_rejected(self):
        for value in ([], 'unknown', ['code', 'deploy'], None, ['code', 3]):
            with self.subTest(value=value), self.assertRaises(ValueError): flow(value)

    def test_normal_range_boundary(self):
        self.assertEqual(decision(contract('review', 'validate', 'stage_completed'), 'review-only'), 'completed')

    def test_required_fix_outside_range(self):
        self.assertEqual(decision(contract(), 'review-only'), 'blocked')

    def test_required_rereview_outside_range(self):
        self.assertEqual(decision(contract('fix', 'review', 'stage_completed'), ['fix', 'validate']), 'blocked')

    def test_pending_validation_outside_range(self):
        state = contract('validate', 'validate', 'stage_completed')
        state['acceptance'] = {'status': 'pending'}
        self.assertEqual(decision(state, ['review']), 'blocked')


class ProvenanceTests(unittest.TestCase):
    def test_no_run_uses_preparation(self):
        self.assertEqual(status(task(preparation='draft'), []), 'draft')

    def test_active_run_owns_state(self):
        self.assertEqual(status(task(), [run(state='running', run_state='running')]), 'running')

    def test_terminal_is_not_overwritten_by_preparation(self):
        self.assertEqual(status(task(preparation='draft'), [run()]), 'completed')

    def test_old_success_does_not_complete_new_definition(self):
        self.assertEqual(status(task(2, 'draft'), [run()]), 'draft')

    def test_explicit_chain_not_id_order_selects_current(self):
        records = [run('z', state='failed'), run('a', 'z')]
        self.assertEqual(status(task(), list(reversed(records))), 'completed')
        self.assertEqual(records[0]['tasks'][0]['result']['state'], 'failed')

    def test_missing_predecessor(self):
        with self.assertRaises(ValueError): status(task(), [run(previous='missing')])

    def test_fork(self):
        with self.assertRaises(ValueError): status(task(), [run(), run('r2', 'r1'), run('r3', 'r1')])

    def test_cycle(self):
        with self.assertRaises(ValueError): chain('a', [run('r1', 'r2'), run('r2', 'r1')])

    def test_duplicate_slug(self):
        record = run(); record['tasks'].append(deepcopy(record['tasks'][0]))
        with self.assertRaises(ValueError): unfinished(record)

    def test_multiple_unfinished_runs(self):
        with self.assertRaises(ValueError): chain('a', [run(run_state='running'), run('r2', 'r1', run_state='running')])

    def test_active_definition_cannot_change(self):
        with self.assertRaises(ValueError): status(task(2), [run(state='queued', run_state='running')])

    def test_same_revision_active_snapshot_mismatch(self):
        definition = task(); definition['definition']['requirement'] = 'external edit'
        with self.assertRaises(ValueError): status(definition, [run(state='queued', run_state='running')])

    def test_revision_regression(self):
        with self.assertRaises(ValueError): chain('a', [run(revision=2), run('r2', 'r1', revision=1)])

    def test_future_revision(self):
        with self.assertRaises(ValueError): status(task(), [run(revision=2)])

    def test_missing_result_does_not_release_run(self):
        record = run(); record['tasks'][0]['result'] = None
        with self.assertRaises(ValueError): unfinished(record)

    def test_completed_with_pending_item_rejected(self):
        with self.assertRaises(ValueError): unfinished(run(state='queued'))

    def test_stopped_with_pending_item_is_unfinished(self):
        self.assertTrue(unfinished(run(state='queued', run_state='stopped')))

    def test_skipped_uses_preparation_but_keeps_recovery_basis(self):
        records = [run(state='failed'), run('r2', 'r1', state='skipped', run_state='stopped')]
        self.assertEqual(status(task(), records), 'ready')
        self.assertEqual(execution_basis('a', records)['state'], 'failed')
        self.assertEqual(status(task(preparation='draft'), records), 'draft')

    def test_only_skipped_has_no_execution_basis(self):
        self.assertIsNone(execution_basis('a', [run(state='skipped', run_state='stopped')]))

    def test_old_protocol_is_not_adopted(self):
        record = run(); record['protocol'] = '0.5'
        with self.assertRaises(ValueError): status(task(), [record])


class RevisionTests(unittest.TestCase):
    def test_pre_call_blocked_revision_keeps_requirement_change(self):
        evidence = Path(__file__).parent / 'fixtures/pre-call-blocked-revision.json'
        case = json.loads(evidence.read_text())
        # The R1 fixture omits call details; provide its completed call.
        case['records'][0]['tasks'][0].update(
            calls=run()['tasks'][0]['calls'], authorization_consumed=True)
        self.assertEqual(execution_basis('a', case['records'])['revision'], 1)
        self.assertEqual(revision_fields(case['current'], case['records']), {'requirement', 'execution_policy'})
        self.assertEqual(revision_action(case['current'], case['records']), 'start')
        self.assertEqual(revision_action(case['current'], case['records'], False), 'reject')

    def test_multiple_unconsumed_revisions_preserve_changes_and_block(self):
        records = [run()]
        for revision, state, field in [(2, 'blocked', 'requirement'), (3, 'failed', 'flow'), (4, 'skipped', 'dependencies')]:
            record = run(f'r{revision}', f'r{revision - 1}', revision, state)
            item = record['tasks'][0]
            item.update(calls=[], authorization_consumed=False)
            item['definition']['changed_fields'] = [field]
            records.append(record)
        current = task(5); current['changed_fields'] = ['execution_policy']
        self.assertEqual(revision_fields(current, records), {'requirement', 'flow', 'dependencies', 'execution_policy'})
        self.assertEqual(revision_action(current, records), 'start')
        self.assertEqual(revision_action(current, records, False), 'reject')

    def test_first_task_blocked_before_call_has_no_execution_basis(self):
        record = run(state='blocked')
        record['tasks'][0].update(calls=[], authorization_consumed=False)
        self.assertIsNone(execution_basis('a', [record]))
        self.assertEqual(revision_action(task(2), [record], False), 'reject')
        self.assertEqual(revision_action(task(2), [record]), 'check_first_or_adopt')

    def test_prepared_call_is_not_treated_as_unconsumed(self):
        record = run(revision=2, state='failed')
        record['tasks'][0]['calls'][0]['dispatch'] = 'prepared'
        record['tasks'][0]['definition']['changed_fields'] = ['requirement']
        current = task(3); current['changed_fields'] = ['execution_policy']
        self.assertEqual(execution_basis('a', [record])['revision'], 2)
        self.assertEqual(revision_action(current, [record]), 'check_recovery')

    def test_valid_no_call_closeout_is_execution_basis(self):
        original = run(revision=2)
        original['tasks'][0]['definition']['changed_fields'] = ['requirement']
        record = run('r2', 'r1', revision=3)
        record['tasks'][0]['calls'] = []
        record['tasks'][0]['result']['last_delivery'] = {'source': 'validate-01.md'}
        record['tasks'][0]['definition'].update(requirement='R2', changed_fields=['execution_policy'])
        current = task(4); current['changed_fields'] = ['execution_policy']
        current['definition']['requirement'] = 'R2'
        for consumed in (False, True):
            record['tasks'][0]['authorization_consumed'] = consumed
            with self.subTest(consumed=consumed):
                self.assertEqual(execution_basis('a', [original, record])['revision'], 3)
                self.assertEqual(revision_action(current, [original, record]), 'verify_only')

    def test_ordinary_call_failure_then_policy_revision(self):
        item = new_item()
        prepare(item, contract('code', 'review', 'stage_completed'), 'small-change')
        self.assertFalse(item['authorization_consumed'])
        recover_call(item, None, 'unknown')
        item.update(slug='a', revision=1, previous_run=None, definition={'requirement': 'R1'})
        record = run(); record['tasks'] = [item]
        current = task(2); current['definition']['requirement'] = 'R1'
        current['changed_fields'] = ['execution_policy']
        self.assertEqual(revision_action(current, [record]), 'check_recovery')
        self.assertEqual(revision_action(current, [record], False), 'reject')
        self.assertEqual(item['budget']['calls'], 1)
        self.assertFalse(item['calls'][0]['closed'])

    def test_missing_consumption_evidence_does_not_mean_unstarted(self):
        for fields in ({'calls': None}, {'authorization_consumed': None},
                       {'calls': [], 'authorization_consumed': True}):
            record = run(state='blocked')
            record['tasks'][0].update(fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                execution_basis('a', [record])

    def test_requirement_change_restarts(self):
        current = task(2); current['changed_fields'] = ['requirement']
        self.assertEqual(revision_action(current, [run()]), 'start')

    def test_policy_only_completed_closes_without_call(self):
        current = task(2); current['changed_fields'] = ['execution_policy']
        self.assertEqual(revision_action(current, [run()]), 'verify_only')

    def test_policy_only_failure_needs_recovery(self):
        current = task(2); current['changed_fields'] = ['execution_policy']
        self.assertEqual(revision_action(current, [run(state='failed')]), 'check_recovery')

    def test_edit_cannot_bypass_unresolved_block(self):
        current = task(2); current['changed_fields'] = ['requirement']
        self.assertEqual(revision_action(current, [run(state='blocked')], False), 'reject')

    def test_changes_across_skipped_revision_are_cumulative(self):
        records = [run(), run('r2', 'r1', revision=2, state='skipped', run_state='stopped')]
        records[1]['tasks'][0]['definition']['changed_fields'] = ['requirement']
        current = task(3); current['changed_fields'] = ['execution_policy']
        self.assertEqual(revision_fields(current, records), {'requirement', 'execution_policy'})
        self.assertEqual(revision_action(current, records), 'start')

    def test_unexecuted_skipped_revision_rechecks_first_or_adopt(self):
        current = task(2); current['changed_fields'] = ['requirement']
        self.assertEqual(revision_action(current, [run(state='skipped', run_state='stopped')]), 'check_first_or_adopt')


class ContractTests(unittest.TestCase):
    def test_malformed_candidate_cannot_close_or_complete(self):
        for candidate in (['commit', 'snapshot'], {'commit': 12, 'snapshot': None},
                          {'commit': None, 'snapshot': {'path': 'code.md'}}, None, {}):
            item = new_item(); prepare(item, contract('code', 'review', 'stage_completed'), 'full')
            live = contract('review', None, 'task_completed')
            live.update(status='completed', candidate=candidate, acceptance={'status': 'passed'})
            live['next']['allowed'] = False
            with self.subTest(candidate=candidate):
                self.assertEqual(decision(live, 'full'), 'failed')
                self.assertEqual(recover_call(item, live, 'complete'), 'failed')
                self.assertFalse(item['calls'][0]['closed'])
                self.assertEqual(item['budget']['calls'], 1)

    def test_valid_candidate_sources_remain_accepted(self):
        for candidate in ({'commit': None, 'snapshot': None},
                          {'commit': 'a' * 40, 'snapshot': None},
                          {'commit': None, 'snapshot': 'code-01.md'}):
            live = contract(); live['candidate'] = candidate
            with self.subTest(candidate=candidate): self.assertTrue(result_valid(live))

    def test_invalid_control_enums_never_complete(self):
        for field, leaf in [('next', 'reason'), ('acceptance', 'status'), ('blocked', 'reason')]:
            for invalid in ('NOT_VALID', [], {}, 42, False):
                state = contract('review', 'validate', 'stage_completed')
                state['status'] = 'completed'
                state['next'].update(allowed=False, stage=None, reason='task_completed')
                state.setdefault(field, {})[leaf] = invalid
                if field == 'blocked': state['blocked']['value'] = True
                with self.subTest(field=field, invalid=invalid):
                    self.assertFalse(result_valid(state))
                    self.assertEqual(decision(state, 'review-only'), 'failed')

    def test_acceptance_optional_but_present_value_must_be_valid(self):
        state = contract('review', 'validate', 'stage_completed')
        state['status'] = 'completed'
        state['next'].update(allowed=False, stage=None, reason='task_completed')
        self.assertEqual(decision(state, 'review-only'), 'completed')
        for value, expected in [(None, 'completed'), ({'status': 'passed'}, 'completed'),
                                ({'status': 'failed'}, 'blocked'), ({'status': 'pending'}, 'completed'),
                                ({'status': 'blocked'}, 'completed'), ({}, 'failed'),
                                ({'status': None}, 'failed'), ('passed', 'failed'), ([], 'failed')]:
            state['acceptance'] = value
            with self.subTest(value=value): self.assertEqual(decision(state, 'review-only'), expected)

    def test_invalid_result_cannot_close_call_or_trigger_next(self):
        item = new_item(); prepare(item, contract('code', 'review', 'stage_completed'), 'full')
        live = contract('review', 'validate', 'NOT_VALID')
        self.assertEqual(recover_call(item, live, 'complete'), 'failed')
        self.assertFalse(item['calls'][0]['closed'])
        self.assertEqual(item['budget']['calls'], 1)
        fresh = new_item(); saved = deepcopy(fresh)
        self.assertEqual(prepare(fresh, live, 'full'), 'failed')
        self.assertEqual(fresh, saved)

    def test_disallowed_next_requires_null_stage(self):
        state = contract(); state['next']['allowed'] = False
        self.assertEqual(decision(state, 'full'), 'failed')
        state['next']['stage'] = None
        self.assertEqual(decision(state, 'full'), 'blocked')

    def test_same_stage_round_must_increase(self):
        before = contract()
        self.assertFalse(result_valid(before, 'review', before))
        after = contract(round_=2)
        self.assertTrue(result_valid(after, 'review', before))

    def test_cross_stage_rounds_are_independent(self):
        self.assertTrue(result_valid(contract('fix', round_=1), 'fix', contract(round_=8)))

    def test_wrong_mode_task_or_stage(self):
        for field, value in (('execution_mode', 'attended'), ('task', 'b'), ('contract', '0.7')):
            state = contract(); state[field] = value
            with self.subTest(field=field): self.assertFalse(result_valid(state, 'review'))
        self.assertFalse(result_valid(contract('fix'), 'review'))

    def test_sync_failure_rejects_new_result(self):
        self.assertFalse(result_valid(contract(round_=2), 'review', contract(), synced=False))

    def test_malformed_completed_is_failed(self):
        state = contract(); state['status'] = 'completed'; state['next']['stage'] = None
        self.assertEqual(decision(state, 'full'), 'failed')

    def test_acceptance_required_when_validate_allowed(self):
        state = contract(); state['status'] = 'completed'; state['next'].update(allowed=False, stage=None)
        self.assertEqual(decision(state, 'full'), 'blocked')
        self.assertEqual(decision(state, 'review-only'), 'completed')
        state['acceptance'] = {'status': 'failed'}
        self.assertEqual(decision(state, 'review-only'), 'blocked')


class BudgetTests(unittest.TestCase):
    def test_identical_failed_results_use_two_retries(self):
        item = new_item(); state = contract('code', 'code', 'stage_failed'); state['stage_result']['status'] = 'failed'
        for _ in range(2):
            self.assertEqual(prepare(item, state, 'small-change'), 'prepared')
            closed_call(item, state)
        self.assertEqual(prepare(item, state, 'small-change'), 'failed')
        self.assertEqual(item['budget']['retries']['code'], 2)

    def test_three_remediation_rounds_allow_rereview(self):
        item = new_item()
        for _ in range(3):
            self.assertEqual(prepare(item, contract(), 'small-change'), 'prepared')
            closed_call(item, contract())
            self.assertEqual(prepare(item, contract('fix', 'review', 'stage_completed'), 'small-change'), 'prepared')
            closed_call(item, contract())
        self.assertEqual(item['budget']['remediation'], 3)
        self.assertEqual(item['budget']['calls'], 6)
        self.assertEqual(prepare(item, contract(), 'small-change'), 'failed')

    def test_validate_evidence_loop_bounded_by_total(self):
        item = new_item(); state = contract('validate', 'validate', 'stage_completed'); state['acceptance'] = {'status': 'pending'}
        for _ in range(16):
            self.assertEqual(prepare(item, state, 'full'), 'prepared')
            closed_call(item, state)
        self.assertEqual(prepare(item, state, 'full'), 'failed')
        self.assertEqual(item['budget']['calls'], 16)

    def test_completion_on_sixteenth_call_is_preserved(self):
        item = new_item(); state = contract('validate', 'validate', 'stage_completed')
        for _ in range(16):
            prepare(item, state, 'full'); closed_call(item, state)
        state['status'] = 'completed'; state['acceptance'] = {'status': 'passed'}
        self.assertEqual(prepare(item, state, 'full'), 'completed')

    def test_normal_boundary_with_exhausted_budget(self):
        item = new_item(); state = contract('validate', 'validate', 'stage_completed')
        for _ in range(16): prepare(item, state, 'full'); closed_call(item, state)
        self.assertEqual(prepare(item, contract('review', 'validate', 'stage_completed'), 'review-only'), 'completed')

    def test_acceptance_failure_is_not_remediation_charge(self):
        item = new_item(); state = contract('validate', 'fix', 'acceptance_failed')
        self.assertEqual(prepare(item, state, 'full'), 'prepared')
        self.assertEqual(item['budget']['remediation'], 0)

    def test_corrupt_budget_is_not_reconstructed(self):
        item = new_item(); item['budget']['calls'] = 3
        with self.assertRaises(ValueError): prepare(item, contract(), 'full')


class UnstartedRecoveryTests(unittest.TestCase):
    def item(self, stage='code'):
        item = new_item()
        item['start_action'] = {'stage': stage, 'source': 'Gate and source checked'}
        return item

    def test_persisted_running_without_intent_rechecks_start(self):
        for stage in ('code', None):
            item = self.item(stage)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'run.json'; path.write_text(json.dumps(item))
                recovered = json.loads(path.read_text())
                action = model.resume_unstarted(recovered, True, 'not_dispatched_no_delivery')
            self.assertEqual(action, item['start_action'])
            self.assertEqual(recovered, item)
            self.assertEqual(recovered['budget']['calls'], 0)

    def test_gate_failure_or_uncertain_dispatch_cannot_use_start(self):
        for admitted, evidence in [(False, 'not_dispatched_no_delivery'), (True, 'unknown'), (True, 'partial')]:
            item = self.item(); saved = deepcopy(item)
            with self.subTest(admitted=admitted, evidence=evidence):
                self.assertIsNone(model.resume_unstarted(item, admitted, evidence))
                self.assertEqual(item, saved)

    def test_recorded_call_cannot_reenter_unstarted_branch(self):
        item = self.item()
        self.assertIsNotNone(model.resume_unstarted(item, True, 'not_dispatched_no_delivery'))
        prepare(item, contract('design', 'code', 'stage_completed'), 'small-change')
        saved = deepcopy(item)
        with self.assertRaises(ValueError):
            model.resume_unstarted(item, True, 'not_dispatched_no_delivery')
        self.assertEqual(item, saved)
        self.assertEqual(recover_call(item, None, 'not_dispatched_no_delivery'), 'dispatch_same_id')
        self.assertEqual(item['calls'][0]['id'], 1)
        self.assertEqual(item['budget']['calls'], 1)

    def test_inconsistent_unstarted_state_stops(self):
        for fields in ({'authorization_consumed': True}, {'calls': None}, {'start_action': None},
                       {'result': {'state': 'completed'}}, {'budget': {'calls': 1, 'remediation': 0, 'retries': {}}},
                       {'checkpoint': {'pending_call': 1, 'last_delivery': None}}):
            item = self.item(); item.update(fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                model.resume_unstarted(item, True, 'not_dispatched_no_delivery')


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.item = new_item()
        prepare(self.item, contract(), 'full', authorization=True)

    def test_prepared_intent_does_not_prove_no_dispatch(self):
        self.assertEqual(recover_call(self.item, contract(), 'unknown'), 'failed')
        self.assertEqual(self.item['budget']['calls'], 1)
        self.assertFalse(self.item['calls'][0]['closed'])

    def test_confirmed_not_dispatched_reuses_id_and_charge(self):
        before = deepcopy(self.item)
        self.assertEqual(recover_call(self.item, None, 'not_dispatched_no_delivery'), 'dispatch_same_id')
        self.assertEqual(self.item, before)

    def test_delivered_before_checkpoint_closed_once(self):
        live = contract('fix', 'review', 'stage_completed')
        self.assertEqual(recover_call(self.item, live, 'complete'), 'closed')
        saved = deepcopy(self.item)
        self.assertEqual(recover_call(self.item, live, 'complete'), 'already_closed')
        self.assertEqual(self.item, saved)

    def test_partial_or_sync_failed_delivery_stops(self):
        for evidence, synced in [('partial', True), ('complete', False)]:
            item = deepcopy(self.item)
            with self.subTest(evidence=evidence):
                self.assertEqual(recover_call(item, contract('fix'), evidence, synced), 'failed')

    def test_cannot_prepare_over_open_call(self):
        with self.assertRaises(ValueError): prepare(self.item, contract(), 'full')

    def test_authorization_remains_consumed(self):
        recover_call(self.item, contract('fix'), 'complete')
        self.assertTrue(self.item['authorization_consumed'])

    def test_file_restart_reads_persisted_intent(self):
        with tempfile.TemporaryDirectory() as folder:
            record = Path(folder) / 'run.json'
            record.write_text(json.dumps(self.item))
            recovered = json.loads(record.read_text())
            self.assertEqual(recover_call(recovered, contract('fix'), 'complete'), 'closed')
            self.assertEqual(recovered['budget']['calls'], 1)
            self.assertEqual(len(recovered['calls']), 1)

    def test_invalid_temporary_save_does_not_replace_valid_record(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'run.json'; temporary = Path(folder) / '.run.tmp'
            target.write_text(json.dumps(self.item)); original = target.read_bytes()
            temporary.write_text('{partial')
            with self.assertRaises(json.JSONDecodeError): json.loads(temporary.read_text())
            self.assertEqual(target.read_bytes(), original)
            recovered = deepcopy(self.item); recover_call(recovered, contract('fix'), 'complete')
            temporary.write_text(json.dumps(recovered)); json.loads(temporary.read_text())
            os.replace(temporary, target)
            self.assertTrue(json.loads(target.read_text())['calls'][0]['closed'])


if __name__ == '__main__':
    unittest.main()

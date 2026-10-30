"""Test-only current control interpretation; legacy model remains a 0.6 oracle.

These checks exercise state scenarios, not real agent adherence to prose.
"""
from .model import decision as legacy_decision, result_valid as legacy_result_valid
from .test_run_guard import guard


def result_valid(state, expected=None, before=None, synced=True, history=()):
    """history contains verified contracts, including source Runs when supplied."""
    if not legacy_result_valid(state, expected, before, synced):
        return False
    if expected:
        try:
            for previous in history:
                sr = previous['stage_result']
                if sr['stage'] == expected and state['stage_result']['round'] <= sr['round']:
                    return False
        except (KeyError, TypeError):
            return False
    return True


def decision(state, configured_flow='code', protocol='0.11'):
    start, allowed = guard.normalize_flow(configured_flow, protocol)
    if not result_valid(state):
        return 'failed'
    if state['status'] == 'failed' or state['next']['reason'] == 'stage_failed' and not state['next']['allowed']:
        return 'failed'
    if state['status'] == 'blocked' or state['blocked']['value']:
        return 'blocked'
    if state['next']['stage'] in ('need', 'design'):
        return 'blocked'
    if state['status'] == 'completed' and state['stage_result']['stage'] in ('code', 'fix'):
        return 'blocked'
    if (state['stage_result']['stage'] in ('code', 'fix', 'validate')
            and state['next']['stage'] == 'review' and 'review' not in allowed):
        return 'blocked'
    return legacy_decision(state, [start, *sorted(allowed - {start})])

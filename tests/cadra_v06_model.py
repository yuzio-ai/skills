"""Test-only executable interpretation of Cadra v0.6. Never imported by skills.

This explores state invariants, not whether an agent will follow the documents.
"""
from copy import deepcopy

STAGES = {'need', 'design', 'code', 'review', 'fix', 'validate'}
PRESETS = {
    'full': ['need', 'design', 'code', 'review', 'fix', 'validate'],
    'feature': ['design', 'code', 'review', 'fix', 'validate'],
    'small-change': ['code', 'review', 'fix', 'validate'],
    'bugfix': ['fix', 'review', 'validate'],
    'review-only': ['review'],
}
END = {'completed', 'blocked', 'failed', 'skipped'}
NEXT_REASONS = {'stage_completed', 'blocking_findings', 'acceptance_failed',
                'stage_failed', 'task_completed', 'human_decision_required', 'blocked', 'other'}
BLOCK_REASONS = {'human_decision_required', 'missing_input', 'missing_permission',
                 'dependency_unavailable', 'environment_blocked', 'candidate_unavailable', 'other', None}
ACCEPTANCE = {'passed', 'failed', 'pending', 'blocked'}


def flow(value):
    values = PRESETS.get(value) if isinstance(value, str) else value
    if not isinstance(values, list) or not values or any(not isinstance(s, str) or s not in STAGES for s in values):
        raise ValueError('invalid flow')
    return values[0], frozenset(values)


def unfinished(run):
    if run['status'] not in {'running', 'interrupted', 'completed', 'stopped'}:
        raise ValueError('invalid run status')
    items = run['tasks']
    if len({i['slug'] for i in items}) != len(items):
        raise ValueError('duplicate slug')
    if sum(i['state'] == 'running' for i in items) > 1:
        raise ValueError('multiple running tasks')
    for item in items:
        if item['state'] not in END | {'queued', 'running'}:
            raise ValueError('invalid task state')
        result = item.get('result')
        if item['state'] in END:
            if not result or result['state'] != item['state']:
                raise ValueError('missing or mismatched outcome')
        elif result is not None:
            raise ValueError('premature result')
    pending = any(i['state'] not in END for i in items)
    if run['status'] == 'completed' and pending:
        raise ValueError('completed run has pending tasks')
    return run['status'] in {'running', 'interrupted'} or pending


def chain(slug, runs):
    if len({r['run_id'] for r in runs}) != len(runs):
        raise ValueError('duplicate run id')
    if any(r['protocol'] != '0.6' for r in runs):
        raise ValueError('unsupported protocol')
    if sum(unfinished(r) for r in runs) > 1:
        raise ValueError('multiple unfinished runs')
    entries = {r['run_id']: i for r in runs for i in r['tasks'] if i['slug'] == slug}
    if not entries:
        return []
    children = {}
    for key, item in entries.items():
        previous = item['previous_run']
        if previous is not None and previous not in entries:
            raise ValueError('missing predecessor')
        if previous in children:
            raise ValueError('fork')
        children[previous] = key
    ordered, current = [], children.get(None)
    while current is not None:
        if current in [key for key, _ in ordered]:
            raise ValueError('cycle')
        item = entries[current]
        if ordered and item['revision'] < ordered[-1][1]['revision']:
            raise ValueError('revision regressed')
        ordered.append((current, item))
        current = children.get(current)
    if len(ordered) != len(entries):
        raise ValueError('disconnected or cyclic chain')
    return ordered


def status(task, runs):
    if task['protocol'] != '0.6' or task['preparation'] not in {'draft', 'ready'}:
        raise ValueError('invalid task metadata')
    entries = chain(task['slug'], runs)
    if not entries:
        return task['preparation']
    for run in runs:
        for item in run['tasks']:
            if item['slug'] == task['slug'] and unfinished(run):
                if item['revision'] != task['revision'] or item['definition'] != task['definition']:
                    raise ValueError('active definition mismatch')
    item = entries[-1][1]
    if item['revision'] > task['revision']:
        raise ValueError('future run revision')
    if item['revision'] != task['revision'] or item['state'] == 'skipped':
        return task['preparation']
    return item['state']


def execution_basis(slug, runs):
    for _, item in reversed(chain(slug, runs)):
        calls, consumed = item.get('calls'), item.get('authorization_consumed')
        if not isinstance(calls, list) or type(consumed) is not bool:
            raise ValueError('missing execution evidence')
        closeout = (item.get('result') or {}).get('last_delivery')
        if item['state'] == 'skipped' and (calls or closeout or consumed):
            raise ValueError('skipped item has execution evidence')
        # Prepared intent is evidence too; an unclosed call must be reconciled.
        # Special authorization is independent of ordinary call/closeout evidence.
        if calls or closeout:
            return item
        if consumed or item['state'] == 'completed':
            raise ValueError('missing call or closeout evidence')
    return None


def revision_fields(task, runs):
    entries = chain(task['slug'], runs)
    basis = execution_basis(task['slug'], runs)
    basis_revision = basis['revision'] if basis else 0
    changed = set(task.get('changed_fields', []))
    for _, item in entries:
        if item['revision'] > basis_revision:
            changed.update(item['definition'].get('changed_fields', []))
    return changed


def revision_action(task, runs, cause_resolved=True):
    latest = next((item for _, item in reversed(chain(task['slug'], runs))
                   if item['state'] != 'skipped'), None)
    if latest and latest['state'] in {'blocked', 'failed'} and not cause_resolved:
        return 'reject'
    basis = execution_basis(task['slug'], runs)
    if basis is None:
        return 'check_first_or_adopt'
    if revision_fields(task, runs) & {'requirement', 'flow'}:
        return 'start'
    return 'verify_only' if basis['state'] == 'completed' else 'check_recovery'


def result_valid(state, expected=None, before=None, synced=True):
    try:
        sr, nxt = state['stage_result'], state['next']
        candidate = state['candidate']
        if (not isinstance(candidate, dict) or set(candidate) != {'commit', 'snapshot'}
                or any(value is not None and not isinstance(value, str) for value in candidate.values())):
            return False
        acceptance = state.get('acceptance')
        if acceptance is not None and (not isinstance(acceptance, dict)
                                       or acceptance.get('status') not in ACCEPTANCE):
            return False
        valid = (state['contract'] == '0.8' and state['task'] == 'a'
                 and state['execution_mode'] == 'unattended'
                 and state['status'] in {'in_progress', 'completed', 'blocked', 'failed'}
                 and sr['stage'] in STAGES and sr['status'] in {'completed', 'blocked', 'failed'}
                 and type(sr['round']) is int and sr['round'] > 0
                 and type(nxt['allowed']) is bool
                 and nxt['reason'] in NEXT_REASONS
                 and (nxt['stage'] in STAGES if nxt['allowed'] else nxt['stage'] is None)
                 and type(state['blocked']['value']) is bool
                 and state['blocked']['reason'] in BLOCK_REASONS
                 and (state['blocked']['value'] or state['blocked']['reason'] is None))
        if expected:
            valid &= synced and sr['stage'] == expected
            if before and before['stage_result']['stage'] == expected:
                valid &= sr['round'] > before['stage_result']['round']
        return bool(valid)
    except (KeyError, TypeError, AttributeError):
        return False


def decision(state, configured_flow):
    if not result_valid(state):
        return 'failed'
    nxt, sr = state['next'], state['stage_result']
    acceptance = (state.get('acceptance') or {}).get('status')
    allowed = flow(configured_flow)[1]
    if state['status'] == 'failed' or (nxt['reason'] == 'stage_failed' and not nxt['allowed']):
        return 'failed'
    if state['status'] == 'blocked' or state['blocked']['value']:
        return 'blocked'
    if state['status'] == 'completed':
        if acceptance == 'passed':
            return 'completed'
        if acceptance == 'failed' or 'validate' in allowed:
            return 'blocked'
        return 'completed'
    if not nxt['allowed']:
        return 'blocked'
    if nxt['stage'] in allowed:
        return 'call'
    required = (nxt['reason'] in {'blocking_findings', 'acceptance_failed', 'stage_failed'}
                or (sr['stage'] in {'fix', 'validate'} and nxt['stage'] == 'review')
                or (sr['stage'] == 'validate' and acceptance == 'pending'))
    return 'blocked' if required else 'completed'


def new_item():
    return {'budget': {'calls': 0, 'remediation': 0, 'retries': {}}, 'calls': [],
            'authorization_consumed': False,
            'checkpoint': {'pending_call': None, 'last_delivery': None}, 'state': 'running', 'result': None}


def check_budget(item):
    calls = item['calls']
    if [c['id'] for c in calls] != list(range(1, len(calls) + 1)):
        raise ValueError('invalid call ids')
    expected = {'calls': 0, 'remediation': 0, 'retries': {}}
    for call in calls:
        charged = call['charged']
        expected['calls'] += charged['calls']
        expected['remediation'] += charged['remediation']
        if charged['retry_stage']:
            stage = charged['retry_stage']
            expected['retries'][stage] = expected['retries'].get(stage, 0) + 1
    if item['budget'] != expected:
        raise ValueError('budget mismatch')


def resume_unstarted(item, admission_passed, evidence):
    """Select an unstarted action only after external Gate/dispatch checks.

    Returns no action when those checks do not establish safe continuation.
    This does not dispatch, consume authorization, or charge a call.
    """
    action = item.get('start_action')
    if (item.get('state') != 'running' or item.get('calls') != []
            or item.get('authorization_consumed') is not False
            or item.get('result') is not None
            or item.get('checkpoint') != {'pending_call': None, 'last_delivery': None}
            or not isinstance(action, dict) or 'stage' not in action
            or action['stage'] not in (*STAGES, None)):
        raise ValueError('not a verifiable unstarted action')
    check_budget(item)
    if admission_passed is not True or evidence != 'not_dispatched_no_delivery':
        return None
    return deepcopy(action)


def prepare(item, state, configured_flow, authorization=False):
    check_budget(item)
    if any(not c['closed'] for c in item['calls']):
        raise ValueError('unclosed call')
    verdict = decision(state, configured_flow)
    if verdict != 'call':
        return verdict
    sr, nxt, budget = state['stage_result'], state['next'], item['budget']
    stage = nxt['stage']
    retry = sr['status'] == 'failed' or nxt['reason'] == 'stage_failed'
    remediate = stage == 'fix' and sr['stage'] == 'review' and nxt['reason'] == 'blocking_findings'
    if budget['calls'] >= 16 or (retry and budget['retries'].get(stage, 0) >= 2) or (remediate and budget['remediation'] >= 3):
        return 'failed'
    call = {'id': len(item['calls']) + 1, 'stage': stage, 'before': deepcopy(state),
            'dispatch': 'prepared', 'closed': False, 'result': None,
            'charged': {'calls': 1, 'remediation': int(remediate), 'retry_stage': stage if retry else None}}
    item['calls'].append(call)
    budget['calls'] += 1
    budget['remediation'] += int(remediate)
    if retry:
        budget['retries'][stage] = budget['retries'].get(stage, 0) + 1
    item['checkpoint']['pending_call'] = call['id']
    item['authorization_consumed'] |= authorization
    return 'prepared'


def recover_call(item, live, evidence, synced=True):
    check_budget(item)
    call = item['calls'][-1]
    if call['closed']:
        return 'already_closed'
    if evidence == 'complete' and result_valid(live, call['stage'], call['before'], synced):
        call['result'] = deepcopy(live)
        call['closed'] = True
        item['checkpoint']['pending_call'] = None
        item['checkpoint']['last_delivery'] = deepcopy(live['stage_result'])
        return 'closed'
    if evidence == 'not_dispatched_no_delivery':
        return 'dispatch_same_id'
    item['state'] = 'failed'
    item['result'] = {'state': 'failed', 'reason': 'unconfirmed delivery'}
    return 'failed'

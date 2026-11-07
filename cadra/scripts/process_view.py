#!/usr/bin/env python3
"""Read one Cadra 0.12 Run into a compact process view; never write or dispatch.

Only frozen Run facts are read. Missing narrative, delivery times and external
evidence remain unknown; report authors may follow saved handoff references.
"""
import argparse
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location('cadra_process_guard', Path(__file__).with_name('run_guard.py'))
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def pick(value, fields):
    if not isinstance(value, dict):
        return None
    return {key: value.get(key) for key in fields}


def recorded_time(value):
    if value is not None:
        try:
            guard.timestamp(value)
            return value
        except (ValueError, TypeError):
            pass
    return None


def candidate_view(value):
    return pick(value, ('commit', 'snapshot', 'sha256'))


def result_view(value):
    result = pick(value, ('state', 'last_delivery', 'findings', 'acceptance',
                          'human_intervention', 'next', 'source', 'at', 'reason'))
    if result is not None:
        result['candidate'] = candidate_view(value.get('candidate'))
    return result


def contract_mapping(value, fields, label):
    guard.require(isinstance(value, dict) and set(fields) <= value.keys(),
                  'invalid recorded ' + label + ': mapping and required fields expected')
    return value


def delivery_contract(result, slug, stage):
    """Validate claimed 0.8 snapshots; a wholly absent delivery stays unknown.

    The Run guard validates scheduling, charges and rounds, not the full
    Cohestra contract. Reject malformed fields before lossy view projection.
    This checks recorded fields and their consistency, not external evidence.
    """
    if not isinstance(result, dict):
        return None
    if 'stage_result' in result or isinstance(result.get('contract'), str):
        value = result
    elif 'contract' in result:
        value = result['contract']
    else:
        return None
    value = contract_mapping(value, ('contract', 'task', 'status', 'execution_mode',
                                     'stage_result', 'candidate', 'next', 'blocked'), 'Cohestra contract')
    guard.require(value['contract'] == '0.8' and value['task'] == slug,
                  'recorded delivery contract/identity mismatch')
    guard.require(value['execution_mode'] == 'unattended', 'recorded delivery mode mismatch')
    guard.require(value['status'] in ('in_progress', 'completed', 'blocked', 'failed'),
                  'invalid recorded task status')
    delivery = contract_mapping(value['stage_result'], ('stage', 'status', 'round'), 'stage_result')
    guard.require(delivery['stage'] == stage and
                  delivery['status'] in ('completed', 'blocked', 'failed') and
                  type(delivery['round']) is int and delivery['round'] > 0,
                  'invalid recorded stage result')
    candidate = contract_mapping(value['candidate'], ('commit', 'snapshot'), 'candidate')
    guard.require(set(candidate) == {'commit', 'snapshot'} and
                  all(v is None or isinstance(v, str) for v in candidate.values()),
                  'invalid recorded candidate')
    findings = value.get('findings')
    if findings is not None:
        contract_mapping(findings, ('blocking', 'non_blocking'), 'findings')
        for key in ('blocking', 'non_blocking', 'unresolved'):
            if key == 'unresolved' and findings.get(key) is None:
                continue
            guard.require(type(findings[key]) is int and findings[key] >= 0,
                          'invalid recorded findings.' + key)
    acceptance = value.get('acceptance')
    if acceptance is not None:
        contract_mapping(acceptance, ('status',), 'acceptance')
        guard.require(acceptance['status'] in ('passed', 'failed', 'pending', 'blocked'),
                      'invalid recorded acceptance.status')
    nxt = contract_mapping(value['next'], ('stage', 'allowed', 'reason'), 'next')
    guard.require(type(nxt['allowed']) is bool and
                  (nxt['stage'] in ('need', 'design', *guard.STAGES) if nxt['allowed'] else nxt['stage'] is None) and
                  nxt['reason'] in ('stage_completed', 'blocking_findings', 'acceptance_failed',
                                    'stage_failed', 'task_completed', 'human_decision_required', 'blocked', 'other'),
                  'invalid recorded next')
    blocked = contract_mapping(value['blocked'], ('value', 'reason'), 'blocked')
    guard.require(type(blocked['value']) is bool, 'invalid recorded blocked.value')
    if blocked['value']:
        guard.require(blocked['reason'] in ('human_decision_required', 'missing_input', 'missing_permission',
                                           'dependency_unavailable', 'environment_blocked', 'candidate_unavailable', 'other') and
                      not nxt['allowed'] and value['status'] == 'blocked', 'invalid recorded blocked state')
    else:
        guard.require(blocked['reason'] is None, 'invalid recorded blocked.reason')
    if stage == 'validate' and acceptance is not None and acceptance['status'] == 'passed':
        guard.require(delivery['status'] == 'completed' and value['status'] == 'completed' and
                      nxt['stage'] is None and not nxt['allowed'] and nxt['reason'] == 'task_completed' and
                      blocked['value'] is False and blocked['reason'] is None,
                      'invalid recorded validate completion state')
    return value


def call_view(call, slug):
    closed = call['closed']
    result = call.get('result') if closed else None
    try:
        contract = delivery_contract(result, slug, call['stage']) if closed else None
    except ValueError as error:
        raise ValueError(f"{slug} call {call['id']}: {error}") from error
    gaps = []
    if closed and contract is None:
        gaps.append('closed call has no recorded Cohestra contract')
    # Direct deliveries have no wrapper sync field; keep it unknown.
    sync = result.get('index_sync') if isinstance(result, dict) and result is not contract else None
    if sync is not None:
        guard.require(type(sync) is bool, 'invalid index_sync value')
    if sync is False:
        gaps.append('recorded index synchronization failed')
    dispatch = call.get('dispatch_evidence') or {}
    return dict(
        id=call['id'], stage=call['stage'],
        status='pending' if not closed else 'unknown' if gaps else 'recorded',
        dispatch=call['dispatch'], closed=closed,
        stage_result=contract['stage_result'] if contract else None,
        findings=pick(contract.get('findings'), ('blocking', 'non_blocking', 'unresolved')) if contract else None,
        acceptance=pick(contract.get('acceptance'), ('status',)) if contract else None,
        candidate=candidate_view(contract.get('candidate')) if contract else None,
        next=pick(contract.get('next'), ('stage', 'allowed', 'reason')) if contract else None,
        blocked=pick(contract.get('blocked'), ('value', 'reason')) if contract else None,
        handoff=result.get('handoff') if isinstance(result, dict) else None,
        source=result.get('source') if isinstance(result, dict) else None,
        index_sync=sync, reason=call.get('reason'),
        prepared_at=recorded_time(call.get('prepared_at')),
        dispatched_at=recorded_time(dispatch.get('at')),
        delivered_at=recorded_time(result.get('at')) if isinstance(result, dict) else None,
        gaps=gaps,
    )


def event_views(data, scheduler_view):
    requests = {r['seq']: r for r in scheduler_view['requests']}
    members = []
    group = 0
    result = []
    for event in data['scheduler']['events']:
        if event['kind'] == 'group':
            members = event['members']
            group += 1
        request = requests.get(event.get('seq'), {})
        slug = event.get('slug', request.get('slug'))
        item = pick(event, ('id', 'at', 'generation', 'kind', 'seq', 'resource',
                            'outcome', 'source', 'reason', 'stage', 'before_ref'))
        item.update(group=group, tasks=[slug] if slug else list(members),
                    call_id=event.get('call_id', request.get('call_id')))
        if item['resource'] is None:
            item['resource'] = request.get('kind')
        if 'candidate' in event:
            item['candidate'] = pick(event['candidate'], ('snapshot', 'sha256'))
        result.append(item)
    return result


def process_view(data):
    """Derive presentation facts, preserving call order and scheduler event IDs."""
    scheduler_view = guard.validate(data, return_view=True)
    events = event_views(data, scheduler_view)
    tasks = []
    for task in data['tasks']:
        tasks.append(dict(
            slug=task['slug'], title=task['definition'].get('title'),
            revision=task['revision'], previous_run=task.get('previous_run'),
            state=task['state'], origin=task['definition'].get('origin'),
            start_action=pick(task.get('start_action'), ('kind', 'stage', 'source')),
            calls=[call_view(call, task['slug']) for call in task['calls']],
            event_ids=[e['id'] for e in events if task['slug'] in e['tasks']],
            # Historical task and phase outcomes are separate facts.
            result=result_view(task.get('result')),
        ))
    return dict(protocol=data['protocol'], run_id=data['run_id'], status=data['status'],
                created_at=data['created_at'], tasks=tasks, events=events,
                ownership_history=data['ownership_history'], append_history=data['append_history'],
                closeout=[{**pick(c, ('slug', 'covered', 'at', 'generation', 'event_count')),
                           'candidate': candidate_view(c.get('candidate'))} for c in data['closeout']])


def read_view(path):
    path = Path(path)
    guard.require(path.is_absolute(), '--run must be an absolute path')
    raw = path.read_bytes()
    result = process_view(guard.header(raw))
    guard.require(path.read_bytes() == raw, 'Run changed while reading; retry the read')
    result['source'] = dict(path=str(path), sha256=guard.digest(raw))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = read_view(args.run)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError) as error:
        parser.exit(1, f'process view unavailable: {error}\n')
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

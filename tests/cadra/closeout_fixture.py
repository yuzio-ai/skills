"""Synthetic closeout deliveries through real guard operations, not agent proof."""
from copy import deepcopy
from .test_run_guard import guard, binding, AT
from .test_cadra import contract


def definition(data, candidate):
    scope = guard.closeout.writable(data, guard.scheduler, guard.normalize_flow)
    number = len(data['closeout']) + 1
    slug = guard.closeout.slug(data, number)
    return dict(protocol=guard.PROTOCOL, slug=slug, title='收尾一致性审查', revision=1,
                preparation='ready', flow='review' if scope['files'] or scope['dirs'] else ['review'],
                origin=dict(run=data['run_id'], round=number), priority='medium', dependencies=[],
                execution_policy=dict(stop_queue_on_failure=True),
                cohestra_task=f'.yuzio/cohestra/handoffs/{slug}/',
                ready_scope=dict(revision=1, scope=scope, inputs=deepcopy(candidate['inputs'])),
                requirement='检查本轮文档同步与替代内容；仅整改已授权范围内的确定问题。')


def deliver(data, stage, candidate, publish, *, next_stage=None, blocking=0, findings=None):
    """Persist binding, intent, dispatch and synthetic delivery separately."""
    data = deepcopy(data); task = data['tasks'][-1]; slug = task['slug']
    role = 'reviewer' if stage == 'review' else 'worker'
    ref = role + '-1'
    when = data['executor']['progress']['at']
    if not any(b['id'] == ref for b in task['agents']):
        task['agents'].append(binding(role, slug+'-'+role, ref))
        publish(data, 'update')
    previous = deepcopy(task['calls'][-1]['result']['contract']) if task['calls'] else None
    call = dict(id=len(task['calls'])+1, stage=stage, reason='synthetic closeout stage', execution_mode='unattended',
                agent_ref=ref, before=previous, dispatch='prepared', dispatch_evidence=None, closed=False, result=None,
                charged=dict(calls=1, remediation=int(stage=='fix' and previous is not None and previous['next']['reason']=='blocking_findings'), retry_stage=None),
                prepared_at=when)
    task['calls'].append(call); task['budget']['calls'] += 1
    task['budget']['remediation'] += call['charged']['remediation']
    task['state'] = 'running'; task['checkpoint']['pending_call'] = call['id']
    publish(data, 'update')
    call.update(dispatch='dispatched', dispatch_evidence=dict(agent_id=slug+'-'+role, source='synthetic host response', at=when))
    publish(data, 'update')
    sr = contract(stage, next_stage, 'blocking_findings' if blocking else 'stage_completed',
                  sum(c['stage']==stage for c in task['calls']))
    sr.update(task=slug, candidate=dict(commit=None, snapshot=candidate['snapshot']),
              findings=dict(blocking=blocking, non_blocking=0, unresolved=0))
    sr['next']['allowed'] = next_stage is not None
    if next_stage is None:
        sr.update(status='completed')
        sr['next'] = dict(stage=None, allowed=False, reason='task_completed')
        if stage == 'validate': sr['acceptance'] = dict(status='passed')
    delivery = dict(contract=sr, handoff=f'{stage}-{sr["stage_result"]["round"]:02d}.md',
                    index_sync=True, findings=deepcopy(findings or []))
    call.update(closed=True, result=delivery)
    task['checkpoint'].update(pending_call=None, last_delivery=deepcopy(delivery))
    publish(data, 'update')
    return data


def finalize(data, candidate, publish):
    task = data['tasks'][-1]; call = task['calls'][-1]
    b = next(b for b in task['agents'] if b['id']==call['agent_ref'])
    when = data['executor']['progress']['at']
    data = guard.scheduler.append_event(data, 'wait', when, slug=task['slug'], call_id=call['id'],
        resource='finalization', scope=task['definition']['ready_scope']['scope'], candidate=candidate,
        stop=dict(agent_id=b['agent_id'], host_id=b['host_id'], tools_stopped=True,
                  observed_at=when, source='synthetic stopped stage and tools'))
    publish(data, 'update')
    data = guard.scheduler.append_event(data, 'close', when, candidate=candidate)
    publish(data, 'update')
    task = data['tasks'][-1]
    task.update(state='completed', result=dict(state='completed', candidate=deepcopy(candidate),
                last_delivery=deepcopy(task['checkpoint']['last_delivery']),
                acceptance=deepcopy(task['checkpoint']['last_delivery']['contract'].get('acceptance'))))
    publish(data, 'update')
    return data


def complete(data, publish, candidate=None):
    """Used by unrelated report/race regressions to satisfy the new real gate."""
    candidate = candidate or deepcopy(guard.scheduler.replay(data)['group']['candidate'])
    d = definition(data, candidate)
    when = max([data['executor']['progress']['at']] + [e['at'] for e in data['scheduler']['events']], key=guard.timestamp)
    data = guard.closeout.prepare(data, d, candidate, when,
                                  'synthetic Gate and project/task preflight evidence', guard.scheduler, guard.normalize_flow)
    publish(data, 'closeout')
    data = guard.scheduler.append_event(data, 'group', when,
                    members=[d['slug']], before={d['slug']: candidate['inputs']}, before_refs={d['slug']: 'synthetic fixed before'})
    publish(data, 'update')
    readonly = d['flow'] == ['review']
    data = deliver(data, 'review', candidate, publish, next_stage=None if readonly else 'validate')
    if not readonly: data = deliver(data, 'validate', candidate, publish)
    return finalize(data, candidate, publish)

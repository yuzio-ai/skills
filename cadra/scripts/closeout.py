"""Protocol 0.12 closeout evidence and admission. No tools, dispatch or writes.

The journal references ordinary Tasks; it does not duplicate their execution
state. The caller verifies actual authorization, snapshots and preflight evidence.
"""
from copy import deepcopy


def need(ok, message):
    if not ok:
        raise ValueError(message)


def origin(definition):
    value = definition.get('origin')
    if value is not None:
        need(isinstance(value, dict) and set(value) == {'run', 'round'}, 'invalid closeout origin')
        need(isinstance(value['run'], str) and type(value['round']) is int and value['round'] > 0,
             'invalid closeout origin identity')
    return value


def slug(data, round_):
    return f"closeout-{data['run_id']}-{round_:02d}"


def covered(tasks):
    return [{'slug': t['slug'], 'revision': t['revision']} for t in tasks]


def writable(data, scheduler, normalize_flow):
    """Exclusive is a scheduling mode, not permission to edit the whole repo."""
    tasks = data['tasks']
    requests = scheduler.replay(data)['requests']
    allowed = {t['slug'] for t in tasks if origin(t['definition']) is None
               and 'fix' in normalize_flow(t['definition']['flow'])[1]}
    scopes = [scheduler.admission(t) for t in tasks if t['slug'] in allowed]
    scopes += [r['scope'] for r in requests if r['slug'] in allowed
               and r['kind'] in ('files', 'agent') and r.get('granted_at')]
    result = dict(mode='exclusive', files=[], dirs=[])
    for kind in ('files', 'dirs'):
        paths = {}
        for value in scopes:
            for path in value[kind]:
                paths.setdefault(scheduler.path_key(path), path)
        result[kind] = sorted(paths.values(), key=scheduler.path_key)
    return result


def required_inputs(tasks, events, scheduler):
    keys = set()
    for task in tasks:
        admission = task['definition']['ready_scope']
        keys.update(scheduler.hashes(admission['inputs']))
        keys.update(map(scheduler.path_key, admission['scope']['files']))
    for event in events:
        if 'candidate' in event:
            keys.update(scheduler.hashes(event['candidate']['inputs']))
        if event['kind'] == 'wait':
            keys.update(map(scheduler.path_key, event['scope']['files']))
        if event['kind'] == 'grant' and 'before' in event:
            keys.update(scheduler.hashes(event['before']))
        if event['kind'] == 'group':
            for values in event['before'].values():
                keys.update(scheduler.hashes(values))
    return keys


def result_candidate(task):
    result = task.get('result') or {}
    return result.get('candidate')


def passed(task, group, scheduler):
    """Check the saved review/acceptance basis, not an author's PASS string."""
    if task['state'] != 'completed' or not group or group['phase'] != 'closed':
        return False
    final = result_candidate(task)
    if final != group['candidate']:
        return False
    scheduler.candidate(final)
    calls = task['calls']
    if not calls or calls[0]['stage'] != 'review' or any(not c['closed'] or c['dispatch'] != 'dispatched' for c in calls):
        return False
    if any(not isinstance(c.get('result'), dict) or c['result'].get('index_sync') is not True
           or not isinstance(c['result'].get('handoff'), str) or not c['result']['handoff'].strip() for c in calls):
        return False
    fixes = [i for i, c in enumerate(calls) if c['stage'] == 'fix']
    reviews = [i for i, c in enumerate(calls) if c['stage'] == 'review' and i > max(fixes, default=-1)]
    if not reviews:
        return False
    last_review = calls[reviews[-1]]['result'].get('contract', {})
    last = calls[-1]['result'].get('contract', {})
    for contract in (last_review, last):
        if not isinstance(contract, dict):
            return False
        blocked, findings, candidate = (contract.get(k) for k in ('blocked', 'findings', 'candidate'))
        if not all(isinstance(value, dict) for value in (blocked, findings, candidate)):
            return False
        if (contract.get('contract') != '0.8' or contract.get('task') != task['slug']
                or contract.get('execution_mode') != 'unattended'
                or contract.get('status') not in ('in_progress', 'completed')
                or blocked.get('value') is not False or blocked.get('reason') is not None
                or type(findings.get('blocking')) is not int or findings['blocking'] != 0
                or type(findings.get('non_blocking')) is not int or findings['non_blocking'] < 0
                or type(findings.get('unresolved', 0)) is not int or findings.get('unresolved', 0) != 0
                or candidate.get('snapshot') != final['snapshot']):
            return False
    if last_review.get('stage_result', {}).get('status') != 'completed':
        return False
    read_only = task['definition']['flow'] == ['review']
    acceptance = last.get('acceptance')
    return (last.get('status') == 'completed'
            and last.get('stage_result', {}).get('status') == 'completed'
            and last.get('stage_result', {}).get('stage') == ('review' if read_only else 'validate')
            and last.get('next') == dict(stage=None, allowed=False, reason='task_completed')
            and (read_only and (acceptance is None or isinstance(acceptance, dict)
                                 and acceptance.get('status') in ('passed', 'pending', 'blocked'))
                 or not read_only and isinstance(acceptance, dict) and acceptance.get('status') == 'passed'))


def validate(data, view, scheduler, normalize_flow):
    rounds = data.get('closeout')
    need(isinstance(rounds, list), 'closeout journal required')
    tasks = data['tasks']
    registered = []
    last_index = -1
    for number, record in enumerate(rounds, 1):
        need(isinstance(record, dict) and set(record) == {'slug', 'covered', 'candidate', 'at', 'generation', 'event_count'},
             'invalid closeout record')
        scheduler.at(record['at'])
        need(type(record['generation']) is int and 1 <= record['generation'] <= data['executor']['generation'],
             'invalid closeout generation')
        owners = [h['previous'] for h in data['ownership_history']] + [data['executor']]
        owner = next((o for o in owners if o['generation'] == record['generation']), None)
        need(owner is not None and scheduler.at(record['at']) >= scheduler.at(owner['claimed_at']), 'closeout predates owner claim')
        index = next((i for i, t in enumerate(tasks) if t['slug'] == record['slug']), -1)
        need(index > last_index and record['slug'] == slug(data, number), 'closeout task order/identity mismatch')
        prefix, task = tasks[:index], tasks[index]
        need(prefix and record['covered'] == covered(prefix), 'closeout coverage must match preceding queue')
        need(origin(task['definition']) == dict(run=data['run_id'], round=number), 'closeout source Run mismatch')
        count = record['event_count']
        need(type(count) is int and 0 <= count <= len(data['scheduler']['events']), 'invalid closeout event boundary')
        events = data['scheduler']['events'][:count]
        need(events and events[-1]['kind'] == 'close', 'closeout requires a stable preceding group')
        need(scheduler.at(record['at']) >= scheduler.at(events[-1]['at']), 'closeout predates covered group')
        grouped = {s for e in events if e['kind'] == 'group' for s in e['members']}
        need(task['slug'] not in grouped and grouped <= {t['slug'] for t in prefix}, 'closeout event boundary crosses task')
        scheduler.candidate(record['candidate'])
        need(required_inputs(prefix, events, scheduler) <= set(scheduler.hashes(record['candidate']['inputs'])),
             'closeout candidate omits covered inputs')
        need(not scheduler.affected(events[-1]['candidate']['inputs'], record['candidate']['inputs']),
             'closeout candidate differs from preceding stable group')
        basis = {**data, 'tasks': prefix, 'scheduler': {'events': events}}
        expected_scope = writable(basis, scheduler, normalize_flow)
        need(scheduler.admission(task) == expected_scope, 'closeout scope exceeds inherited implementation permission')
        expected_flow = 'review' if expected_scope['files'] or expected_scope['dirs'] else ['review']
        need(task['definition']['flow'] == expected_flow and task['start_action']['stage'] == 'review',
             'closeout flow must preserve inherited permission')
        calls = task['calls']
        need(not calls or calls[0]['stage'] == 'review', 'closeout first call must be review')
        for call in calls[1:]:
            next_ = (call.get('before') or {}).get('next', {})
            refresh = call.get('refresh')
            refreshed = (isinstance(refresh, dict) and refresh in view['invalidations']
                         and refresh.get('slug') == task['slug'] and refresh.get('stage') == call['stage'])
            need(refreshed or next_.get('allowed') is True and next_.get('stage') == call['stage'],
                 'closeout call must follow verified next or candidate refresh')
        need(task['definition'].get('execution_policy') == {'stop_queue_on_failure': True},
             'closeout failure must stop the Run')
        need(task['previous_run'] is None and task['revision'] == 1, 'closeout is bound to its originating Run')
        need(task['definition'].get('cohestra_task') == f".yuzio/cohestra/handoffs/{task['slug']}/",
             'closeout Cohestra binding mismatch')
        if number > 1:
            previous = tasks[last_index]
            group = next((g for g in view['groups'] if previous['slug'] in g['members']), None)
            need(passed(previous, group, scheduler), 'cannot replace unsuccessful closeout or reset its budget')
            need(any(origin(t['definition']) is None for t in tasks[last_index+1:index]),
                 'cannot repeat closeout for unchanged coverage')
        for binding in task['agents']:
            if binding['role'] == 'reviewer':
                authors = [(b['host_id'], b['agent_id']) for t in prefix for b in t['agents'] if b['role'] == 'worker']
                need((binding['host_id'], binding['agent_id']) not in authors, 'closeout reviewer authored covered changes')
        group = next((g for g in view['groups'] if task['slug'] in g['members']), None)
        if group and group['phase'] == 'closed' and task['state'] not in ('failed', 'blocked', 'skipped'):
            need(required_inputs(prefix, events, scheduler) | set(scheduler.hashes(record['candidate']['inputs']))
                 <= set(scheduler.hashes(group['candidate']['inputs'])), 'final closeout candidate omits covered inputs')
        if task['state'] == 'completed':
            need(passed(task, group, scheduler), 'closeout completion lacks matching independent review/acceptance')
            final_keys = set(scheduler.hashes(result_candidate(task)['inputs']))
            need(required_inputs(prefix, events, scheduler) | set(scheduler.hashes(record['candidate']['inputs'])) <= final_keys,
                 'final closeout candidate omits covered inputs')
        registered.append(record['slug']); last_index = index
    need([t['slug'] for t in tasks if origin(t['definition']) is not None] == registered,
         'generated closeout task requires owner registration')
    if data['status'] == 'completed':
        need(rounds and last_index == len(tasks)-1 and tasks[-1]['state'] == 'completed',
             'completed Run requires current passed closeout')
        need(view['group'] and view['group']['members'] == [tasks[-1]['slug']], 'closeout must be the final stable group')


def prepare(data, definition, candidate, when, evidence, scheduler, normalize_flow):
    """Build a proposal AFTER the caller prepared the Task, Gate and preflight."""
    need(data['status'] == 'running', 'closeout requires running Run')
    need(all(t['state'] in scheduler.TERMINAL for t in data['tasks']), 'drain queue before closeout')
    view = scheduler.replay(data)
    need(view['group'] and view['group']['phase'] == 'closed', 'close groups before closeout')
    need(not scheduler._policy_failures(data), 'stopped policy forbids closeout dispatch')
    need(isinstance(evidence, str) and evidence.strip(), 'closeout preflight evidence required')
    number = len(data['closeout']) + 1
    need(definition.get('slug') == slug(data, number), 'unexpected generated closeout slug')
    proposal = deepcopy(data)
    task = dict(slug=definition['slug'], revision=1, previous_run=None, state='queued', definition=deepcopy(definition),
                start_action=dict(kind='closeout', stage='review', source=evidence), authorization_consumed=False,
                budget=dict(calls=0, remediation=0, retries={}), checkpoint=dict(pending_call=None, last_delivery=None),
                agents=[], calls=[], result=None)
    proposal['tasks'].append(task)
    proposal['preflight'].append(dict(scope='task', slug=task['slug'], status='passed', at=when, inputs={}, evidence=evidence))
    proposal['append_history'].append(dict(at=when, source=evidence, tasks=[dict(slug=task['slug'], revision=1)]))
    proposal['closeout'].append(dict(slug=task['slug'], covered=covered(data['tasks']), candidate=deepcopy(candidate),
                                    at=when, generation=data['executor']['generation'], event_count=len(data['scheduler']['events'])))
    return proposal


def summary(data):
    rounds = data['closeout']
    if not rounds:
        return dict(status='not_started', rounds=0)
    record = rounds[-1]
    task = next(t for t in data['tasks'] if t['slug'] == record['slug'])
    status = task['state']
    if status == 'completed':
        status = 'passed' if data['tasks'][-1]['slug'] == task['slug'] else 'outdated'
    result = task.get('result') or {}
    delivery = (task['calls'][-1].get('result') or {}) if task['calls'] else {}
    delivery = delivery if isinstance(delivery, dict) else {}
    contract = delivery if 'stage_result' in delivery else delivery.get('contract')
    contract = contract if isinstance(contract, dict) else {}
    counts = contract.get('findings')
    counts = counts if isinstance(counts, dict) else {}
    acceptance = contract.get('acceptance')
    acceptance = acceptance if isinstance(acceptance, dict) else {}
    return dict(status=status, rounds=len(rounds), slug=task['slug'], covered=len(record['covered']),
                read_only=task['definition']['flow'] == ['review'],
                findings={k: counts[k] for k in ('blocking', 'non_blocking', 'unresolved') if k in counts},
                acceptance=acceptance.get('status', 'unknown'),
                reason=result.get('reason'))

"""Read-only Cadra 0.10 structural validation, frozen from e1d7fcb.

Used only by list_summary. No writing, migration, dispatch or installed-copy
imports. Keep serial states, budgets, roles and flow grammar separate from 0.11.
Optional display_issues preserves list's action-only diagnostics; strict checks
remain the default. Query output is never admission or execution evidence.
"""
from datetime import datetime
import re


STAGES = ('code', 'review', 'fix', 'validate')


PROTOCOL = '0.10'


PROTOCOL_ERROR = 'unsupported Cadra protocol; finish old Runs and archive the old container before cutover'


PRESETS = {
    'code': ('code', 'review', 'fix', 'validate'),
    'fix': ('fix', 'review', 'validate'),
    'review': ('review', 'fix', 'validate'),
}


def normalize_flow(value='code', protocol=PROTOCOL):
    require(protocol == PROTOCOL, PROTOCOL_ERROR)
    stages = PRESETS.get(value) if isinstance(value, str) else value
    require(isinstance(stages, (list, tuple)) and stages and
            all(isinstance(s, str) and s in STAGES for s in stages), 'invalid ' + protocol + ' flow')
    return stages[0], frozenset(stages)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    require(isinstance(value, str), 'timestamp required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timestamp must include timezone')
    return result


def validate_charge(task, call):
    charged, stage = call['charged'], call['stage']
    require(charged['calls'] == 1 and type(charged['calls']) is int and
            type(charged['remediation']) is int and charged['remediation'] in (0, 1), 'invalid budget charge')
    require('retry_stage' in charged and
            (charged['retry_stage'] is None or charged['retry_stage'] == stage), 'retry charge must match call stage')
    before = call.get('before')
    require(before is None or isinstance(before, dict), 'invalid before contract for budget')
    require(call['id'] == 1 or before is not None, 'follow-up call requires before contract')
    remediation, retry_stage = 0, None
    if before is not None:
        previous, next_ = before.get('stage_result', {}), before.get('next', {})
        require(isinstance(previous, dict) and isinstance(next_, dict) and
                previous.get('stage') in ('need', 'design', *STAGES) and
                previous.get('status') in ('completed', 'blocked', 'failed') and
                type(next_.get('allowed')) is bool and isinstance(next_.get('reason'), str),
                'before contract lacks budget evidence')
        remediation = int(stage == 'fix' and previous['stage'] == 'review' and
                          next_['reason'] == 'blocking_findings')
        if previous['status'] == 'failed' or next_['reason'] == 'stage_failed' and next_['allowed']:
            retry_stage = stage
    # A newly admitted definition restart may use its own start instead of the
    # old contract's next. Preserve that existing first-call exception using
    # frozen revision/authorization evidence, without inventing a kind enum.
    # The caller still verifies the exact source and admitted start action.
    definition = task['definition']
    restart_eligible = (call['id'] == 1 and task.get('authorization_consumed') is True and
                        bool(set(definition.get('changed_fields', [])) & {'requirement', 'flow'}) and
                        stage == task['start_action']['stage'] == normalize_flow(definition['flow'])[0])
    actual = (charged['remediation'], charged['retry_stage'])
    require(actual == (remediation, retry_stage) or restart_eligible and actual == (0, None),
            'budget charge disagrees with call basis')


def saved_contract(value):
    if isinstance(value, dict):
        # A direct Cohestra contract has a scalar `contract` version; only
        # delivery wrappers use that key for the nested contract object.
        contract = value if 'stage_result' in value else value.get('contract')
        if isinstance(contract, dict) and 'stage_result' in contract:
            return contract
    return None


def validate_delivery_round(call, rounds):
    """Compare known rounds of the same stage, including across review/fix.

    Full handoff, candidate, source-chain and sync verification remains with
    the caller. This only checks structured evidence already saved in a Run.
    """
    before = call.get('before')
    if before is not None:
        previous = before.get('stage_result', {})
        stage, round_ = previous.get('stage'), previous.get('round')
        require(type(round_) is int and round_ > 0, 'invalid before stage round')
        rounds[stage] = max(rounds.get(stage, 0), round_)
    contract = saved_contract(call.get('result'))
    if call.get('closed') and contract is not None:
        delivery = contract['stage_result']
        stage, round_ = delivery.get('stage'), delivery.get('round')
        require(stage == call['stage'] and type(round_) is int and round_ > rounds.get(stage, 0),
                'delivery round must advance its own stage')
        rounds[stage] = round_


def validate(data, display_issues=None):
    def presentation(ok, message, task):
        if display_issues is None:
            require(ok, message)
        elif not ok:
            display_issues.append({'slug': task['slug'], 'reason': message})
    require(isinstance(data, dict), 'Run must be an object')
    require(data.get('protocol') == PROTOCOL, PROTOCOL_ERROR)
    require(re.fullmatch(r'run-\d{8}-\d{2,}', data.get('run_id', '')), 'invalid run id')
    require(data.get('status') in ('running', 'interrupted', 'completed', 'stopped'), 'invalid Run state')
    require(data.get('execution_mode') == 'unattended', 'invalid execution mode')
    timestamp(data.get('created_at'))
    owner = data.get('executor', {})
    require(isinstance(owner.get('instance_id'), str) and owner['instance_id'].strip(), 'executor instance required')
    require(type(owner.get('generation')) is int and owner['generation'] >= 1, 'invalid executor generation')
    for key in ('host_id', 'thread_id', 'turn_id'):
        require(key in owner and (owner[key] is None or isinstance(owner[key], str)), 'missing executor identity field')
    timestamp(owner.get('claimed_at'))
    progress = owner.get('progress', {})
    require(timestamp(progress.get('at')) >= timestamp(owner['claimed_at']), 'progress predates claim')
    require(bool(progress.get('event')), 'progress event required')
    require(isinstance(data.get('ownership_history'), list), 'ownership history required')
    require(isinstance(data.get('reports'), list), 'reports must be an array')
    require(isinstance(data.get('preflight'), list) and data['preflight'], 'preflight evidence required')
    require(any(c.get('scope') == 'project' and c.get('status') == 'passed' for c in data['preflight']), 'project preflight required')
    for check in data['preflight']:
        require(check.get('scope') in ('project', 'task'), 'invalid preflight scope')
        require(check.get('status') in ('passed', 'deferred'), 'failed preflight cannot admit a Run')
        timestamp(check.get('at'))
        require(bool(check.get('evidence')) and isinstance(check.get('inputs'), dict), 'preflight source and inputs required')
        require(all(isinstance(path, str) and isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{64}', sha)
                    for path, sha in check['inputs'].items()), 'preflight inputs must carry SHA-256')
        if check['status'] == 'deferred':
            require(check['scope'] == 'task' and bool(check.get('produced_by')), 'only future stage outputs may be deferred')
    task_preflights = {c['slug'] for c in data['preflight'] if c['scope'] == 'task' and c['status'] == 'passed'
                       and isinstance(c.get('slug'), str)}
    tasks = data.get('tasks')
    require(isinstance(tasks, list) and tasks, 'empty Run')
    require(len({t['slug'] for t in tasks}) == len(tasks), 'duplicate slug')
    require(sum(t.get('state') == 'running' for t in tasks) <= 1, 'multiple running tasks')
    agent_identities = set()
    for task in tasks:
        require(type(task.get('revision')) is int and task['revision'] >= 1, 'invalid task revision')
        definition = task.get('definition', {})
        require(definition.get('protocol') == data['protocol'] and definition.get('slug') == task['slug'] and
                definition.get('revision') == task['revision'], 'definition protocol/identity mismatch')
        _, allowed = normalize_flow(definition.get('flow'), definition['protocol'])
        require(definition.get('preparation') == 'ready', 'definition must have passed Ready Gate')
        require(isinstance(task.get('start_action'), dict) and 'stage' in task['start_action'], 'start action required')
        require(task.get('start_action', {}).get('stage') in (*allowed, None), 'start action outside flow')
        validate_agents(task, agent_identities)
        require(task['slug'] in task_preflights, 'task preflight required')
        state = task.get('state')
        require(state in ('queued', 'running', 'completed', 'blocked', 'failed', 'skipped'), 'invalid task state')
        terminal = state in ('completed', 'blocked', 'failed', 'skipped')
        require((task.get('result') is not None) == terminal, 'result/state mismatch')
        if terminal:
            require(task['result'].get('state') == state, 'result state mismatch')
        calls = task.get('calls', [])
        require([c['id'] for c in calls] == list(range(1, len(calls) + 1)), 'invalid call sequence')
        require(task['budget']['calls'] == sum(c['charged']['calls'] for c in calls), 'budget mismatch')
        require(task['budget']['remediation'] == sum(c['charged']['remediation'] for c in calls), 'remediation budget mismatch')
        retries = {}
        rounds = {}
        previous_contract = None
        for call in calls:
            charged = call['charged']
            if previous_contract is not None:
                require(call.get('before') == previous_contract, 'before contract disagrees with last delivery')
            validate_charge(task, call)
            previous_contract = saved_contract(call.get('result')) if call.get('closed') else None
            if charged['retry_stage'] is not None:
                stage = charged['retry_stage']
                retries[stage] = retries.get(stage, 0) + 1
        require(task['budget']['retries'] == retries, 'retry budget mismatch')
        require(len(calls) <= 16 and task['budget']['remediation'] <= 3 and all(n <= 2 for n in retries.values()), 'budget limit exceeded')
        pending = [c for c in calls if not c.get('closed')]
        presentation(len(pending) <= 1, 'multiple unclosed calls', task)
        presentation(not pending or pending[0] is calls[-1], 'unclosed call must be last', task)
        require(state != 'queued' or not calls, 'queued task cannot contain calls')
        presentation(isinstance(task.get('checkpoint'), dict) and 'pending_call' in task['checkpoint'] and
                     task['checkpoint']['pending_call'] == (pending[0]['id'] if pending else None), 'checkpoint mismatch', task)
        if state == 'skipped':
            require(not calls and task['authorization_consumed'] is False and
                    task['budget'] == {'calls': 0, 'remediation': 0, 'retries': {}} and
                    task['checkpoint'] == {'pending_call': None, 'last_delivery': None} and
                    task['result'].get('last_delivery') is None, 'skipped task cannot contain execution evidence')
        for call in calls:
            presentation(call.get('stage') in allowed and
                         call.get('execution_mode') == 'unattended', 'invalid call stage/mode', task)
            presentation(call.get('dispatch') in ('prepared', 'dispatched'), 'invalid dispatch state', task)
            presentation(type(call.get('closed')) is bool, 'closed must be boolean', task)
            presentation(not call.get('closed') or call.get('result') is not None, 'closed call lacks result', task)
            try:
                validate_call_agent(task, call)
            except ValueError as exc:
                presentation(False, str(exc), task)
            validate_delivery_round(call, rounds)
        if state == 'completed':
            require(not pending, 'completed task has unclosed call')
    if data['status'] == 'completed':
        require(all(t['state'] not in ('queued', 'running') for t in tasks), 'completed Run has unfinished task')
    validate_append_history(data)


def agent_stopped(binding, observation, since=None):
    if not isinstance(observation, dict):
        return False
    if any(observation.get(k) != binding.get(k) for k in ('agent_id', 'host_id')):
        return False
    try:
        return (observation.get('state') == 'stopped' and observation.get('tools_stopped') is True
                and isinstance(observation.get('source'), str) and bool(observation['source'].strip())
                and timestamp(observation.get('observed_at')) >= timestamp(since or binding['created_at']))
    except (KeyError, TypeError, ValueError):
        return False


def validate_agents(task, identities):
    bindings = task.get('agents')
    require(isinstance(bindings, list), 'task agents must be an array')
    seen, latest = {}, {}
    for binding in bindings:
        require(isinstance(binding.get('id'), str) and binding['id'] and binding['id'] not in seen,
                'duplicate or missing agent binding id')
        require(binding.get('role') in ('worker', 'reviewer'), 'invalid agent role')
        require(isinstance(binding.get('agent_id'), str) and binding['agent_id'].strip(), 'actual agent id required')
        require('host_id' in binding and (binding['host_id'] is None or isinstance(binding['host_id'], str)),
                'agent host identity required')
        key = (binding['host_id'], binding['agent_id'])
        require(key not in identities, 'agent cannot be reused across bindings, tasks or roles')
        identities.add(key)
        timestamp(binding.get('created_at'))
        require(isinstance(binding.get('source'), str) and binding['source'].strip(), 'agent creation source required')
        previous = latest.get(binding['role'])
        require('supersedes' in binding and binding['supersedes'] == (previous['id'] if previous else None),
                'replacement must reference latest role binding')
        if previous:
            require(agent_stopped(previous, binding.get('stop_observation')), 'replacement requires stopped agent and tools')
            require(timestamp(binding['created_at']) >= timestamp(binding['stop_observation']['observed_at']),
                    'replacement predates stop observation')
        else:
            require(binding.get('stop_observation') is None, 'initial binding cannot invent replacement evidence')
        latest[binding['role']] = binding
        seen[binding['id']] = binding


def validate_call_agent(task, call):
    binding = next((b for b in task['agents'] if b['id'] == call.get('agent_ref')), None)
    require(binding is not None, 'call requires recorded agent binding')
    require(binding['role'] == ('reviewer' if call['stage'] == 'review' else 'worker'), 'call agent role mismatch')
    require(timestamp(call.get('prepared_at')) >= timestamp(binding['created_at']), 'call predates agent binding')
    evidence = call.get('dispatch_evidence')
    require('dispatch_evidence' in call, 'dispatch evidence field required')
    if evidence is not None:
        require(isinstance(evidence, dict) and evidence.get('agent_id') == binding['agent_id']
                and isinstance(evidence.get('source'), str) and evidence['source'].strip(), 'dispatch evidence identity/source mismatch')
        require(timestamp(evidence.get('at')) >= timestamp(call['prepared_at']), 'dispatch evidence predates intent')
    require(call['dispatch'] != 'dispatched' or evidence is not None, 'dispatched call requires evidence')


def validate_append_history(data):
    history = data.get('append_history')
    require(isinstance(history, list), 'append history required')
    appended, last_at = [], timestamp(data['created_at'])
    for event in history:
        at = timestamp(event.get('at'))
        require(at >= last_at, 'append time cannot regress')
        last_at = at
        require(isinstance(event.get('source'), str) and event['source'].strip(), 'append request source required')
        require(isinstance(event.get('tasks'), list) and event['tasks'], 'append batch required')
        appended.extend(event['tasks'])
    if appended:
        require(len(appended) < len(data['tasks']), 'append history cannot replace initial queue')
        require(appended == [{'slug': t['slug'], 'revision': t['revision']} for t in data['tasks'][-len(appended):]],
                'append history must match queue suffix')


def unfinished(data):
    if data.get('status') in ('running', 'interrupted'):
        return True
    if data.get('status') != 'stopped':
        return False
    return any(t['state'] in ('queued', 'running') for t in data['tasks'])

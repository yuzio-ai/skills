#!/usr/bin/env python3
"""Cadra 0.8 Run publication guard. Stdlib only; never dispatches work.

New Runs use JSON inside YAML Front Matter. Legacy YAML headers are inspected
read-only; full provenance and Cohestra contract checks remain the caller's job.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

STAGES = ('code', 'review', 'fix', 'validate')
PRESETS = {
    'implementation': ('code', 'review', 'fix', 'validate'),
    'bugfix': ('fix', 'review', 'validate'),
    'review-only': ('review',),
}


def normalize_flow(value):
    stages = PRESETS.get(value) if isinstance(value, str) else value
    require(isinstance(stages, (list, tuple)) and stages and
            all(isinstance(s, str) and s in STAGES for s in stages), 'invalid 0.8 flow')
    return stages[0], frozenset(stages)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('invalid JSON constant: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def timestamp(value):
    require(isinstance(value, str), 'timestamp required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timestamp must include timezone')
    return result


def split_document(raw):
    match = re.fullmatch(r'---\r?\n(.*?)\r?\n---(?:\r?\n(.*))?', raw.decode(), re.S)
    require(match is not None, 'missing Front Matter')
    return match[1], match[2] or ''


def header(raw):
    block, _ = split_document(raw)
    if block.lstrip().startswith('{'):
        result = read_json(block)
        require(isinstance(result, dict) and result.get('protocol') in ('0.6', '0.7', '0.8'),
                'unsupported or malformed Run header')
        if result['protocol'] == '0.6':
            result['legacy_closed'] = legacy_tasks_closed(result.get('tasks'))
        return result
    # Bounded historical block form only, not a general YAML parser. Never
    # derive control fields from nested definitions or quoted block content.
    result = {}
    lines = block.splitlines()
    require(all(not line or line[0].isspace() or line.startswith(('#', '- ')) or
                re.fullmatch(r'[A-Za-z_][\w-]*:[ ]*.*', line) for line in lines),
            'unsupported legacy root syntax')
    roots = [(i, m[1], m[2]) for i, line in enumerate(lines)
             if (m := re.fullmatch(r'([A-Za-z_][\w-]*):[ ]*(.*)', line))]
    require(len({key for _, key, _ in roots}) == len(roots), 'duplicate legacy root key')
    for key in ('protocol', 'run_id', 'status'):
        values = [value for _, name, value in roots if name == key]
        require(len(values) == 1, 'missing legacy control field')
        result[key] = legacy_scalar(values[0])
    require(result.get('protocol') == '0.6', 'unsupported or malformed Run header')
    result['legacy_closed'] = False
    sections = [i for i, key, value in roots if key == 'tasks' and not value]
    if not sections:
        return result
    start = sections[0] + 1
    end = next((i for i, _, _ in roots if i >= start), len(lines))
    items = lines[start:end]
    significant = [line for line in items if line.strip() and not line.lstrip().startswith('#')]
    if not significant:
        return result
    first = re.fullmatch(r'( {0,2})- slug:[ ]*(.*)', significant[0])
    if not first or len(first[1]) not in (0, 2):
        return result
    indent = len(first[1])
    tasks, task, in_result = [], None, False
    try:
        seen = set()
        for line in significant:
            depth = len(line) - len(line.lstrip(' '))
            if depth == indent:
                match = re.fullmatch(r' *- slug:[ ]*(.*)', line)
                require(match is not None, 'unsupported legacy task item')
                task = {'slug': legacy_scalar(match[1])}
                tasks.append(task)
                seen, in_result = {'slug'}, False
            elif depth == indent + 2:
                # Nested call lists may use indentless YAML sequences here.
                match = re.fullmatch(r' *([A-Za-z_][\w-]*):[ ]*(.*)', line)
                if not match:
                    require(line.lstrip().startswith('- '), 'unsupported legacy task field')
                    in_result = False
                    continue
                key, value = match.groups()
                require(key not in seen, 'duplicate legacy task key')
                seen.add(key)
                in_result = key == 'result'
                if key == 'state':
                    task['state'] = legacy_scalar(value)
                elif in_result:
                    require(not value, 'unsupported legacy result')
                    task['result'] = {}
                    result_keys = set()
            elif depth == indent + 4 and in_result:
                match = re.fullmatch(r' *([A-Za-z_][\w-]*):[ ]*(.*)', line)
                if not match:
                    require(line.lstrip().startswith('- '), 'unsupported legacy result field')
                    continue
                key, value = match.groups()
                require(key not in result_keys, 'duplicate legacy result key')
                result_keys.add(key)
                if key == 'state':
                    task['result']['state'] = legacy_scalar(value)
            else:
                require(depth > indent + 2, 'unsupported legacy indentation')
        result['legacy_closed'] = legacy_tasks_closed(tasks)
    except ValueError:
        # Unsupported/ambiguous structures remain read-only, never admission proof.
        pass
    return result


def legacy_scalar(value):
    match = re.fullmatch(r'''(?:([A-Za-z0-9_.-]+)|"([A-Za-z0-9_.-]+)"|'([A-Za-z0-9_.-]+)')''', value.strip())
    require(match is not None, 'unsupported legacy scalar')
    return next(part for part in match.groups() if part is not None)


def legacy_tasks_closed(tasks):
    if not isinstance(tasks, list) or not tasks or not all(isinstance(t, dict) for t in tasks):
        return False
    slugs = [t.get('slug') for t in tasks]
    return (all(isinstance(slug, str) and slug for slug in slugs) and len(set(slugs)) == len(slugs)
            and all(t.get('state') in ('completed', 'blocked', 'failed', 'skipped')
                    and isinstance(t.get('result'), dict) and t['result'].get('state') == t['state']
                    for t in tasks))


def current(raw):
    block, body = split_document(raw)
    require(block.lstrip().startswith('{'), '0.8 Run requires JSON Front Matter; legacy is read-only')
    data = read_json(block)
    require(isinstance(data, dict) and data.get('protocol') == '0.8', 'only 0.8 Runs may be written')
    validate(data)
    return data, body


def identity(owner):
    return {k: v for k, v in owner.items() if k != 'progress'}


def validate(data):
    require(isinstance(data, dict), 'Run must be an object')
    require(data.get('protocol') in ('0.7', '0.8'), 'unsupported Run protocol')
    modern = data['protocol'] == '0.8'
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
        if modern:
            _, allowed = normalize_flow(definition.get('flow'))
            require(definition.get('preparation') == 'ready', 'definition must have passed Ready Gate')
            require(isinstance(task.get('start_action'), dict) and 'stage' in task['start_action'], 'start action required')
            require(task.get('start_action', {}).get('stage') in (*allowed, None), 'start action outside flow')
            validate_agents(task, agent_identities)
        require(any(c.get('scope') == 'task' and c.get('slug') == task['slug'] and c.get('status') == 'passed'
                    for c in data['preflight']), 'task preflight required')
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
        for call in calls:
            charged = call['charged']
            require(charged['calls'] == 1 and type(charged['calls']) is int and
                    type(charged['remediation']) is int and charged['remediation'] in (0, 1), 'invalid budget charge')
            if charged.get('retry_stage'):
                stage = charged['retry_stage']
                retries[stage] = retries.get(stage, 0) + 1
        require(task['budget']['retries'] == retries, 'retry budget mismatch')
        require(len(calls) <= 16 and task['budget']['remediation'] <= 3 and all(n <= 2 for n in retries.values()), 'budget limit exceeded')
        pending = [c for c in calls if not c.get('closed')]
        require(len(pending) <= 1, 'multiple unclosed calls')
        require(not pending or pending[0] is calls[-1], 'unclosed call must be last')
        require(state != 'queued' or not calls, 'queued task cannot contain calls')
        require(task['checkpoint']['pending_call'] == (pending[0]['id'] if pending else None), 'checkpoint mismatch')
        for call in calls:
            require(call.get('stage') in (allowed if modern else ('need','design','code','review','fix','validate')) and
                    call.get('execution_mode') == 'unattended', 'invalid call stage/mode')
            require(call.get('dispatch') in ('prepared', 'dispatched'), 'invalid dispatch state')
            require(type(call.get('closed')) is bool, 'closed must be boolean')
            require(not call.get('closed') or call.get('result') is not None, 'closed call lacks result')
            if modern:
                validate_call_agent(task, call)
        if state == 'completed':
            require(not pending, 'completed task has unclosed call')
    if data['status'] == 'completed':
        require(all(t['state'] not in ('queued', 'running') for t in tasks), 'completed Run has unfinished task')
    if modern:
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


def descendants_stopped(data, observation):
    children = observation.get('children') if isinstance(observation, dict) else None
    bindings = [b for task in data['tasks'] for b in task.get('agents', [])]
    if not bindings:
        return children in (None, [])
    if not isinstance(children, list) or len(children) != len(bindings):
        return False
    for task in data['tasks']:
        for binding in task['agents']:
            times = [binding['created_at'], data['executor']['progress']['at']]
            for call in task['calls']:
                if call['agent_ref'] == binding['id']:
                    times.append(call['prepared_at'])
                    if call.get('dispatch_evidence'):
                        times.append(call['dispatch_evidence']['at'])
            if sum(agent_stopped(binding, child, max(times, key=timestamp)) for child in children) != 1:
                return False
    return True


def activity(owner, observation):
    """No elapsed-time heuristic. Observation must concern this exact instance."""
    if not isinstance(observation, dict) or any(observation.get(k) != owner.get(k) for k in ('instance_id', 'generation')):
        return 'unknown'
    if observation.get('source_kind') not in ('host', 'human_handoff'):
        return 'unknown'
    for key in ('host_id', 'thread_id', 'turn_id'):
        if key not in observation or observation[key] != owner.get(key):
            return 'unknown'
        if observation['source_kind'] == 'host' and not owner.get(key):
            return 'unknown'
    try:
        if timestamp(observation['observed_at']) < timestamp(owner['progress']['at']):
            return 'unknown'
    except (KeyError, TypeError, ValueError):
        return 'unknown'
    if not isinstance(observation.get('source'), str) or not observation['source'].strip():
        return 'unknown'
    if observation.get('state') == 'active':
        return 'active'
    if observation.get('state') == 'stopped' and observation.get('tools_stopped') is True:
        return 'stopped'
    return 'unknown'


@contextmanager
def writer_lock(directory):
    """Short-lived OS lock; kernel releases on process exit. Never unlink lock."""
    import fcntl
    path = directory / '.writer.lock'
    require(not path.is_symlink(), 'linked writer lock')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another Run writer is active') from None
        yield
    finally:
        os.close(fd)


def unfinished(data):
    if data.get('status') in ('running', 'interrupted'):
        return True
    if data.get('status') != 'stopped':
        return False
    if data.get('protocol') == '0.6':
        return not (data.get('legacy_closed') or legacy_tasks_closed(data.get('tasks')))
    return any(t['state'] in ('queued', 'running') for t in data['tasks'])


def validate_update(old, new):
    for key in ('protocol', 'run_id', 'created_at', 'execution_mode', 'skill_version'):
        require(old.get(key) == new.get(key), 'Run identity is frozen')
    require([t['slug'] for t in old['tasks']] == [t['slug'] for t in new['tasks']], 'queue is frozen')
    require(old['append_history'] == new['append_history'], 'append history changes require append operation')
    require(sum(len(b['calls']) - len(a['calls']) for a, b in zip(old['tasks'], new['tasks'])) <= 1,
            'publish one call intent at a time')
    for before, after in zip(old['tasks'], new['tasks']):
        for key in ('slug', 'revision', 'previous_run', 'definition', 'start_action'):
            require(before.get(key) == after.get(key), 'task definition/start is frozen')
        if before['state'] in ('completed', 'blocked', 'failed', 'skipped'):
            require(before == after, 'terminal task history is immutable')
        require(len(after['calls']) >= len(before['calls']), 'cannot delete calls')
        if before['state'] == 'running':
            require(after['state'] != 'queued', 'running task cannot return to queued')
        require(after['agents'][:len(before['agents'])] == before['agents'], 'agent bindings are append-only')
        require(len(after['agents']) <= len(before['agents']) + 1, 'publish one agent binding at a time')
        if len(after['agents']) > len(before['agents']):
            require(all(c['closed'] for c in before['calls']), 'cannot replace or bind agent while call is pending')
            require(after['calls'] == before['calls'], 'persist binding separately before preparing call')
            for added in after['agents'][len(before['agents']):]:
                if added['supersedes']:
                    previous = next(b for b in before['agents'] if b['id'] == added['supersedes'])
                    times = [previous['created_at'], old['executor']['progress']['at']]
                    for call in before['calls']:
                        if call['agent_ref'] == previous['id']:
                            times.append(call['prepared_at'])
                            if call.get('dispatch_evidence'):
                                times.append(call['dispatch_evidence']['at'])
                    require(agent_stopped(previous, added['stop_observation'], max(times, key=timestamp)),
                            'replacement stop proof predates latest agent activity')
        if len(after['calls']) > len(before['calls']):
            require(all(c['closed'] for c in before['calls']), 'resolve pending call before appending intent')
            require(after['state'] == 'running', 'new call requires running task')
            call = after['calls'][-1]
            binding = next((b for b in before['agents'] if b['id'] == call.get('agent_ref')), None)
            require(binding is not None and binding == next(b for b in reversed(before['agents']) if b['role'] == binding['role']),
                    'new call must use latest persisted role binding')
            require(call.get('dispatch') == 'prepared' and call.get('closed') is False and call.get('result') is None,
                    'new call must first persist an unclosed prepared intent')
            require(call.get('dispatch_evidence') is None, 'new intent cannot invent dispatch evidence')
        require(not before.get('authorization_consumed') or after.get('authorization_consumed'), 'authorization consumption cannot regress')
        for a, b in zip(before['calls'], after['calls']):
            if a.get('closed'):
                require(a == b, 'closed call is immutable')
            else:
                require({k: v for k, v in a.items() if k not in ('dispatch', 'closed', 'result', 'dispatch_evidence')} ==
                        {k: v for k, v in b.items() if k not in ('dispatch', 'closed', 'result', 'dispatch_evidence')}, 'call intent is immutable')
                require(a.get('dispatch_evidence') is None or a['dispatch_evidence'] == b.get('dispatch_evidence'),
                        'dispatch evidence is immutable once recorded')
                require(not (a['dispatch'] == 'dispatched' and b['dispatch'] == 'prepared'), 'dispatch cannot regress')
    require(new['preflight'][:len(old['preflight'])] == old['preflight'], 'preflight evidence is append-only')


def fresh_task(task):
    return (task['state'] == 'queued' and not task['calls'] and not task['agents']
            and task['result'] is None and task['authorization_consumed'] is False
            and task['budget'] == {'calls': 0, 'remediation': 0, 'retries': {}}
            and task['checkpoint'] == {'pending_call': None, 'last_delivery': None})


def validate_append(old, new):
    require(old['status'] == new['status'] == 'running', 'append requires running Run')
    mutable = {'tasks', 'preflight', 'append_history'}
    require({k:v for k,v in old.items() if k not in mutable} ==
            {k:v for k,v in new.items() if k not in mutable}, 'append cannot change execution or ownership')
    count = len(old['tasks'])
    require(new['tasks'][:count] == old['tasks'] and len(new['tasks']) > count,
            'append may only extend queue suffix')
    added = new['tasks'][count:]
    require(all(fresh_task(t) for t in added), 'appended tasks must be fresh queued entries')
    priority = {'high': 0, 'medium': 1, 'low': 2}
    require(all(t['definition'].get('priority', 'medium') in priority for t in added), 'invalid task priority')
    require(added == sorted(added, key=lambda t: (priority[t['definition'].get('priority', 'medium')], t['slug'])),
            'append batch must follow priority/slug order')
    checks = len(old['preflight'])
    require(new['preflight'][:checks] == old['preflight'], 'append cannot change existing preflight')
    slugs = {t['slug'] for t in added}
    require(all(c['scope'] == 'task' and c.get('slug') in slugs for c in new['preflight'][checks:]),
            'append preflight must concern new tasks only')
    require(all(any(c.get('slug') == slug and c['status'] == 'passed' for c in new['preflight'][checks:])
                for slug in slugs), 'each appended task requires new admission evidence')
    require(len(new['append_history']) == len(old['append_history']) + 1 and
            new['append_history'][:-1] == old['append_history'], 'append requires one immutable batch record')
    require(new['append_history'][-1]['tasks'] == [{'slug': t['slug'], 'revision': t['revision']} for t in added],
            'append record does not match batch')


def publish(path, proposed, expected, instance, generation, mode='update', observation=None):
    path = Path(path).absolute()
    require(path.parent.name == 'runs' and path.parent.parent.name == 'cadra' and
            path.parent.parent.parent.name == '.yuzio', 'expected project .yuzio/cadra/runs path')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'linked Run path')
    new, new_body = current(proposed)
    require(path.name == new['run_id'] + '.md', 'Run filename mismatch')
    with writer_lock(path.parent):
        raw = path.read_bytes() if path.exists() else None
        require((digest(raw) if raw is not None else None) == expected, 'Run changed; reread before writing')
        if mode == 'create':
            require(raw is None, 'Run already exists')
            require(new['executor']['generation'] == 1 and not new['ownership_history'], 'new Run cannot invent ownership history')
            require(new['status'] == 'running' and all(fresh_task(t) for t in new['tasks']), 'new Run must start queued')
            require(new['append_history'] == [], 'new Run cannot invent append history')
            for other in path.parent.glob('run-*.md'):
                if '-report-' in other.name:
                    continue
                require(not other.is_symlink(), 'linked historical Run')
                data = header(other.read_bytes())
                require(data.get('protocol') in ('0.6', '0.7', '0.8') and data.get('status') in ('running','interrupted','completed','stopped'), 'unknown historical Run')
                if data['protocol'] in ('0.7', '0.8'):
                    validate(data)
                elif data['status'] == 'completed':
                    require(data.get('legacy_closed') or legacy_tasks_closed(data.get('tasks')),
                        'legacy closure cannot be verified from this header form')
                require(not unfinished(data), 'unfinished or unverified legacy stopped Run; do not create another')
        else:
            require(raw is not None, 'missing Run')
            old, old_body = current(raw)
            if mode == 'append':
                require(new_body == old_body, 'append cannot rewrite Run body')
                validate_append(old, new)
            else:
                validate_update(old, new)
            if mode == 'append':
                pass
            elif mode == 'takeover':
                require(new_body == old_body, 'takeover cannot rewrite Run body')
                require(unfinished(old), 'closed Run cannot be taken over')
                require(activity(old['executor'], observation) == 'stopped', 'executor or tools not confirmed stopped')
                require(descendants_stopped(old, observation), 'child agents or tools not confirmed stopped')
                require(new['executor']['generation'] == old['executor']['generation'] + 1 and
                        new['executor']['instance_id'] != old['executor']['instance_id'], 'takeover requires new identity and next generation')
                require(timestamp(new['executor']['claimed_at']) >= timestamp(observation['observed_at']), 'takeover predates stop evidence')
                require(all(timestamp(new['executor']['claimed_at']) >= timestamp(child['observed_at'])
                            for child in observation.get('children', [])), 'takeover predates child stop evidence')
                require({k:v for k,v in old.items() if k not in ('executor','ownership_history')} ==
                        {k:v for k,v in new.items() if k not in ('executor','ownership_history')}, 'takeover must not replay or change work')
                require(new['ownership_history'] == old['ownership_history'] + [
                    {'previous': old['executor'], 'observation': observation}], 'takeover history must preserve evidence')
            elif mode == 'report':
                require({k:v for k,v in old.items() if k != 'reports'} == {k:v for k,v in new.items() if k != 'reports'}, 'report only appends links')
                require(split_document(proposed)[1] == old_body, 'report cannot rewrite Run body')
            else:
                require(mode == 'update' and unfinished(old), 'closed Run is read-only except report links')
                require(identity(old['executor']) == identity(new['executor']), 'executor changed; use takeover')
                require(old['ownership_history'] == new['ownership_history'], 'ownership history is immutable')
                require(timestamp(new['executor']['progress']['at']) >= timestamp(old['executor']['progress']['at']), 'progress cannot regress')
            require(new.get('reports', [])[:len(old.get('reports', []))] == old.get('reports', []), 'report links are append-only')
        if mode not in ('report', 'append'):
            require((instance, generation) == (new['executor']['instance_id'], new['executor']['generation']), 'writer does not own Run')
        fd, temporary = tempfile.mkstemp(prefix='.run-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as file:
                file.write(proposed)
                file.flush()
                os.fsync(file.fileno())
            require((path.read_bytes() if path.exists() else None) == raw, 'Run changed during publication')
            os.replace(temporary, path)
            require(path.read_bytes() == proposed, 'Run readback failed; stop and inspect')
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return digest(proposed)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('mode', choices=('inspect', 'create', 'update', 'takeover', 'report', 'append'))
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--proposal', type=Path)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--instance')
    parser.add_argument('--generation', type=int)
    parser.add_argument('--observation', type=Path)
    args = parser.parse_args()
    try:
        observation = read_json(args.observation.read_text()) if args.observation else None
        if args.mode == 'inspect':
            raw = args.run.read_bytes()
            data = header(raw)
            require(data.get('status') in ('running', 'interrupted', 'completed', 'stopped'), 'unknown Run state')
            result = {'sha256': digest(raw), 'protocol': data['protocol'], 'status': data.get('status'), 'activity': 'unknown'}
            if data['protocol'] in ('0.7', '0.8'):
                validate(data)
                result['executor'] = data['executor']
                result['activity'] = activity(data['executor'], observation)
                if data['protocol'] == '0.8' and result['activity'] == 'stopped' and not descendants_stopped(data, observation):
                    result['activity'] = 'unknown'
            print(json.dumps(result, ensure_ascii=False))
        else:
            require(args.proposal is not None, 'proposal required')
            print(publish(args.run, args.proposal.read_bytes(), args.expected_sha256,
                          args.instance, args.generation, args.mode, observation))
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()

"""Deterministic Cadra 0.11 scheduling journal. Stdlib; no tools or dispatch.

Run.scheduler.events is the source of resource decisions. A view is derived,
never stored beside it. Observations and project input hashes are caller evidence,
not proof supplied by this module. Validate transitions before granting any tool.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import unicodedata

TERMINAL = {'completed', 'blocked', 'failed', 'skipped'}
WAIT_KINDS = {'files', 'verification', 'agent', 'finalization'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def at(value):
    need(isinstance(value, str), 'scheduler timestamp required')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(stamp.tzinfo is not None, 'scheduler timestamp requires timezone')
    return stamp


def path_key(value):
    need(isinstance(value, str) and value and '\\' not in value and '\x00' not in value,
         'invalid scope path')
    p = PurePosixPath(value)
    need(not p.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/')),
         'scope must be a canonical project relative path')
    need(p.parts[0].casefold() not in ('.git', '.yuzio'), 'process/private paths are not business scope')
    # Conservative across case-sensitive and case-insensitive installations.
    return unicodedata.normalize('NFC', value).casefold()


def scope(value):
    need(isinstance(value, dict) and set(value) == {'mode', 'files', 'dirs'}, 'scope shape required')
    need(value['mode'] in ('parallel', 'exclusive'), 'invalid scope mode')
    for field in ('files', 'dirs'):
        need(isinstance(value[field], list), 'scope paths must be arrays')
        keys = [path_key(p) for p in value[field]]
        need(len(keys) == len(set(keys)), 'scope contains path aliases')
    return value


def validate_paths(root, value):
    """Check declared paths and every existing descendant of directory leases."""
    root = Path(root).resolve()
    scope(value)
    seen = {}

    def check(p):
        need(p.resolve().is_relative_to(root), 'scope escapes project')
        need(not any(q.is_symlink() for q in (p, *p.parents) if q != root and q.is_relative_to(root)),
             'scope symlink alias')
        if p.exists() and p.is_file():
            info = p.stat()
            need(info.st_nlink == 1, 'scope hardlink alias')
            key = (info.st_dev, info.st_ino)
            canonical = unicodedata.normalize('NFC', p.relative_to(root).as_posix()).casefold()
            need(key not in seen or seen[key] == canonical, 'scope filesystem alias')
            seen[key] = canonical

    for kind in ('files', 'dirs'):
        for name in value[kind]:
            p = root / name
            check(p)
            if p.exists():
                need(p.is_dir() if kind == 'dirs' else p.is_file(),
                     'directory scope and file scope must match actual path kind')
            if kind == 'dirs' and p.is_dir():
                for child in p.rglob('*'):
                    check(child)


def overlap(a, b):
    scope(a); scope(b)
    if 'exclusive' in (a['mode'], b['mode']):
        return True
    left = set(map(path_key, a['files'] + a['dirs']))
    right = set(map(path_key, b['files'] + b['dirs']))
    # A future regular file cannot also be another path's directory ancestor.
    return any(p == q or p.startswith(q + '/') or q.startswith(p + '/') for p in left for q in right)


def covers(outer, inner):
    scope(outer); scope(inner)
    if outer['mode'] == 'exclusive':
        return True
    if inner['mode'] == 'exclusive':
        return False
    dirs = list(map(path_key, outer['dirs']))
    for kind in ('files', 'dirs'):
        exact = set(map(path_key, outer[kind]))
        for p in map(path_key, inner[kind]):
            if p not in exact and not any(p == d or p.startswith(d + '/') for d in dirs):
                return False
    return True


def admission(task):
    value = task['definition'].get('ready_scope')
    need(isinstance(value, dict) and set(value) == {'revision', 'scope', 'inputs'}, 'ready scope required')
    need(value['revision'] == task['revision'], 'ready scope revision mismatch')
    scope(value['scope']); hashes(value['inputs'])
    return value['scope']


def hashes(value):
    need(isinstance(value, dict), 'input hashes required')
    normalized = {}
    for p, sha in value.items():
        key = path_key(p)
        need(key not in normalized, 'input hashes contain path aliases')
        need(sha is None or isinstance(sha, str) and len(sha) == 64
             and all(c in '0123456789abcdef' for c in sha), 'invalid input hash')
        normalized[key] = sha
    return normalized


def request_key(value, slug):
    prefix = '.yuzio/cohestra/handoffs/' + slug + '/scratch/resources/'
    need(isinstance(value, str) and value.startswith(prefix) and '\\' not in value
         and '\x00' not in value and all(c not in ('', '.', '..') for c in value.split('/')),
         'canonical request path required')
    return unicodedata.normalize('NFC', value).casefold()


def candidate(value):
    need(isinstance(value, dict) and isinstance(value.get('snapshot'), str) and value['snapshot'],
         'fixed candidate required')
    sha = value.get('sha256')
    need(isinstance(sha, str) and len(sha) == 64 and all(c in '0123456789abcdef' for c in sha),
         'candidate digest required')
    hashes(value.get('inputs'))


def select_group(data):
    tasks = [t for t in data['tasks'] if t['state'] == 'queued']
    if not tasks:
        return []
    first = tasks[0]
    result = [first['slug']]
    for t in tasks[1:]:
        if not overlap(admission(first), admission(t)):
            result.append(t['slug']); break
    return result


def initial():
    return {'events': []}


def _empty():
    return {'groups': [], 'group': None, 'leases': {}, 'stopped': {}, 'requests': [],
            'active': None, 'scope': {}, 'next_seq': 1, 'windows': [], 'invalidations': [],
            'consumed_requests': {}}


def _task(data, slug):
    t = next((t for t in data['tasks'] if t['slug'] == slug), None)
    need(t is not None, 'scheduler references missing task')
    return t


def _stop(data, event, view):
    t = _task(data, event['slug']); proof = event.get('stop')
    need(isinstance(proof, dict) and proof.get('tools_stopped') is True and proof.get('source'),
         'confirmed stopped tools required before release')
    when = at(proof.get('observed_at'))
    call_id = event.get('call_id')
    need(call_id is None or type(call_id) is int and call_id > 0, 'invalid wait call id')
    if call_id is not None:
        c = next((c for c in t['calls'] if c['id'] == call_id), None)
        need(c is not None, 'wait call not found')
        b = next(b for b in t['agents'] if b['id'] == c['agent_ref'])
        need(proof.get('agent_id') == b['agent_id'] and proof.get('host_id') == b['host_id'],
             'release observation agent mismatch')
        since = (c.get('dispatch_evidence') or {}).get('at', c['prepared_at'])
        need(when >= at(since), 'release observation predates call')
    else:
        need(proof.get('agent_id') is None, 'pre-dispatch release cannot invent agent')
    previous = [r for r in view['requests'] if r['slug'] == event['slug'] and r.get('granted_at')]
    if previous:
        need(when >= max(at(r['granted_at']) for r in previous), 'release observation predates resource grant')
    need(at(event['at']) >= when, 'release event predates observation')
    return proof


def executable(view, request):
    if request['status'] != 'waiting' or request['kind'] == 'finalization':
        return False
    group = view['group']
    if request['kind'] == 'agent' and not request.get('available', False):
        return False
    if request['kind'] == 'verification':
        return group['phase'] == 'verifying' and view['active'] is None
    return (group['phase'] == 'working' and view['active'] is None
            and not any(overlap(request['scope'], s) for slug, s in view['leases'].items()
                        if slug != request['slug']))


def next_request(view):
    return next((r['seq'] for r in view['requests'] if executable(view, r)), None)


def _step(view, event, data):
    need(isinstance(event, dict) and event.get('kind') in {
        'group', 'wait', 'grant', 'finish', 'barrier', 'window_end', 'close', 'invalidate', 'abort', 'agent_ready'},
        'invalid scheduling event')
    at(event.get('at'))
    kind = event['kind']
    if kind == 'group':
        need(view['group'] is None or view['group']['phase'] == 'closed', 'fixed group cannot be refilled')
        if view['group']:
            need(all(_task(data, s)['state'] in TERMINAL for s in view['group']['members']),
                 'publish previous group results before next group')
        members = event.get('members')
        need(isinstance(members, list) and 1 <= len(members) <= 2 and len(set(members)) == len(members),
             'group requires one or two distinct tasks')
        used = {s for g in view['groups'] for s in g['members']}
        need(not used.intersection(members), 'task cannot enter another group')
        scopes = {s: deepcopy(admission(_task(data, s))) for s in members}
        need(len(members) == 1 or not overlap(*scopes.values()), 'group scopes overlap')
        before = event.get('before')
        need(isinstance(before, dict) and set(before) == set(members), 'group before images required')
        need(isinstance(event.get('before_refs'), dict) and set(event['before_refs']) == set(members)
             and all(isinstance(x, str) and x for x in event['before_refs'].values()), 'before snapshot references required')
        for s in members:
            hashes(before[s])
        g = {'id': len(view['groups']) + 1, 'members': members, 'phase': 'working', 'candidate': None}
        view['groups'].append(g); view['group'] = g
        view['leases'] = scopes; view['scope'] = deepcopy(scopes); view['stopped'] = {}
        return
    g = view['group']
    need(g is not None and g['phase'] != 'closed', 'no open group')
    if kind == 'abort':
        slug = event.get('slug'); need(slug in g['members'], 'abort outside current group')
        proof = _stop(data, event, view)
        need(event.get('state') in ('failed', 'blocked') and event.get('source') and event.get('reason'),
             'abort requires actual failure/stop evidence')
        view['leases'].pop(slug, None); view['stopped'][slug] = proof
        for r in view['requests']:
            if r['slug'] == slug and r['status'] in ('waiting', 'granted'):
                r['status'] = 'aborted'; r['source'] = event['source']
                if view['active'] == r['seq']: view['active'] = None
        # No outcome is invented for a previously granted command. Keep its
        # request, original call and actual abort evidence for recovery.
        return
    if kind == 'wait':
        slug = event.get('slug'); need(slug in g['members'], 'wait outside current group')
        need(view['active'] is None or view['requests'][view['active'] - 1]['slug'] != slug,
             'finish verification before waiting again')
        pending = [r for r in view['requests'] if r['slug'] == slug and r['status'] == 'waiting']
        # A finished stage may only have process handoff left. Retire its
        # unused post-verification write continuation without granting writes,
        # including when a peer's failure has stopped further dispatch.
        if pending and event.get('resource') == 'finalization':
            need(len(pending) == 1 and _finished_continuation(view, pending[0], slug, event.get('call_id')),
                 'task already has waiting request')
            task = _task(data, slug)
            call = next((c for c in task['calls'] if c['id'] == event.get('call_id')), None)
            need(call is not None and call['closed'], 'finalization cannot hide pending call')
            pending[0]['status'] = 'cancelled'
        else:
            need(not pending, 'task already has waiting request')
        need(event.get('resource') in WAIT_KINDS, 'invalid wait reason')
        stop = _stop(data, event, view)
        task = _task(data, slug)
        call = next((c for c in task['calls'] if c['id'] == event.get('call_id')), None)
        if call and (not call['closed'] or 'request' in event):
            request = event.get('request', {})
            body = request.get('body', {})
            need(isinstance(request.get('path'), str), 'immutable task request path required')
            key = request_key(request['path'], slug)
            need(isinstance(body, dict) and type(body.get('generation')) is int
                 and type(body.get('call_id')) is int, 'resource request identity requires integers')
            need(key not in view['consumed_requests'], 'resource request already consumed')
            view['consumed_requests'][key] = event['id']
            need(request.get('sha256') == hashlib.sha256(json.dumps(body, ensure_ascii=False,
                sort_keys=True, separators=(',', ':')).encode()).hexdigest(), 'resource request digest mismatch')
            need(all(body.get(k) == v for k, v in dict(run_id=data['run_id'], generation=event['generation'],
                slug=slug, call_id=call['id'], agent_ref=call['agent_ref'], resource=event['resource'],
                scope=event['scope'], candidate=event['candidate']).items()), 'resource request binding mismatch')
            if event['resource'] == 'verification':
                need(body.get('argv') == event.get('argv'), 'verification request argv mismatch')
        wanted = scope(event.get('scope'))
        need(covers(wanted, view['scope'][slug]), 'runtime scope cannot shrink')
        candidate(event.get('candidate'))
        if event['resource'] == 'verification':
            need(call is not None and call['dispatch'] == 'dispatched',
                 'verification needs original dispatched pending stage')
            need(isinstance(event.get('argv'), list) and event['argv'] and
                 all(isinstance(x, str) and x for x in event['argv']), 'verification argv required')
        if event['resource'] == 'agent':
            need(call is None or call['closed'], 'role wait cannot replace pending stage')
            need(event.get('stage') in ('code', 'review', 'fix', 'validate'), 'role wait stage required')
        if event['resource'] == 'finalization':
            need(event.get('call_id') is None or _task(data, slug)['calls'][event['call_id'] - 1]['closed'],
                 'finalization cannot hide pending call')
        r = {'seq': view['next_seq'], 'slug': slug, 'call_id': event.get('call_id'),
             'kind': event['resource'], 'scope': deepcopy(wanted), 'candidate': event['candidate'],
             'status': 'waiting', 'at': event['at'], 'generation': event['generation']}
        if event['resource'] == 'agent':
            r.update(available=False, stage=event['stage'])
        view['requests'].append(r); view['next_seq'] += 1
        view['scope'][slug] = deepcopy(wanted); view['leases'].pop(slug, None); view['stopped'][slug] = stop
    elif kind == 'agent_ready':
        seq = event.get('seq')
        need(type(seq) is int and 1 <= seq <= len(view['requests']), 'unknown role request')
        r = view['requests'][seq - 1]
        need(r['kind'] == 'agent' and r['status'] == 'waiting' and not r['available'],
             'role request is not awaiting availability')
        binding = next((b for b in _task(data, r['slug'])['agents'] if b['id'] == event.get('agent_ref')), None)
        need(binding is not None and binding['role'] == ('reviewer' if r['stage'] == 'review' else 'worker')
             and event.get('source'), 'available role needs actual matching binding/source')
        r.update(available=True, agent_ref=binding['id'])
    elif kind == 'grant':
        seq = event.get('seq')
        need(type(seq) is int and seq == next_request(view), 'grant must follow executable FIFO')
        r = view['requests'][seq - 1]
        # Request creation generation is not execution provenance: finish or
        # a newly recorded wait may carry an observation from the old owner.
        owners = [h['previous'] for h in data['ownership_history']] + [data['executor']]
        owner = next(o for o in owners if o['generation'] == event['generation'])
        proof = view['stopped'].get(r['slug'])
        if event.get('stop') is not None or proof is None or at(proof['observed_at']) < at(owner['claimed_at']):
            proof = _stop(data, {**event, 'slug': r['slug'], 'call_id': r['call_id']}, view)
        need(at(proof['observed_at']) >= at(owner['claimed_at']),
             'cross-generation grant requires a new stop observation')
        r.update(status='granted', granted_at=event['at'])
        if r['kind'] == 'verification':
            need(event.get('candidate') == g['candidate'], 'grant candidate differs from stable window')
            view['active'] = seq
        else:
            hashes(event.get('before'))
            need(isinstance(event.get('before_ref'), str) and event['before_ref'], 'resume before snapshot reference required')
            r['before'] = event['before']; view['leases'][r['slug']] = deepcopy(r['scope'])
            view['stopped'].pop(r['slug'], None)
    elif kind == 'finish':
        seq = event.get('seq')
        need(type(seq) is int and view['active'] == seq, 'no matching active verification')
        r = view['requests'][seq - 1]
        stop = _stop(data, {**event, 'slug': r['slug'], 'call_id': r['call_id']}, view)
        view['stopped'][r['slug']] = stop
        need(event.get('outcome') in ('passed', 'failed', 'inconclusive', 'interrupted') and event.get('source'),
             'verification outcome evidence required')
        r.update(status='done', finished_at=event['at'], outcome=event['outcome'], source=event['source'])
        view['active'] = None
        # The command is finished, but production writes remain paused. A
        # continuation joins FIFO and can only run after the window drains.
        view['requests'].append({'seq': view['next_seq'], 'slug': r['slug'], 'call_id': r['call_id'],
            'kind': 'files', 'scope': deepcopy(view['scope'][r['slug']]), 'candidate': g['candidate'],
            'resume_of': r['seq'],
            'status': 'waiting', 'at': event['at'], 'generation': event['generation']})
        view['next_seq'] += 1
    elif kind == 'barrier':
        need(g['phase'] == 'working' and not view['leases'] and view['active'] is None,
             'all writes must stop before verification')
        need(set(g['members']) <= set(view['stopped']), 'every member requires stopped observation')
        need(not any(executable(view, r) for r in view['requests'] if r['kind'] != 'verification'),
             'executable file/agent request precedes barrier')
        need(any(r['kind'] == 'verification' and r['status'] == 'waiting' for r in view['requests']),
             'verification barrier requires requests')
        candidate(event.get('candidate'))
        g['phase'] = 'verifying'; g['candidate'] = event['candidate']
        view['windows'].append({'group': g['id'], 'at': event['at'], 'candidate': event['candidate']})
    elif kind == 'window_end':
        need(g['phase'] == 'verifying' and view['active'] is None and
             not any(r['kind'] == 'verification' and r['status'] == 'waiting' for r in view['requests']),
             'drain verification queue before writing')
        g['phase'] = 'working'
    elif kind == 'invalidate':
        slug = event.get('slug'); need(slug in g['members'], 'invalidation outside group')
        old = next((r for r in reversed(view['requests']) if r['slug'] == slug and
                    r['kind'] == 'finalization' and r['status'] == 'waiting'), None)
        need(old is not None, 'invalidation requires provisional completion')
        candidate(event.get('candidate'))
        changed = affected(old['candidate']['inputs'], event['candidate']['inputs'])
        need(changed and event.get('paths') == changed and event.get('source'), 'candidate change evidence required')
        stage = event.get('stage')
        flow = _task(data, slug)['definition']['flow']
        allowed = {'code': ('code', 'review', 'fix', 'validate'), 'fix': ('fix', 'review', 'validate'),
                   'review': ('review', 'fix', 'validate')}.get(flow, flow) if isinstance(flow, str) else flow
        need(stage in ('review', 'validate') and stage in allowed, 'candidate refresh outside allowed flow')
        old['status'] = 'invalidated'; view['invalidations'].append(deepcopy(event))
        view['requests'].append({'seq': view['next_seq'], 'slug': slug, 'call_id': old['call_id'],
            'kind': 'files', 'scope': deepcopy(view['scope'][slug]), 'candidate': event['candidate'],
            'status': 'waiting', 'at': event['at'], 'generation': event['generation']})
        view['next_seq'] += 1
    elif kind == 'close':
        need(view['active'] is None and g['phase'] == 'working', 'close only outside verification')
        need(not view['leases'], 'release all files before group close')
        candidate(event.get('candidate')); final = event['candidate']
        for slug in g['members']:
            t = _task(data, slug)
            requests = [r for r in view['requests'] if r['slug'] == slug and r['status'] == 'waiting']
            if t['state'] in ('failed', 'blocked', 'skipped'):
                need(event.get('residuals', {}).get(slug) and slug in view['stopped'],
                     'failed member needs stopped tools and safe residual evidence')
                for r in requests: r['status'] = 'cancelled'
            else:
                need(len(requests) == 1 and requests[0]['kind'] == 'finalization',
                     'each successful member must await finalization')
                need(not affected(requests[0]['candidate']['inputs'], final['inputs']),
                     'final candidate invalidates task evidence')
                need(all(c['closed'] for c in t['calls']), 'cannot finalize pending stage')
                requests[0]['status'] = 'done'
        g['phase'] = 'closed'; g['candidate'] = final


def affected(old, new):
    """Only dependencies recorded by the old evidence; unrelated new files do not invalidate it."""
    hashes(old)
    current = hashes(new)
    # Missing evidence is distinct from an explicit nonexistence marker.
    return sorted(p for p, sha in old.items() if path_key(p) not in current or current[path_key(p)] != sha)


def replay(data):
    journal = data.get('scheduler')
    need(isinstance(journal, dict) and set(journal) == {'events'} and isinstance(journal['events'], list),
         'scheduler journal required')
    view = _empty(); previous = at(data['created_at']); previous_generation = 1
    for i, event in enumerate(journal['events']):
        need(type(event.get('id')) is int and event['id'] == i + 1, 'scheduler event ids must be contiguous')
        need(type(event.get('generation')) is int and 1 <= event['generation'] <= data['executor']['generation'],
             'invalid scheduler generation')
        need(event['generation'] >= previous_generation, 'scheduler generation regressed')
        previous_generation = event['generation']
        owners = [h['previous'] for h in data['ownership_history']] + [data['executor']]
        owner = next((o for o in owners if o['generation'] == event['generation']), None)
        need(owner is not None, 'scheduler generation has no executor provenance')
        stamp = at(event.get('at')); need(stamp >= previous, 'scheduler time regressed'); previous = stamp
        need(stamp >= at(owner['claimed_at']), 'scheduler event predates generation claim')
        _step(view, event, data)
    return view


def validate(data):
    for t in data['tasks']: admission(t)
    view = replay(data); g = view['group']
    members = g['members'] if g else []
    for t in data['tasks']:
        slug, state = t['slug'], t['state']
        if state in ('running', 'waiting'):
            need(slug in members, 'active task outside fixed group')
        pending = [r for r in view['requests'] if r['slug'] == slug and (r['status'] == 'waiting' or
                   g and g['phase'] == 'closed' and r['kind'] == 'finalization' and r['status'] == 'done')]
        if state == 'waiting':
            need(slug not in view['leases'] and (view['active'] is None or
                 view['requests'][view['active'] - 1]['slug'] != slug), 'waiting task must release every resource')
            need(len(pending) == 1, 'waiting task needs one checkpoint')
        if state == 'running':
            need(slug in view['leases'] or view['active'] is not None and
                 view['requests'][view['active'] - 1]['slug'] == slug, 'running task needs resource grant')
        if state == 'completed':
            need(any(slug in group['members'] and group['phase'] == 'closed' for group in view['groups']),
                 'completed task requires stable group close')
    for r in view['requests']:
        if r['kind'] == 'verification' and r['status'] in ('waiting', 'granted'):
            t = _task(data, r['slug'])
            need(t['calls'] and t['calls'][-1]['id'] == r['call_id'] and not t['calls'][-1]['closed']
                 and t['calls'][-1]['dispatch'] == 'dispatched',
                 'unfinished resource wait must retain original pending stage')
    need(sum(t['state'] == 'running' for t in data['tasks']) <= 2, 'at most two active stages')
    for a, av in view['leases'].items():
        for b, bv in view['leases'].items():
            need(a == b or not overlap(av, bv), 'overlapping file leases')
    if data['status'] == 'completed':
        need(g is None or g['phase'] == 'closed', 'completed Run has open group')
    return view


def _policy_failures(data):
    # Queue-stop policies survive group close and remain local to this Run.
    return [t for t in data['tasks'] if t['state'] in ('failed', 'blocked')
            and t['definition'].get('execution_policy', {}).get('stop_queue_on_failure', False)]


def _dispatch_blocks(data, view, slug):
    """Reasons a new launch is forbidden, with recorded historical cutoffs."""
    blocks = []
    if data['status'] != 'running':
        blocks.append(('dispatch requires running Run', data['executor']['progress']['at']))
    g = view['group']
    if not g or slug not in g['members']:
        blocks.append(('dispatch outside current fixed group', None))
        return blocks
    if slug not in view['leases']:
        blocks.append(('dispatch requires complete file lease', (view['stopped'].get(slug) or {}).get('observed_at')))
    if g['phase'] != 'working':
        blocks.append(('dispatch forbidden in verification window', view['windows'][-1]['at'] if view['windows'] else None))
    for t in _policy_failures(data):
        events = [e for e in data['scheduler']['events'] if e['kind'] == 'abort' and e['slug'] == t['slug']]
        cutoff = events[-1]['at'] if events else (t.get('result') or {}).get('at')
        blocks.append(('stop_queue_on_failure stops Run dispatch', cutoff))
    return blocks


def _check_dispatch_registration(data, view, slug, call):
    blocks = _dispatch_blocks(data, view, slug)
    if not blocks:
        return
    evidence = call['dispatch_evidence']; historical = evidence.get('historical')
    need(isinstance(historical, dict) and historical.get('source'), blocks[0][0])
    observed = at(historical.get('observed_at')); dispatched = at(evidence['at'])
    need(observed >= dispatched and observed >= at(data['executor']['claimed_at']),
         'historical dispatch requires current host observation')
    need(all(cutoff is not None and dispatched <= at(cutoff) for _, cutoff in blocks),
         'historical dispatch occurred after scheduling stop boundary')


def _finished_continuation(view, request, slug, call_id):
    if (request['kind'] != 'files' or request.get('resume_of') is None
            or request['slug'] != slug or request['call_id'] != call_id):
        return False
    finished = view['requests'][request['resume_of'] - 1]
    return (finished['kind'] == 'verification' and finished['status'] == 'done'
            and finished['slug'] == slug and finished['call_id'] == call_id)


def _can_close_stage(view, slug, call_id):
    pending = [r for r in view['requests'] if r['slug'] == slug and r['call_id'] == call_id and r['status'] == 'waiting']
    if view['active'] is not None:
        r = view['requests'][view['active'] - 1]
        if r['slug'] == slug and r['call_id'] == call_id:
            return False
    for r in pending:
        if r['kind'] == 'finalization':
            continue
        if _finished_continuation(view, r, slug, call_id):
            continue  # Only process handoff writes, never business writes.
        return False
    return True


def validate_update(old, new):
    prior = old['scheduler']['events']; events = new['scheduler']['events']
    need(events[:len(prior)] == prior, 'scheduler history is append-only')
    view = replay(old)
    policy_stopped = bool(_policy_failures(new))
    for event in events[len(prior):]:
        need(event['generation'] == new['executor']['generation'], 'new event requires current generation')
        if event['kind'] == 'group':
            need(not policy_stopped, 'stop_queue_on_failure stops new Run groups')
            need(event['members'] == select_group(old), 'group must scan queue in frozen order')
        if event['kind'] == 'agent_ready':
            r = next((r for r in view['requests'] if r['seq'] == event.get('seq')), None)
            need(r is not None and any(b['id'] == event.get('agent_ref') for b in _task(old, r['slug'])['agents']),
                 'persist role binding before availability')
        if event['kind'] == 'grant':
            need(new['status'] == 'running', 'resource grant requires running Run')
            need(not policy_stopped, 'stop_queue_on_failure stops Run dispatch')
            r = next((r for r in view['requests'] if r['seq'] == event.get('seq')), None)
            need(r is not None and _task(old, r['slug'])['state'] not in TERMINAL,
                 'terminal member cannot receive resources; abort its requests')
        if event['kind'] in ('wait', 'abort'):
            t = _task(old, event['slug'])
            latest = t['calls'][-1]['id'] if t['calls'] else None
            need(event.get('call_id') == latest, 'wait must bind latest call')
            if event['kind'] == 'wait' and event['resource'] == 'verification':
                need(latest is not None and not _task(new, event['slug'])['calls'][-1]['closed'],
                     'verification needs original dispatched pending stage')
        _step(view, event, new)
    for a, b in zip(old['tasks'], new['tasks']):
        for before, after in zip(a['calls'], b['calls']):
            if before['dispatch'] == 'prepared' and after['dispatch'] == 'dispatched':
                _check_dispatch_registration(new, view, a['slug'], after)
            if not before['closed'] and after['closed']:
                need(_can_close_stage(view, a['slug'], after['id']),
                     'unfinished resource wait cannot be a formal stage delivery')
        if a['state'] == 'waiting' and a['checkpoint']['pending_call'] is not None:
            old_call = a['calls'][-1]
            if not b['calls'][-1]['closed']:
                need(a['checkpoint']['last_delivery'] == b['checkpoint']['last_delivery'],
                     'resource wait cannot replace last delivery')
        if len(b['calls']) > len(a['calls']):
            need(new['status'] == 'running', 'stage dispatch requires running Run')
            need(a['slug'] in view['leases'], 'stage dispatch requires complete file lease')
            need(not policy_stopped, 'stop_queue_on_failure stops Run dispatch')
            refresh = b['calls'][-1].get('refresh')
            outstanding = [r for r in view['invalidations'] if r['slug'] == a['slug'] and
                           not any(c.get('refresh') == r for t in old['tasks'] for c in t['calls'])]
            need(not outstanding or refresh == outstanding[-1], 'candidate refresh must preserve invalidation evidence')
            if refresh is not None:
                need(refresh in view['invalidations'] and refresh['slug'] == a['slug'] and
                     refresh['stage'] == b['calls'][-1]['stage'] and
                     not any(c.get('refresh') == refresh for t in old['tasks'] for c in t['calls']),
                     'unverified or consumed candidate refresh')


def append_event(data, kind, when, **payload):
    """Prepare an in-memory proposal; caller still uses guard CAS publication."""
    new = deepcopy(data)
    event = {'id': len(new['scheduler']['events']) + 1, 'kind': kind, 'at': when,
             'generation': data['executor']['generation'], **deepcopy(payload)}
    new['scheduler']['events'].append(event)
    new['executor']['progress'] = {'at': when, 'event': 'scheduler_' + kind}
    view = replay(new)
    if kind == 'wait': _task(new, payload['slug'])['state'] = 'waiting'
    if kind == 'grant': _task(new, view['requests'][payload['seq'] - 1]['slug'])['state'] = 'running'
    if kind == 'finish': _task(new, view['requests'][payload['seq'] - 1]['slug'])['state'] = 'waiting'
    if kind == 'abort' and _task(new, payload['slug'])['state'] not in TERMINAL:
        t = _task(new, payload['slug']); t['state'] = payload['state']
        t['result'] = {'state': payload['state'], 'reason': payload['reason'], 'source': payload['source'],
                       'at': when, 'last_delivery': deepcopy(t['checkpoint']['last_delivery'])}
    return new


def summary(data):
    view = replay(data)
    return {'group': view['group'], 'leases': view['leases'], 'next_request': next_request(view),
            'waiting': [r for r in view['requests'] if r['status'] == 'waiting'],
            'active_verification': view['active'], 'windows': view['windows']}

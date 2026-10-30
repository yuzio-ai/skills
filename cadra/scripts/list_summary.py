#!/usr/bin/env python3
"""Read-only Cadra list projection. Never dispatches, locks, caches or repairs.

Python stdlib; YAML Task headers use one batched Ruby/Psych safe-load process.
JSON headers need no Ruby. Run checks come from the installed run_guard.
Output is a query snapshot, never execution/admission/host-liveness evidence.
"""
import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
from zoneinfo import ZoneInfo

_spec = importlib.util.spec_from_file_location('cadra_list_guard', Path(__file__).with_name('run_guard.py'))
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)
_legacy_spec = importlib.util.spec_from_file_location('cadra_list_010', Path(__file__).with_name('list_legacy_010.py'))
legacy = importlib.util.module_from_spec(_legacy_spec)
_legacy_spec.loader.exec_module(legacy)
READ_PROTOCOLS = (legacy.PROTOCOL, guard.PROTOCOL)
STATES = ('running', 'waiting', 'queued', 'blocked', 'failed', 'unknown', 'ready', 'draft', 'completed')
END = {'completed', 'blocked', 'failed', 'skipped'}
LABELS = dict(code='实现', review='评审', fix='整改', validate='验证')
RUBY = r'''
require 'yaml'; require 'json'; require 'date'
def check(node)
  raise 'YAML aliases are not accepted' if node.is_a?(Psych::Nodes::Alias)
  if node.respond_to?(:tag) && node.tag
    raise 'unsupported YAML tag' unless node.tag.match(/\Atag:yaml.org,2002:(str|int|float|bool|null|map|seq|timestamp)\z/)
  end
  if node.is_a?(Psych::Nodes::Mapping)
    keys = node.children.each_slice(2).map { |k,v| k.value }
    raise 'duplicate YAML key' unless keys.uniq.length == keys.length
  end
  (node.children || []).each { |c| check(c) } if node.respond_to?(:children)
end
out = JSON.parse(STDIN.read).map do |raw|
  begin
    tree = Psych.parse_stream(raw)
    raise 'one YAML document required' unless tree.children.length == 1
    check(tree)
    {data: YAML.safe_load(raw, permitted_classes: [Date, Time], aliases: false)}
  rescue => e
    {error: 'invalid YAML header (' + e.class.name + ')'}
  end
end
print JSON.generate(out)
'''


def require(value, reason):
    if not value:
        raise ValueError(reason)


def record_reader(protocol):
    if protocol == guard.PROTOCOL:
        return guard
    if protocol == legacy.PROTOCOL:
        return legacy
    raise ValueError('unsupported Cadra protocol for list; only 0.10 and 0.11 are readable')


def yaml_batch(blocks):
    if not blocks:
        return []
    ruby = shutil.which('ruby')
    if not ruby:
        return [{'error': 'YAML parser unavailable: Ruby/Psych required'} for _ in blocks]
    try:
        proc = subprocess.run([ruby, '-e', RUBY], input=json.dumps(blocks), text=True,
                              capture_output=True, timeout=60, check=False)
        require(proc.returncode == 0, 'YAML parser failed')
        result = guard.read_json(proc.stdout)
        require(isinstance(result, list) and len(result) == len(blocks), 'invalid YAML parser response')
        return result
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return [{'error': 'YAML parser unavailable or failed'} for _ in blocks]


def creation(data, body, zone):
    """Only explicit first-created fields/lines; never file or Run timestamps."""
    values = [data['created_at']] if 'created_at' in data else []
    for line in body.splitlines():
        if re.match(r'^\s*[-*]\s*(创建|创建时间)\s*[:：]', line):
            stamps = re.findall(r'\d{4}-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:\d\d)?', line)
            if not stamps:
                return None, None
            values.extend(stamps)
    try:
        times = [guard.timestamp(v) for v in values]
        if not times or any(t != times[0] for t in times):
            return None, None
        return times[0].timestamp(), times[0].astimezone(zone).strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError, OverflowError):
        return None, None


def task_valid(data, slug):
    rules = record_reader(data.get('protocol'))
    require(data.get('slug') == slug and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug), 'Task identity mismatch')
    require(isinstance(data.get('title'), str) and data['title'].strip(), 'missing Task title')
    require(type(data.get('revision')) is int and data['revision'] > 0, 'invalid Task revision')
    require(data.get('preparation') in ('draft', 'ready'), 'invalid preparation')
    require(data.get('priority', 'medium') in ('high', 'medium', 'low'), 'invalid priority')
    require(data.get('cohestra_task') == f'.yuzio/cohestra/handoffs/{slug}/', 'Task binding mismatch')
    deps = data.get('dependencies', [])
    require(isinstance(deps, list) and all(isinstance(d, str) and d for d in deps), 'invalid dependencies')
    rules.normalize_flow(data.get('flow', 'code'), data['protocol'])


def same_definition(task, item):
    definition = item['definition']
    current = task['data']
    # Snapshots may add requirement/source_document; all Task header fields
    # must still match while owned by an unfinished Run.
    if any(definition.get(k) != v for k, v in current.items()):
        return False
    documents = [definition[k] for k in ('source_document', 'definition_record') if k in definition]
    if documents and any(not isinstance(value, str) or value != task['raw'].decode('utf-8') for value in documents):
        return False
    section = re.search(r'^## Requirement\s*\n(.*?)(?=^## |\Z)', task['body'], re.M | re.S)
    if section and 'requirement' in definition:
        return isinstance(definition.get('requirement'), str) and definition['requirement'].strip() == section[1].strip()
    return bool(documents)


def tail(entries, revision, protocol, unfinished_runs=()):
    if not entries:
        return None
    children = {}
    for run_id, item in entries.items():
        require(item['definition']['protocol'] == protocol, 'cross-protocol source chain is not supported')
        require('previous_run' in item, 'missing previous_run')
        previous = item['previous_run']
        require(previous is None or isinstance(previous, str) and previous in entries, 'missing source Run')
        require(previous not in unfinished_runs,
                f'Run lifecycle contradiction: unfinished predecessor {previous} has successor {run_id}')
        require(previous not in children, 'branched source chain')
        require(item['revision'] <= revision, 'Run revision exceeds Task')
        children[previous] = run_id
    seen, key, prior = set(), children.get(None), 0
    last = None
    while key is not None and key not in seen:
        seen.add(key)
        last = (key, entries[key])
        require(last[1]['revision'] >= prior, 'revision regressed along source chain')
        prior = last[1]['revision']
        key = children.get(key)
    require(key is None and len(seen) == len(entries), 'cyclic or disconnected source chain')
    return last


def action(item, gaps=()):
    if gaps:
        return '未知：' + '; '.join(gaps)
    if item['state'] == 'waiting':
        return '等待资源（见调度摘要）'
    calls = item.get('calls', [])
    pending = item['checkpoint']['pending_call']
    if pending is not None:
        call = next(c for c in calls if c['id'] == pending)
        label = LABELS[call['stage']]
        return '待派发' + label if call['dispatch'] == 'prepared' else label + '中（已派发，交付待核对）'
    if calls and calls[-1]['closed']:
        contract = guard.saved_contract(calls[-1].get('result'))
        if contract:
            if (contract.get('contract') != '0.8' or contract.get('task') != item['slug']
                    or contract.get('execution_mode') != 'unattended'):
                return '未知：最近交付契约版本、任务身份或执行模式不符'
            candidate, blocked = contract.get('candidate'), contract.get('blocked')
            if (contract.get('status') not in ('in_progress', 'completed', 'blocked', 'failed')
                    or contract['stage_result'].get('status') not in ('completed', 'blocked', 'failed')
                    or not isinstance(candidate, dict) or set(candidate) != {'commit', 'snapshot'}
                    or any(v is not None and not isinstance(v, str) for v in candidate.values())
                    or not isinstance(blocked, dict) or type(blocked.get('value')) is not bool
                    or blocked.get('reason') not in (None, 'human_decision_required', 'missing_input', 'missing_permission',
                                                    'dependency_unavailable', 'environment_blocked', 'candidate_unavailable', 'other')
                    or not blocked['value'] and blocked.get('reason') is not None):
                return '未知：最近交付状态、候选或受阻字段缺失或非法'
            if 'acceptance' in contract and (not isinstance(contract['acceptance'], dict)
                    or contract['acceptance'].get('status') not in ('passed', 'failed', 'pending', 'blocked')):
                return '未知：最近交付验收字段非法'
            if 'findings' in contract and (not isinstance(contract['findings'], dict)
                    or not {'blocking', 'non_blocking'} <= set(contract['findings'])
                    or any(type(contract['findings'][k]) is not int or contract['findings'][k] < 0
                           for k in ('blocking', 'non_blocking', 'unresolved') if k in contract['findings'])):
                return '未知：最近交付 findings 字段非法'
            nxt = contract.get('next', {})
            if (not isinstance(nxt, dict) or type(nxt.get('allowed')) is not bool
                    or nxt.get('reason') not in ('stage_completed', 'blocking_findings', 'acceptance_failed',
                                               'stage_failed', 'task_completed', 'human_decision_required', 'blocked', 'other')
                    or (nxt.get('stage') not in ('need', 'design', *LABELS) if nxt.get('allowed') else nxt.get('stage') is not None)):
                return '未知：最近交付 next 字段缺失或非法'
            if nxt.get('allowed') is True and nxt.get('stage') in LABELS:
                return '等待' + LABELS[nxt['stage']]
    return '待核对后续动作'


def scheduling_summary(view, details=False, history=False):
    def fixed(value):
        return {k: value[k] for k in ('snapshot', 'sha256') if k in value} if value else None
    groups = view['groups'] if history else ([view['group']] if view['group'] else [])
    result = dict(groups=[{**{k: g[k] for k in ('id', 'members', 'phase')},
                           'candidate': fixed(g['candidate'])} for g in groups],
                  active=view['active'], request_count=len(view['requests']))
    result['leases'] = view['leases'] if details else {
        s: dict(mode=v['mode'], files=len(v['files']), dirs=len(v['dirs'])) for s, v in view['leases'].items()}
    result['requests'] = []
    for r in view['requests']:
        if not history and r['status'] not in ('waiting', 'granted'):
            continue
        if not history and (not view['group'] or view['group']['phase'] == 'closed' or r['slug'] not in view['group']['members']):
            continue
        row = {k: r[k] for k in ('seq', 'slug', 'call_id', 'kind', 'status', 'at', 'granted_at', 'finished_at', 'outcome') if k in r}
        row['candidate'] = fixed(r['candidate'])
        for name, start, end in (('queue_seconds', 'at', 'granted_at'), ('verification_seconds', 'granted_at', 'finished_at')):
            row[name] = (guard.timestamp(r[end]) - guard.timestamp(r[start])).total_seconds() if start in r and end in r else None
        if details:
            row['scope'] = r['scope']
        result['requests'].append(row)
    windows = view['windows'] if history else view['windows'][-1:]
    result['windows'] = [dict(group=w['group'], at=w['at'], candidate=fixed(w['candidate'])) for w in windows]
    result['invalidations'] = [{k: e[k] for k in ('id', 'slug', 'stage', 'at', 'paths', 'source') if k in e}
                               for e in view['invalidations']] if history else len(view['invalidations'])
    return result


def reason(item):
    result = item.get('result') or {}
    # No full delivery/contracts or arbitrary prose in the normal projection.
    for key in ('reason', 'human_action', 'next'):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value[:240]
    return '详见 Run 结果，需按来源核对'


def delivery_summary(value):
    if not isinstance(value, dict):
        return value
    fields = ('stage', 'round', 'status', 'handoff', 'source', 'at', 'index_sync', 'actual_author', 'tools_stopped')
    result = {k: value[k] for k in fields if k in value}
    contract = guard.saved_contract(value)
    if contract is not None:
        result['stage_result'] = contract['stage_result']
    omitted = sorted(set(value) - set(fields))
    if omitted:
        result['omitted_fields'] = omitted
    return result


def checkpoint_summary(value):
    if not isinstance(value, dict):
        return value
    result = dict(value)
    if 'last_delivery' in result:
        result['last_delivery'] = delivery_summary(result['last_delivery'])
    return result


def result_summary(value):
    if not isinstance(value, dict):
        return value
    fields = ('state', 'reason', 'candidate', 'findings', 'acceptance', 'next', 'human_action',
              'human_intervention', 'source', 'sources', 'at', 'stage', 'round', 'last_delivery')
    result = {k: value[k] for k in fields if k in value}
    if 'last_delivery' in result:
        result['last_delivery'] = delivery_summary(result['last_delivery'])
    candidate = result.get('candidate')
    if isinstance(candidate, dict) and isinstance(candidate.get('inputs'), dict):
        result['candidate'] = {k: v for k, v in candidate.items() if k != 'inputs'}
        result['candidate'].update(inputs_count=len(candidate['inputs']), omitted_fields=['inputs'])
    omitted = sorted(set(value) - set(fields))
    if omitted:
        result['omitted_fields'] = omitted
    return result


def inventory(root):
    tasks = sorted(p for p in (root / 'tasks').glob('*.md') if not p.name.startswith('.'))
    runs = sorted(p for p in (root / 'runs').glob('*.md') if not p.name.startswith('.')
                  and not re.fullmatch(r'run-\d{8}-\d{2,}-report-\d{2,}\.md', p.name))
    return tasks, runs


def summarize(project, slugs=(), states=(), expand_completed=False, history=False,
              run_id=None, roles=False, timezone='Asia/Shanghai', full_results=False):
    project = Path(project)
    require(project.is_absolute(), 'project must be an absolute path')
    require(project.is_dir(), 'project directory does not exist')
    zone = ZoneInfo(timezone)
    root = project / '.yuzio/cadra'
    require(not any(p.is_symlink() for p in (project / '.yuzio', root, root / 'tasks', root / 'runs')),
            'linked container directory is not supported')
    out = dict(project=str(project), protocol=None, execution_protocol=guard.PROTOCOL,
               supported_protocols=list(READ_PROTOCOLS), timezone=timezone,
               initialized=root.exists(), issues=[], counts={}, queues=[], groups=[], runs=[])
    if not root.exists():
        out['container'] = str(root)
        return out
    issues = out['issues']
    issues_by_slug = defaultdict(list)
    def issue(path, message, slug=None):
        record = dict(source=str(path), reason=message)
        if slug is not None:
            record['slug'] = slug
            issues_by_slug[slug].append(record)
        issues.append(record)

    for name in ('tasks', 'runs'):
        if not (root / name).is_dir():
            issue(root / name, 'missing container directory')
    # Only direct children. Reports, scratch and archives never enter the scan.
    task_paths, run_paths = inventory(root)
    snapshots, docs, yaml_paths, blocks = {}, {}, [], []
    for p in task_paths + run_paths:
        try:
            require(not p.is_symlink(), 'linked record is not supported')
            raw = p.read_bytes()
            snapshots[p] = guard.digest(raw)
            block, body = guard.split_document(raw)
            docs[p] = dict(raw=raw, body=body)
            if block.lstrip().startswith('{'):
                docs[p]['data'] = guard.read_json(block)
            else:
                yaml_paths.append(p)
                blocks.append(block)
        except (OSError, ValueError, UnicodeError) as exc:
            docs[p] = dict(error=str(exc))
    for p, parsed in zip(yaml_paths, yaml_batch(blocks)):
        docs[p].update(parsed)

    tasks, runs, entries = {}, {}, defaultdict(dict)
    broken_runs = False
    for p in task_paths:
        doc = docs[p]
        record = dict(slug=p.stem, title=p.stem, state='unknown', source=str(p), created_at=None)
        tasks[p.stem] = dict(row=record, **doc)
        try:
            require('error' not in doc, doc.get('error'))
            data = doc['data']
            require(isinstance(data, dict), 'Task header must be a mapping')
            record['protocol'] = data.get('protocol')
            task_valid(data, p.stem)
            record['title'] = data['title']
            stamp, display = creation(data, doc['body'], zone)
            tasks[p.stem]['sort_time'] = stamp
            record['created_at'] = display
            record['state'] = data['preparation']
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            issue(p, str(exc), p.stem)
            tasks[p.stem]['invalid'] = True

    for p in run_paths:
        try:
            doc = docs[p]
            require('error' not in doc, doc.get('error'))
            data = doc['data']
            require(isinstance(data, dict), 'Run header must be a mapping')
            rules = record_reader(data.get('protocol'))
            # Current Runs must use JSON, even if the YAML parser can read it.
            require(guard.split_document(doc['raw'])[0].lstrip().startswith('{'), 'Run requires a JSON header')
            require(data.get('run_id') == p.stem, 'Run identity mismatch')
            display_issues = []
            if rules is guard:
                view = guard.validate(data, display_issues=display_issues, return_view=True)
                is_unfinished = guard.unfinished(data, scheduler_view=view)
            else:
                rules.validate(data, display_issues=display_issues)
                view, is_unfinished = None, rules.unfinished(data)
            require(all(isinstance(item['slug'], str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', item['slug'])
                        for item in data['tasks']), 'invalid Run task slug')
            for gap in display_issues:
                issue(p, gap['reason'], gap['slug'])
                issues[-1]['kind'] = 'action'
            gaps_by_slug = defaultdict(list)
            for gap in display_issues:
                gaps_by_slug[gap['slug']].append(gap['reason'])
            runs[p.stem] = dict(data=data, source=str(p), unfinished=is_unfinished, view=view, gaps=gaps_by_slug)
            for item in data['tasks']:
                entries[item['slug']][p.stem] = item
        except (ValueError, TypeError, KeyError, AttributeError, StopIteration, IndexError) as exc:
            issue(p, str(exc))
            broken_runs = True
    unfinished = {rid: r for rid, r in runs.items() if r['unfinished']}
    owners = {t['slug']: (rid, t) for rid, r in unfinished.items() for t in r['data']['tasks']}
    if len(unfinished) > 1:
        issue(root / 'runs', 'multiple unfinished Runs')
    global_unknown = broken_runs or len(unfinished) > 1 or any(not (root / n).is_dir() for n in ('tasks', 'runs'))
    for slug in entries.keys() - tasks.keys():
        tasks[slug] = dict(row=dict(slug=slug, title=slug, state='unknown', created_at=None,
                                    source=str(root / 'tasks' / (slug + '.md'))), invalid=True)
        issue(root / 'tasks' / (slug + '.md'), 'Task missing but Run history exists', slug)
    def source_protocol(slug):
        data = tasks.get(slug, {}).get('data')
        value = data.get('protocol') if isinstance(data, dict) else None
        return value if isinstance(value, str) else None
    for slug, task in tasks.items():
        row = task['row']
        if task.get('invalid'):
            continue
        try:
            require(not global_unknown, 'Run ownership/closure cannot be established; see global issues')
            last = tail(entries[slug], task['data']['revision'], task['data']['protocol'], unfinished)
            if slug in owners:
                _, item = owners[slug]
                require(item['revision'] == task['data']['revision'] and same_definition(task, item),
                        'unfinished Run definition/revision differs from Task')
            if last:
                rid, item = last
                task['latest'] = (rid, item)
                if item['revision'] == task['data']['revision'] and item['state'] != 'skipped':
                    row['state'] = item['state']
                    if row['state'] in ('blocked', 'failed'):
                        row['reason'] = reason(item)
            for dep in task['data'].get('dependencies', []):
                dep_protocol = source_protocol(dep)
                if dep_protocol in READ_PROTOCOLS and dep_protocol != task['data']['protocol']:
                    issue(row['source'], 'cross-protocol dependency cannot establish completion: ' + dep, slug)
        except (ValueError, TypeError, KeyError) as exc:
            row['state'] = 'unknown'
            issue(row['source'], str(exc), slug)

    # Detect a changing snapshot without taking the writer lock or creating files.
    changed = False
    for p, sha in snapshots.items():
        try:
            require(guard.digest(p.read_bytes()) == sha, 'record changed during query; rerun list')
        except (OSError, ValueError):
            issue(p, 'record changed during query; rerun list')
            changed = True
    current_tasks, current_runs = inventory(root)
    if current_tasks != task_paths or current_runs != run_paths:
        issue(root, 'record inventory changed during query; rerun list')
        changed = True
    if changed:
        for task in tasks.values():
            task['row']['state'] = 'unknown'
    out['scan'] = dict(tasks=len(task_paths), runs=len(run_paths), stable=not changed)
    protocols = Counter(doc['data']['protocol'] for doc in docs.values()
                        if isinstance(doc.get('data'), dict) and isinstance(doc['data'].get('protocol'), str))
    out['protocols'] = dict(protocols)
    if len(protocols) == 1:
        out['protocol'] = next(iter(protocols))
    if legacy.PROTOCOL in protocols:
        out['legacy_read_only'] = True
    # Filter only AFTER global closure, ownership and per-slug chain checks.
    selected = {s: t for s, t in tasks.items() if not slugs or s in slugs}
    run_items = {}
    if run_id:
        require(re.fullmatch(r'run-\d{8}-\d{2,}', run_id), 'invalid requested Run ID')
        if run_id not in runs:
            issue(root / 'runs' / (run_id + '.md'), 'requested Run is missing or invalid')
        run_items = {t['slug']: t for t in runs[run_id]['data']['tasks']} if run_id in runs else {}
        selected = {s: t for s, t in selected.items() if s in run_items
                    and (not states or run_items[s]['state'] in states)}
    elif states:
        selected = {s: t for s, t in selected.items() if t['row']['state'] in states}
    for slug in slugs:
        if slug not in tasks:
            issue(root / 'tasks' / (slug + '.md'), 'requested Task not found', slug)
    out['counts'] = dict(Counter(t['row']['state'] for t in selected.values()))
    if run_id:
        out['current_counts'] = dict(out['counts'])
        if not changed:
            out['counts'] = dict(Counter(run_items[s]['state'] for s in selected))
    out['total'] = len(selected)
    expand = expand_completed or 'completed' in states or bool(slugs)
    detail = len(slugs) == 1
    if detail or run_id:
        out['result_mode'] = 'full' if full_results else 'summary'
    def add_roles(rid, slug):
        data = runs[rid]['data']
        role_run = out.setdefault('role_details', {}).setdefault(rid, dict(
            protocol=data['protocol'], source=runs[rid]['source'], executor=data['executor'], agents={}))
        role_run['agents'][slug] = entries[slug][rid]['agents']
    def task_row(slug, current_details=True):
        task = tasks[slug]
        row = dict(task['row'])
        errors = [i['reason'] for i in issues_by_slug.get(slug, ())]
        if errors:
            row['reason'] = '; '.join(errors)
        if detail and current_details and 'data' in task and not task.get('invalid'):
            d = task['data']
            dep_protocols = {dep: source_protocol(dep) for dep in d.get('dependencies', [])}
            row['details'] = dict(revision=d['revision'], priority=d.get('priority', 'medium'),
                                 flow=d.get('flow', 'code'), dependencies={dep: tasks.get(dep, {}).get('row', {}).get('state', 'unknown')
                                                                         if dep_protocols[dep] == d['protocol'] else 'unknown'
                                                                         for dep in d.get('dependencies', [])})
            if dep_protocols:
                row['details']['dependency_protocols'] = dep_protocols
            if 'latest' in task:
                rid, item = task['latest']
                add_roles(rid, slug)
                row['details'].update(run=rid, checkpoint=item.get('checkpoint') if full_results else checkpoint_summary(item.get('checkpoint')),
                                      roles_ref=rid)
                if full_results:
                    row['details']['result'] = item['result']
        return row

    if roles and not run_id:
        for slug, task in selected.items():
            if 'latest' in task:
                rid, item = task['latest']
                add_roles(rid, slug)
    queued = set()
    for rid, run in sorted(runs.items(), reverse=True):
        if changed:
            break
        data = run['data']
        relevant = any(t['slug'] in selected for t in data['tasks'])
        if not relevant or run_id and rid != run_id:
            continue
        top = data['status'] == 'running' and not run_id
        if not (top or run['unfinished'] or history or run_id):
            continue
        summary = dict(run=rid, source=run['source'], protocol=data['protocol'], status=data['status'],
                       ended=sum(t['state'] in END for t in data['tasks']), total=len(data['tasks']),
                       activity='unknown', appended_batches=len(data['append_history']))
        summary['current'] = []
        for t in data['tasks']:
            if t['state'] not in ('running', 'waiting'):
                continue
            gaps = run['gaps'].get(t['slug'], ())
            verb = action(t, gaps)
            if verb.startswith('未知：') and not gaps:
                issue(run['source'], verb.removeprefix('未知：'), t['slug'])
                issues[-1]['kind'] = 'action'
            summary['current'].append(dict(slug=t['slug'], state=t['state'], action=verb))
        if roles or detail or run_id:
            for t in data['tasks']:
                if t['slug'] in selected:
                    add_roles(rid, t['slug'])
            summary['roles_ref'] = rid
        if data['protocol'] == guard.PROTOCOL:
            summary['scheduling'] = scheduling_summary(run['view'], details=bool(run_id), history=bool(history or run_id))
        else:
            summary['legacy_read_only'] = True
        if top or run_id:
            summary['queue'] = []
            hidden = 0
            for n, item in enumerate(data['tasks'], 1):
                slug = item['slug']
                if slug not in selected:
                    continue
                queued.add(slug)
                if item['state'] == 'completed' and tasks[slug]['row']['state'] == 'completed' and not (expand or run_id):
                    hidden += 1
                    continue
                row = task_row(slug, current_details=not run_id)
                row.update(position=n, run_state=item['state'])
                if run_id:
                    row['current_state'] = row['state']
                    row['state'] = item['state']
                    row['title'] = item['definition'].get('title', slug)
                    row['task_source'] = row['source']
                    row['source'] = run['source']
                    row['result'] = item['result'] if full_results else result_summary(item['result'])
                    if detail:
                        definition = item['definition']
                        row['details'] = dict(revision=item['revision'], priority=definition.get('priority', 'medium'),
                                              flow=definition.get('flow', 'code'), run=rid,
                                              checkpoint=item.get('checkpoint') if full_results else checkpoint_summary(item.get('checkpoint')),
                                              roles_ref=rid)
                summary['queue'].append(row)
            summary['completed_hidden'] = hidden
        out['queues' if top else 'runs'].append(summary)
    for state in STATES:
        members = [s for s in selected if s not in queued and tasks[s]['row']['state'] == state]
        members.sort(key=lambda s: (tasks[s].get('sort_time') is None, tasks[s].get('sort_time') or 0, s))
        if members:
            group = dict(state=state, count=len(members))
            if state == 'completed' and not expand:
                group['collapsed'] = True
            else:
                group['tasks'] = [task_row(s) for s in members]
            out['groups'].append(group)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--slug', action='append', default=[])
    parser.add_argument('--status', action='append', choices=STATES, default=[])
    parser.add_argument('--expand-completed', action='store_true')
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--run')
    parser.add_argument('--roles', action='store_true')
    parser.add_argument('--full-results', action='store_true')
    parser.add_argument('--timezone', default='Asia/Shanghai')
    args = parser.parse_args()
    try:
        result = summarize(args.project, args.slug, args.status, args.expand_completed,
                           args.history, args.run, args.roles, args.timezone, args.full_results)
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps(dict(error=str(exc)), ensure_ascii=False, separators=(',', ':')))
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Inspect, check and publish Cadra 0.12 Task preparation."""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import run_guard as guard

records = guard.task_records
require = guard.require
ROOT = Path('.yuzio/cadra')
DEFAULT_POLICY = {'stop_queue_on_failure': False}
GATE = re.compile(r'^## Ready Gate[ \t]*$(.*?)(?=^## |\Z)', re.M | re.S)


def sha(raw):
    return None if raw is None else guard.digest(raw)


def load_task(raw, slug):
    doc = records.documents({slug: raw}, guard.split_document, guard.read_json)[slug]
    data = doc['data']
    require(isinstance(data, dict) and data.get('protocol') == guard.PROTOCOL, f'{slug}: {guard.PROTOCOL_ERROR}')
    records.validate_task(data, slug, guard)
    dependencies(data.get('dependencies', []))
    policy = data.get('execution_policy', DEFAULT_POLICY)
    require(isinstance(policy, dict) and set(policy) == set(DEFAULT_POLICY) and
            type(policy['stop_queue_on_failure']) is bool, f'{slug}: invalid execution policy')
    guard.closeout.origin(data)
    return doc


def dependencies(value):
    require(isinstance(value, list) and all(records.valid_slug(v) for v in value), 'invalid dependencies')
    require(len(value) == len(set(value)), 'duplicate dependencies')
    return value


def folder(path, project):
    for part in (path, *path.parents):
        if not part.is_relative_to(project):
            break
        require(not part.is_symlink(), f'linked directory: {part}')
    require(not path.exists() or path.is_dir(), f'expected directory: {path}')
    return path


def ownership(run_dir, slugs, project):
    entries = defaultdict(dict)
    unfinished = {}
    for path in sorted(run_dir.glob('*.md')):
        if path.name.startswith('.') or '-report-' in path.name.casefold():
            continue
        try:
            raw = records.read_file(path, project)
            require(raw is not None, 'Run disappeared during inspection')
            data = guard.header(raw)
            require(data['run_id'] == path.stem, 'Run identity mismatch')
            view = guard.validate(data, return_view=True)
            if guard.unfinished(data, scheduler_view=view):
                unfinished[path.stem] = data['status']
            for item in data['tasks']:
                if item['slug'] in slugs:
                    entries[item['slug']][path.stem] = item
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
            raise ValueError(f'{path}: {exc}') from exc
    require(len(unfinished) <= 1, 'multiple unfinished Runs')
    return entries, unfinished


def source_state(slug, doc, entries, unfinished, *, target):
    require(doc is not None or not entries, f'{slug}: Task missing but Run history exists')
    if doc is None:
        return {'state': None, 'latest': None, 'history': [], 'execution_evidence': False}
    data = doc['data']
    latest = records.tail(entries, data['revision'], data['protocol'], unfinished)
    for run_id in entries.keys() & unfinished.keys():
        item = entries[run_id]
        require(records.same_definition(doc, item), f'{slug}: definition differs from unfinished Run {run_id}')
        require(not target, f'{slug}: belongs to unfinished Run {run_id}')
    state = data['preparation']
    if latest and latest[1]['revision'] == data['revision'] and latest[1]['state'] != 'skipped':
        state = latest[1]['state']
    return {'state': state, 'latest': latest[0] if latest else None,
            'history': [dict(run=run_id, revision=item['revision'], state=item['state'],
                             sha256=sha(json.dumps(item, sort_keys=True).encode()))
                        for run_id, item in sorted(entries.items())],
            'execution_evidence': any(item['calls'] or (item['result'] or {}).get('last_delivery')
                                      for item in entries.values())}


def inspect(project, slug, entry, requested=None):
    require(entry in ('add', 'ready') and records.valid_slug(slug), 'invalid preparation entry or slug')
    require(project.is_absolute() and project.resolve() == project and project.is_dir(),
            'project must be a resolved absolute directory')
    root = project / ROOT
    task_dir = folder(root / 'tasks', project)
    run_dir = folder(root / 'runs', project)
    readme = records.read_file(root / 'README.md', project)
    if readme is not None:
        stamp = re.search(r'^- 任务/Run 协议[：:][ \t]*`?([^\s`]+)', readme.decode(), re.M)
        require(stamp and stamp[1] == guard.PROTOCOL, guard.PROTOCOL_ERROR)
    target = records.task_path(root, slug)
    raw = records.read_file(target, project)
    doc = load_task(raw, slug) if raw is not None else None
    if entry == 'ready':
        require(doc is not None, f'{slug}: Task does not exist')
        require(requested is None, 'ready cannot override dependencies')
    if doc is not None:
        require(guard.closeout.origin(doc['data']) is None, f'{slug}: generated task requires its source Run')
    direct = dependencies(requested if requested is not None else (doc['data'].get('dependencies', []) if doc else []))
    docs = {slug: doc}
    visiting = {slug}

    def visit(dep):
        require(dep not in visiting, f'dependency cycle through {dep}')
        if dep in docs:
            return
        path = records.task_path(root, dep)
        raw = records.read_file(path, project)
        require(raw is not None, f'missing dependency: {dep}')
        docs[dep] = load_task(raw, dep)
        visiting.add(dep)
        for child in docs[dep]['data'].get('dependencies', []):
            visit(child)
        visiting.remove(dep)

    for dep in direct:
        visit(dep)

    # add validates dependency definitions, without resolving their execution state.
    slugs = docs.keys() if entry == 'ready' else {slug}
    entries, unfinished = ownership(run_dir, slugs, project)
    states = {name: source_state(name, docs[name], entries[name], unfinished, target=name == slug)
              for name in sorted(slugs)}
    if entry == 'ready':
        require(states[slug]['state'] in ('draft', 'ready'), f"{slug}: current state {states[slug]['state']} is not preparable")
    handoff = folder(project / '.yuzio/cohestra/handoffs' / slug, project)
    index = records.read_file(handoff / 'README.md', project)
    deliveries = {}
    for path in sorted(handoff.glob('*.md')):
        if re.fullmatch(r'(need|design|code|review|fix|validate)-\d+\.md', path.name):
            deliveries[path.name] = sha(records.read_file(path, project)) if entry == 'ready' else True
    token = dict(project=str(project), slug=slug, entry=entry, requested=requested, direct=direct,
                 task=sha(raw), dependencies={name: sha(value['raw']) for name, value in docs.items() if name != slug},
                 states=states, unfinished=unfinished, handoff={'index': sha(index), 'deliveries': deliveries})
    task = {key: doc[key] for key in ('data', 'body')} if doc is not None else None
    result = dict(snapshot=token, task=task,
                  initialized=readme is not None and task_dir.is_dir() and run_dir.is_dir())
    return result, doc


def measure(snapshot, inputs, attachments):
    project = Path(snapshot['project'])
    require(isinstance(inputs, dict) and all(isinstance(reason, str) and reason.strip() for reason in inputs.values()),
            'business inputs must map explicit paths to a non-empty reason')
    require(snapshot['entry'] == 'ready' or not inputs, 'add does not fingerprint business inputs')
    guard.scheduler.validate_paths(project, dict(mode='parallel', files=list(inputs), dirs=[]))
    business = {path: sha(records.read_file(project / path, project)) for path in inputs}
    guard.scheduler.hashes(business)
    require(isinstance(attachments, dict), 'attachments must map retained paths to expected SHA-256')
    prefix = ROOT / 'tasks' / snapshot['slug'] / 'inputs'
    captured = {}
    issues = []
    for path, expected in attachments.items():
        require(isinstance(path, str) and re.fullmatch(r'[^/]+(?:/[^/]+)*', path) and
                not set(path.split('/')) & {'.', '..'} and '\\' not in path and '\x00' not in path,
                'invalid attachment path')
        relative = Path(path)
        require(relative.is_relative_to(prefix) and len(relative.relative_to(prefix).parts) >= 2,
                f'attachment outside Task input batches: {path}')
        require(isinstance(expected, str) and re.fullmatch(r'[0-9a-f]{64}', expected), f'invalid attachment SHA-256: {path}')
        captured[path] = sha(records.read_file(project / relative, project))
        if captured[path] != expected:
            issues.append(path)
    return dict(snapshot=snapshot, inputs=inputs, attachments=attachments,
                business=business, captured=captured, attachment_issues=issues)


def compare(label, before, after):
    if isinstance(before, dict) and isinstance(after, dict):
        changed = [name for name in sorted(before.keys() | after.keys())
                   if name not in before or name not in after or before[name] != after[name]]
        require(not changed, f'{label} changed: {", ".join(changed)}')
    else:
        require(before == after, f'{label} changed')


def check_proposal(snapshot, original, proposed, checked):
    data = proposed['data']
    slug = snapshot['slug']
    require(guard.closeout.origin(data) is None, 'ordinary preparation cannot set generated origin')
    require(data.get('dependencies', []) == snapshot['direct'], 'proposal dependencies were not inspected')
    require(records.requirement(proposed['body']), 'Task Requirement required')
    require(len(GATE.findall(proposed['body'])) == 1, 'one Task Ready Gate section required')
    ready = data['preparation'] == 'ready'
    scope = data.get('ready_scope')
    if ready:
        guard.scheduler.admission({'definition': data, 'revision': data['revision']})
    else:
        require(scope is None, 'draft cannot retain ready_scope')
    if snapshot['entry'] == 'ready':
        old = original['data']
        gate_fields = {'preparation', 'ready_scope'}
        require({k: v for k, v in old.items() if k not in gate_fields} ==
                {k: v for k, v in data.items() if k not in gate_fields}, 'ready cannot change Task definition')
        require(GATE.sub('', original['body'], count=1) == GATE.sub('', proposed['body'], count=1),
                'ready can only edit the Ready Gate section')
        if ready:
            require(not checked['attachment_issues'], 'changed or missing attachment blocks ready')
            require(scope['inputs'] == checked['business'], 'ready_scope.inputs must match measured inputs')
            require(all(snapshot['states'][dep]['state'] == 'completed' for dep in snapshot['direct']),
                    'direct dependency has not completed its current definition')
            guard.scheduler.validate_paths(Path(snapshot['project']), scope['scope'])
        return

    require(not checked['attachment_issues'], 'changed or missing staged attachment blocks add')
    if original is None:
        require(not ready and data['revision'] == 1 and data.get('revision_base') is None, 'new Task must start as revision 1 draft')
        return
    old = original['data']
    changed = (
        records.requirement(original['body']) != records.requirement(proposed['body'])
        or old.get('dependencies', []) != data.get('dependencies', [])
        or guard.normalize_flow(old.get('flow', 'code')) != guard.normalize_flow(data.get('flow', 'code'))
        or old.get('execution_policy', DEFAULT_POLICY) != data.get('execution_policy', DEFAULT_POLICY)
    )
    history = snapshot['states'][slug]['history']
    entered = any(item['revision'] == old['revision'] for item in history)
    if changed:
        expected_base = (dict(run=snapshot['states'][slug]['latest'], revision=old['revision'])
                         if entered else old.get('revision_base'))
        require(not ready and data['revision'] == old['revision'] + int(entered) and
                data.get('revision_base') == expected_base, 'changed Task needs the required draft revision')
    else:
        require(all(data.get(key) == old.get(key) for key in ('revision', 'revision_base', 'preparation', 'ready_scope')),
                'unchanged Task definition must preserve its preparation and revision')


def publish(checked, proposal):
    expected = checked['snapshot']
    project = Path(expected['project'])
    target = records.task_path(project / ROOT, expected['slug'])
    proposed = load_task(proposal, expected['slug'])
    run_dir = folder(project / ROOT / 'runs', project)
    with guard.writer_lock(run_dir):
        current, original = inspect(project, expected['slug'], expected['entry'], expected['requested'])
        require(current['initialized'], 'complete the project Cadra container before saving')
        actual = current['snapshot']
        for field in ('task', 'dependencies', 'states', 'unfinished', 'handoff'):
            compare(f"{expected['slug']} {field}", expected[field], actual[field])
        fresh = measure(actual, checked['inputs'], checked['attachments'])
        compare('business inputs', checked['business'], fresh['business'])
        compare('design attachments', checked['captured'], fresh['captured'])
        raw = original['raw'] if original is not None else None
        check_proposal(actual, original, proposed, fresh)
        ignored = subprocess.run(['git', 'check-ignore', '-q', '--', str(target)],
                                 cwd=project, capture_output=True).returncode
        require(ignored == 0, f'Task path is not ignored or is tracked: {target}')
        fd, temporary = tempfile.mkstemp(prefix='.task-', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(proposal)
                out.flush()
                os.fsync(out.fileno())
            require(records.read_file(target, project) == raw, f'Task changed during publication: {target}')
            if raw is None:
                os.link(temporary, target)
                os.unlink(temporary)
            else:
                os.replace(temporary, target)
            require(records.read_file(target, project) == proposal, f'Task readback failed: {target}')
        finally:
            Path(temporary).unlink(missing_ok=True)
    return dict(path=str(target), slug=expected['slug'], preparation=proposed['data']['preparation'],
                revision=proposed['data']['revision'], sha256=sha(proposal))


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    sub = parser.add_subparsers(dest='action', required=True)
    read = sub.add_parser('inspect')
    read.add_argument('--project', type=Path, required=True)
    read.add_argument('--slug', required=True)
    read.add_argument('--entry', choices=('add', 'ready'), required=True)
    read.add_argument('--dependencies', help='JSON array of proposed direct dependencies for add')
    check = sub.add_parser('check')
    check.add_argument('--inspection', type=Path, required=True)
    check.add_argument('--inputs', type=Path)
    check.add_argument('--attachments', type=Path)
    save = sub.add_parser('publish')
    save.add_argument('--checked', type=Path, required=True)
    save.add_argument('--proposal', type=Path, required=True)
    try:
        args = parser.parse_args()
        if args.action == 'inspect':
            result, _ = inspect(args.project, args.slug, args.entry,
                                guard.read_json(args.dependencies) if args.dependencies else None)
        elif args.action == 'check':
            result = measure(guard.read_json(args.inspection.read_text())['snapshot'],
                             guard.read_json(args.inputs.read_text()) if args.inputs else {},
                             guard.read_json(args.attachments.read_text()) if args.attachments else {})
        else:
            result = publish(guard.read_json(args.checked.read_text()), args.proposal.read_bytes())
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()

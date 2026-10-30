#!/usr/bin/env python3
"""One-time local Cadra 0.10 cutover. Not an installed skill dependency.

Dry-run by default. Requires macOS system Ruby/Psych only for offline old YAML.
Runtime Cadra never imports this tool. Current execution entries reject old
protocols; list alone can read 0.10 without migration. This historical tool
requires matching 0.10 source packages and does not migrate to 0.11.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

PROTOCOL = '0.10'
PACKAGES = ('cadra', 'cohestra')
END = {'completed', 'blocked', 'failed', 'skipped'}
RUBY = r'''
require 'yaml'; require 'json'; require 'date'
def check(node)
  raise 'YAML aliases are not accepted' if node.is_a?(Psych::Nodes::Alias)
  if node.is_a?(Psych::Nodes::Mapping)
    keys = node.children.each_slice(2).map { |k,v| k.value }
    raise 'duplicate YAML key' unless keys.uniq.length == keys.length
  end
  (node.children || []).each { |child| check(child) } if node.respond_to?(:children)
end
raw = STDIN.read
check(Psych.parse_stream(raw))
print JSON.generate(YAML.safe_load(raw, permitted_classes: [Date, Time], aliases: false))
'''


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), f'linked path: {path}')
    return path


def files(root):
    root = safe(root)
    require(root.is_dir(), f'missing directory: {root}')
    result = {}
    for p in root.rglob('*'):
        require(not p.is_symlink(), f'linked file: {p}')
        if p.is_file() and p.name != '.writer.lock':
            result[str(p.relative_to(root))] = sha(p.read_bytes())
    return result


def load(raw):
    match = re.fullmatch(r'---\r?\n(.*?)\r?\n---(?:\r?\n(.*))?', raw.decode(), re.S)
    require(match, 'missing Front Matter')
    proc = subprocess.run(['/usr/bin/ruby', '-e', RUBY], input=match[1], text=True,
                          capture_output=True, check=False)
    require(proc.returncode == 0, 'unsupported offline YAML: ' + proc.stderr[-400:])
    data = json.loads(proc.stdout)
    require(isinstance(data, dict), 'mapping Front Matter required')
    return data, match[2] or ''


def dump(data, body):
    return ('---\n' + json.dumps(data, ensure_ascii=False, indent=2) + '\n---\n' + body).encode()


def atomic_write(path, raw, expected=Ellipsis):
    path = safe(path)
    fd, temporary = tempfile.mkstemp(prefix='.cutover-file-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        if expected is not Ellipsis:
            require((path.read_bytes() if path.exists() else None) == expected, 'file changed before replacement')
        os.replace(temporary, path)
        require(path.read_bytes() == raw, 'file readback failed; inspect cutover journal')
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def old_flow(value):
    if isinstance(value, str):
        value = {'implementation': 'code', 'bugfix': 'fix', 'review-only': ['review'],
                 'full': 'code', 'feature': 'code', 'small-change': 'code'}.get(value, value)
    stages = {'code': ['code', 'review', 'fix', 'validate'],
              'fix': ['fix', 'review', 'validate'], 'review': ['review', 'fix', 'validate']}
    expanded = stages.get(value) if isinstance(value, str) else value
    require(isinstance(expanded, list) and expanded and all(s in ('code', 'review', 'fix', 'validate')
            for s in expanded), 'flow needs human preparation before cutover')
    return value


def inspect(project, installation, source):
    project, installation, source = map(safe, (project, installation, source))
    require(project != source, 'cannot cut over the skill source repository')
    root = project / '.yuzio/cadra'
    snapshot = files(root)
    require(not re.search(r'^- 任务/Run 协议：0\.10\s*$', (root/'README.md').read_text(), re.M), 'cutover already completed')
    runs, entries = {}, {}
    for p in sorted((root / 'runs').glob('run-*.md')):
        if '-report-' in p.name:
            continue
        d, _ = load(p.read_bytes())
        require(d.get('protocol') in ('0.6','0.7','0.8','0.9'), 'not a pre-0.10 container; refuse repeat cutover')
        key = d.get('run_id')
        require(key == p.stem and key not in runs, 'Run identity mismatch')
        require(d.get('status') in ('completed', 'stopped'), f'unfinished Run: {key}; keep original environment')
        require(isinstance(d.get('tasks'), list) and d['tasks'], 'missing Run tasks')
        seen = set()
        for item in d['tasks']:
            slug = item.get('slug')
            require(isinstance(slug, str) and slug and slug not in seen, 'duplicate/missing task slug')
            seen.add(slug)
            require(item.get('state') in END and item.get('result', {}).get('state') == item['state'],
                    'unclosed or inconsistent task result')
            require(all(c.get('closed') is True for c in item.get('calls', [])), 'unclosed call; keep original environment')
            entries.setdefault(slug, {})[key] = item
        runs[key] = d
    latest = {}
    for slug, chain in entries.items():
        successors = {}
        for key, item in chain.items():
            previous = item.get('previous_run')
            require(previous is None or previous in chain, f'missing source Run for {slug}')
            require(previous not in successors, f'branched source chain for {slug}')
            successors[previous] = key
        visited, key = [], successors.get(None)
        require(key is not None, f'no source root for {slug}')
        while key is not None and key not in visited:
            visited.append(key)
            key = successors.get(key)
        require(key is None and len(visited) == len(chain), f'cyclic source chain for {slug}')
        revisions = [chain[k]['revision'] for k in visited]
        require(revisions == sorted(revisions), f'revision regression for {slug}')
        latest[slug] = {'run': visited[-1], **chain[visited[-1]]}
    tasks, completed = {}, []
    for p in sorted((root / 'tasks').glob('*.md')):
        d, body = load(p.read_bytes())
        require(d.get('protocol') in ('0.6','0.7','0.8','0.9'), 'not a pre-0.10 Task')
        slug = d.get('slug')
        require(slug == p.stem and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug), 'Task identity mismatch')
        require(type(d.get('revision')) is int and d['revision'] > 0, 'invalid Task revision')
        require(d.get('cohestra_task') == f'.yuzio/cohestra/handoffs/{slug}/', 'Task binding mismatch')
        prior = latest.get(slug)
        require(not prior or prior['revision'] <= d['revision'], 'Run revision exceeds Task')
        if prior and prior['revision'] == d['revision'] and prior['state'] == 'completed':
            completed.append(slug)
        else:
            tasks[slug] = {'definition': d, 'body': body, 'source': prior,
                           'flow': old_flow(d.get('flow', 'implementation'))}
    require(set(entries) <= set(tasks) | set(completed), 'Run has missing Task; resolve before cutover')
    for item in tasks.values():
        deps = item['definition'].get('dependencies', [])
        require(isinstance(deps, list) and all(d in tasks or d in completed for d in deps), 'unresolved dependency')
    versions = {}
    for name in PACKAGES:
        versions[name] = {'installed': json.loads((installation/name/'release.json').read_text()),
                          'source': json.loads((source/name/'release.json').read_text())}
    require(versions['cadra']['source']['protocol_version'] == PROTOCOL, 'source protocol mismatch')
    plan = {'project': str(project), 'installation': str(installation), 'source': str(source),
            'container': snapshot, 'installed': {p: files(installation/p) for p in PACKAGES},
            'packages': {p: files(source/p) for p in PACKAGES}, 'versions': versions,
            'completed': completed, 'pending': tasks}
    plan['sha256'] = sha(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode())
    return plan


def rewrite_links(raw, origin, destination, moved, project):
    """Resolve Markdown from its ORIGINAL location; immutable originals stay in backup."""
    text = raw.decode()
    def link(match):
        target = match[1]
        angled = target.startswith('<') and target.endswith('>')
        value = target[1:-1] if angled else target
        if re.match(r'[a-zA-Z][\w+.-]*:', value) or value.startswith('#'):
            return match[0]
        path, sep, fragment = value.partition('#')
        original = (origin.parent / path).resolve()
        resolved = moved.get(original, original)
        if resolved == original and destination == origin:
            return match[0]
        result = os.path.relpath(resolved, destination.parent) + (sep + fragment if sep else '')
        return '](' + ('<' + result + '>' if angled else result) + ')'
    text = re.sub(r'\]\((<[^>]+>|[^\s)]+)\)', link, text)
    # Also repair literal absolute and project-relative source pointers.
    for old, new in sorted(moved.items(), key=lambda pair: len(str(pair[0])), reverse=True):
        boundary = r"(?=$|[/\s#):>,;\]`\"'；，。])"
        text = re.sub(re.escape(str(old)) + boundary, lambda _: str(new), text)
        text = re.sub(re.escape(str(old.relative_to(project))) + boundary,
                      lambda _: str(new.relative_to(project)), text)
    return text.encode()


def references(project, root):
    for directory, names, filenames in os.walk(project):
        base = Path(directory)
        names[:] = [n for n in names if n not in ('.git', 'node_modules', '.build', '.next', 'output',
                     'DerivedData', 'cadra-archive') and not (base/n).is_symlink()]
        if base == root:
            names[:] = []
            continue
        for name in filenames:
            p = base/name
            if p.suffix == '.md' and not p.is_symlink():
                yield p


def replace_tree(target, source, expected=None):
    safe(target); safe(source)
    expected = files(target) if expected is None else expected
    staging = Path(tempfile.mkdtemp(prefix='.cutover-', dir=target.parent))
    shutil.copytree(source, staging, dirs_exist_ok=True)
    # Preserve the guard's lock inode across container renames. A copied lock
    # would let another writer acquire a different inode during the switch.
    old_lock, new_lock = target/'runs/.writer.lock', staging/'runs/.writer.lock'
    if old_lock.exists() and new_lock.parent.is_dir():
        safe(old_lock)
        new_lock.unlink(missing_ok=True)
        os.link(old_lock, new_lock)
    displaced = target.with_name(target.name + '.cutover-old')
    require(not displaced.exists(), 'unfinished previous tree switch; restore from cutover journal')
    require(files(target) == expected, 'tree changed before replacement')
    target.rename(displaced)
    try:
        require(files(displaced) == expected, 'tree changed during replacement')
        staging.rename(target)
    except BaseException:
        displaced.rename(target)
        raise
    require(files(target) == files(source), 'tree readback failed; retain displaced tree and restore journal')
    require(files(displaced) == expected, 'displaced tree changed; preserve it for recovery')
    shutil.rmtree(displaced)


def tree_state(target, before, after):
    displaced = target.with_name(target.name + '.cutover-old')
    require(target.exists() or displaced.exists(), 'missing current and displaced trees')
    if target.exists():
        require(files(target) in (before, after), 'new work exists; refuse rollback')
    if displaced.exists():
        require(files(displaced) in (before, after), 'displaced tree changed; refuse rollback')
    return {'target': files(target) if target.exists() else None,
            'displaced': files(displaced) if displaced.exists() else None}


def restore_tree(target, backup, before, after, archive, label, expected):
    require(tree_state(target, before, after) == expected, 'tree changed since rollback validation')
    displaced = target.with_name(target.name + '.cutover-old')
    if displaced.exists():
        # A crash can leave the old tree displaced with target either absent
        # or already installed. Preserve both versions before restoring.
        if target.exists():
            quarantine = archive/'recovery'/label
            quarantine.parent.mkdir(parents=True, exist_ok=True)
            require(not quarantine.exists(), 'recovery quarantine already exists')
            target.rename(quarantine)
        displaced.rename(target)
    if files(target) != before:
        expected_current = expected['displaced'] if expected['displaced'] is not None else expected['target']
        replace_tree(target, backup, expected=expected_current)
    require(files(target) == before, 'tree restoration readback failed')


def apply_locked(plan, expected):
    require(plan['sha256'] == expected, 'plan changed; inspect again')
    project, installation, source = (Path(plan[k]) for k in ('project', 'installation', 'source'))
    root = project/'.yuzio/cadra'
    require(inspect(project, installation, source)['sha256'] == expected, 'inputs changed before preparation')
    archive = project/'.yuzio/cadra-archive'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    require(not archive.exists(), 'archive already exists')
    archive.mkdir(parents=True)
    original = archive/'original'
    shutil.copytree(root, original/'container')
    for name in PACKAGES:
        shutil.copytree(installation/name, original/'installed'/name)
    require(files(original/'container') == plan['container'], 'container backup verification failed')
    for name in PACKAGES:
        require(files(original/'installed'/name) == plan['installed'][name], 'installation backup verification failed')
    # Every archived source is byte-for-byte original. Views provide working links.
    stage = archive/'prepared/cadra'
    shutil.copytree(root, stage)
    for name in ('tasks', 'runs'):
        shutil.rmtree(stage/name)
        (stage/name).mkdir()
    retained = {f'tasks/{slug}.md' for slug in plan['pending']}
    removed = [k for k in plan['container'] if k.startswith(('runs/','tasks/')) and k not in retained]
    moved = {root/k: original/'container'/k for k in removed}
    for key in removed:
        parent = Path(key).parent
        while len(parent.parts) > 1:
            moved[root/parent] = original/'container'/parent
            parent = parent.parent
    migrations = []
    for slug, item in plan['pending'].items():
        d = dict(item['definition']); prior = item['source']; old_revision = d['revision']
        d.update(protocol=PROTOCOL, flow=item['flow'], preparation='draft', revision_base=None, changed_fields=[])
        if prior:
            d['revision'] += 1
            d['changed_fields'] = ['requirement']
        closed_deps = [dep for dep in d.get('dependencies', []) if dep in plan['completed']]
        d['dependencies'] = [dep for dep in d.get('dependencies', []) if dep not in closed_deps]
        if closed_deps:
            d['changed_fields'] = list(dict.fromkeys(d['changed_fields'] + ['dependencies']))
        source_path = original/'container/tasks'/f'{slug}.md'
        note = ('\n\n## 协议 0.10 切换与重新准入\n\n'
                f'- 原任务：[{slug}]({source_path})；原修订 {old_revision}，新修订 {d["revision"]}。\n'
                '- 旧 Ready Gate 已失效；preparation=draft。重新核对方案、授权、现有候选及 Cohestra 绑定后才能 ready。\n'
                '- 首个新 Run 的 previous_run=null；归档来源仅作审计，不作为新版运行时来源链。\n')
        if prior:
            note += (f'- 原执行来源：[{prior["run"]}]({original/"container/runs"/(prior["run"]+".md")})；'
                     f'原结果 {prior["state"]}。原失败或受阻原因必须有解除证据，不能借切换绕过。\n')
        for dep in closed_deps:
            note += f'- 已完成前置输入：[{dep}]({original/"container/tasks"/(dep+".md")})；核对归档证据，不再作为当前队列依赖。\n'
        raw = rewrite_links(dump(d, item['body']), root/'tasks'/f'{slug}.md', root/'tasks'/f'{slug}.md', moved, project)
        (stage/'tasks'/f'{slug}.md').write_bytes(raw + note.encode())
        migrations.append({'slug': slug, 'old_revision': old_revision, 'new_revision': d['revision'], 'flow': d['flow']})
    readme = stage/'README.md'
    readme.write_text(f'# 项目任务编排上下文\n\n- 项目：{project.name}\n- 当前采用发行版：{plan["versions"]["cadra"]["source"]["version"]}\n- 任务/Run 协议：0.10\n\n[tasks/](tasks/) 保存当前待办定义，全部需要重新 ready；[runs/](runs/) 从新的 0.10 来源链开始。\n\n旧容器原件与历史执行事实已归档，不参与扫描或准入。已完成任务不会重新入队。\n\n归档：[切换清单]({archive}/manifest.json)；[原始初始化记录]({original}/container/README.md)。\n')
    changes = []
    for p in references(project, root):
        before = p.read_bytes()
        after = rewrite_links(before, p, p, moved, project)
        if before != after:
            backup = original/'references'/p.relative_to(project)
            backup.parent.mkdir(parents=True, exist_ok=True); backup.write_bytes(before)
            changes.append((p, before, after))
    view_moved = {root/k: original/'container'/k for k in plan['container']}
    view_moved.update({root: original/'container', root/'tasks': original/'container/tasks', root/'runs': original/'container/runs'})
    for key in plan['container']:
        parent = Path(key).parent
        while parent != Path('.'):
            view_moved[root/parent] = original/'container'/parent
            parent = parent.parent
    for key in plan['container']:
        p = root/key
        if p.suffix != '.md': continue
        view = archive/'views'/key
        view.parent.mkdir(parents=True, exist_ok=True)
        view.write_bytes(rewrite_links((original/'container'/key).read_bytes(), p, view, view_moved, project))
    # Recheck all files and package sources before the first live replacement.
    require(inspect(project, installation, source)['sha256'] == expected, 'inputs changed during preparation')
    manifest = {'project': str(project), 'installation': str(installation), 'before': plan,
                'migrations': migrations, 'references': [str(p.relative_to(project)) for p,_,_ in changes],
                'reference_before': {str(p.relative_to(project)): sha(before) for p,before,_ in changes},
                'state': 'prepared', 'after': {'container': files(stage),
                'installed': plan['packages'], 'references': {str(p.relative_to(project)): sha(after) for p,_,after in changes}}}
    save = lambda: atomic_write(archive/'manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode())
    save()
    (archive/'README.md').write_text('# Cadra 0.10 切换归档\n\noriginal/ 保留逐字节原件；views/ 提供按原位置解析后修复链接的阅读副本。manifest.json 记录版本、SHA-256、待办映射及恢复状态。恢复前拒绝覆盖新增工作。\n')
    replace_tree(root, stage, expected=plan['container'])
    for name in PACKAGES:
        require(files(installation/name) == plan['installed'][name], 'installed copy changed during cutover')
        require(files(source/name) == plan['packages'][name], 'source changed during cutover')
        replace_tree(installation/name, source/name, expected=plan['installed'][name])
    for p, before, after in changes:
        require(p.read_bytes() == before, 'reference changed during cutover')
        atomic_write(p, after, before)
    require(files(root) == files(stage), 'container readback mismatch')
    require(all(files(installation/n) == plan['packages'][n] for n in PACKAGES), 'installed copy readback mismatch')
    manifest.update(state='completed', after={'container': files(root), 'installed': {n: files(installation/n) for n in PACKAGES},
                                            'references': {str(p.relative_to(project)): sha(after) for p,_,after in changes}})
    save()
    return archive


def rollback_locked(archive):
    archive = safe(archive)
    m = json.loads((archive/'manifest.json').read_text())
    require(m.get('state') in ('prepared', 'completed'), 'cutover is not restorable')
    project, installation = Path(m['project']), Path(m['installation'])
    root = project/'.yuzio/cadra'
    require(archive.parent == project/'.yuzio/cadra-archive', 'archive project mismatch')
    container_state = tree_state(root, m['before']['container'], m['after']['container'])
    require(files(archive/'original/container') == m['before']['container'], 'backup changed')
    package_states = {}
    for name in PACKAGES:
        package_states[name] = tree_state(installation/name, m['before']['installed'][name], m['after']['installed'][name])
        require(files(archive/'original/installed'/name) == m['before']['installed'][name], 'installation backup changed')
    reference_bytes = {}
    for key, digest in m['after']['references'].items():
        require(not Path(key).is_absolute() and '..' not in Path(key).parts, 'invalid reference path')
        before_sha = sha((archive/'original/references'/key).read_bytes())
        require(before_sha == m['reference_before'][key], 'reference backup changed')
        raw = safe(project/key).read_bytes()
        require(sha(raw) in (digest, before_sha), 'reference changed; refuse rollback')
        reference_bytes[key] = raw
    restore_tree(root, archive/'original/container', m['before']['container'], m['after']['container'], archive, 'container', container_state)
    for name in PACKAGES:
        restore_tree(installation/name, archive/'original/installed'/name, m['before']['installed'][name],
                     m['after']['installed'][name], archive, name, package_states[name])
    for key in m['references']:
        atomic_write(project/key, (archive/'original/references'/key).read_bytes(), reference_bytes[key])
    require(files(root) == m['before']['container'], 'restoration readback failed')
    require(all(files(installation/n) == m['before']['installed'][n] for n in PACKAGES), 'installed restoration readback failed')
    m['state'] = 'rolled_back'
    atomic_write(archive/'manifest.json', (json.dumps(m, ensure_ascii=False, indent=2)+'\n').encode())


@contextmanager
def file_lock(path):
    import fcntl
    path = safe(path)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Run writer is active; keep original environment') from None
        yield
    finally:
        os.close(fd)


def apply(plan, expected):
    require(plan['sha256'] == expected, 'plan changed; inspect again')
    root = Path(plan['project']) / '.yuzio/cadra'
    with file_lock(root.parent/'.cadra-cutover.lock'), file_lock(root/'runs/.writer.lock'):
        return apply_locked(plan, expected)


def rollback(archive):
    archive = safe(archive)
    m = json.loads((archive/'manifest.json').read_text())
    root = safe(Path(m['project'])/'.yuzio/cadra')
    require(archive.parent == root.parent/'cadra-archive', 'archive project mismatch')
    lock_root = root if root.exists() else root.with_name(root.name+'.cutover-old')
    with file_lock(root.parent/'.cadra-cutover.lock'), file_lock(lock_root/'runs/.writer.lock'):
        rollback_locked(archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path)
    parser.add_argument('--installation', type=Path)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    try:
        if args.rollback:
            rollback(args.rollback); print('restored verified backups'); return
        require(args.project and args.installation, '--project and --installation are required')
        plan = inspect(args.project, args.installation, args.source)
        if args.apply:
            print(apply(plan, args.expected_sha256))
        else:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as e:
        parser.exit(1, str(e)+'\n')


if __name__ == '__main__':
    main()

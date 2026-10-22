#!/usr/bin/env python3
"""Cadra package structure checks; not agent or runtime validation.

No wording, paragraph-count or duplicated-entrypoint assertions are used here.
"""
from pathlib import Path
import json
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
FAILURES = []
LINK_RE = re.compile(r'\[[^\]]*\]\(([^)]+)\)')


def check_links(files):
    total = broken = 0
    for path in map(Path, files):
        for target in LINK_RE.findall(path.read_text(encoding='utf-8')):
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            total += 1
            resolved = path.parent / unquote(parsed.path)
            if not resolved.exists():
                broken += 1
                FAILURES.append(f'{path}: missing {target}')
    return total, broken


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    match = re.match(r'\A---\n(.*?)\n---(?:\n|$)', text, re.S)
    if not match:
        FAILURES.append(f'{path}: missing Front Matter')
        return ''
    return match[1]


def keys(block):
    return set(re.findall(r'^([a-z_]+):', block, re.M))


def check_package():
    release = json.loads((ROOT / 'cadra/release.json').read_text())
    if not re.fullmatch(r'\d+\.\d+\.\d+', release['version']):
        FAILURES.append('Invalid release version')
    if release['skill_path'] != 'cadra':
        FAILURES.append('Invalid skill_path')
    skill = frontmatter(ROOT / 'cadra/SKILL.md')
    if not {'name', 'description'} <= keys(skill):
        FAILURES.append('Skill metadata incomplete')
    task = frontmatter(ROOT / 'cadra/assets/task.md')
    run = frontmatter(ROOT / 'cadra/assets/run.md')
    for label, block, required in [
        ('task', task, {'protocol', 'slug', 'revision', 'preparation', 'flow', 'cohestra_task', 'revision_base', 'changed_fields'}),
        ('run', run, {'protocol', 'run_id', 'status', 'execution_mode', 'tasks', 'reports'}),
    ]:
        if not required <= keys(block):
            FAILURES.append(f'{label} template missing fields: {required - keys(block)}')
        match = re.search(r'^protocol:\s*"([\d.]+)"$', block, re.M)
        if not match or match[1] != release['protocol_version']:
            FAILURES.append(f'{label} protocol mismatch')
    if {'status', 'state', 'budget', 'calls', 'result', 'current_run'} & keys(task):
        FAILURES.append('Task template stores execution state')
    if (ROOT / 'cadra/assets/project/queue').exists():
        FAILURES.append('Obsolete queue template remains')
    for entry in ('add', 'ready', 'list', 'run', 'resume', 'report'):
        path = ROOT / f'cadra/references/{entry}.md'
        if not path.is_file():
            FAILURES.append(f'Missing entry {entry}')
        if f'references/{entry}.md' not in (ROOT / 'cadra/SKILL.md').read_text():
            FAILURES.append(f'Unreachable entry {entry}')
    contract = (ROOT / 'cadra/references/contract.md').read_text()
    block = re.search(r'```yaml\n(.*?)```', contract, re.S)
    if not block:
        FAILURES.append('Missing contract reference')
    else:
        required = {'contract', 'task', 'status', 'execution_mode', 'stage_result', 'candidate', 'findings', 'acceptance', 'next', 'blocked'}
        if keys(block[1]) != required:
            FAILURES.append('Cohestra contract field mismatch')
        version = re.search(r'^contract:\s*"([\d.]+)"', block[1], re.M)
        source = (ROOT / 'cohestra/references/workflow.md').read_text()
        if not version or f'contract: "{version[1]}"' not in source:
            FAILURES.append('Cohestra contract version mismatch')
    for path in (ROOT / 'README.md', ROOT / 'README.zh-CN.md'):
        body = path.read_text()
        if f"**{release['version']}**" not in body or f"**v{release['protocol_version']}**" not in body:
            FAILURES.append(f'{path.name}: release metadata mismatch')
    return release


def main():
    FAILURES.clear()
    release = check_package()
    files = list((ROOT / 'cadra').rglob('*.md')) + [ROOT / 'README.md', ROOT / 'README.zh-CN.md', ROOT / 'tests/cadra/scenarios.md']
    total, broken = check_links(files)
    print(f"Cadra {release['version']} / v{release['protocol_version']}: {len(files)} documents, {total} relative links, {broken} broken")
    for problem in FAILURES:
        print(f'FAIL: {problem}')
    print('PASS: package structure' if not FAILURES else f'FAIL: {len(FAILURES)} checks')
    return bool(FAILURES)


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Cadra package structure checks; not agent or runtime validation.

No wording, paragraph-count or duplicated-entrypoint assertions are used here.
"""
from pathlib import Path
import json
import re
import unittest

from shared.package_checks import SkillPackageChecks, frontmatter, keys

ROOT = Path(__file__).resolve().parents[2]

def check_package():
    failures = []
    release = json.loads((ROOT / 'cadra/release.json').read_text())
    task = frontmatter(ROOT / 'cadra/assets/task.md')
    run = frontmatter(ROOT / 'cadra/assets/run.md')
    for label, block, required in [
        ('task', task, {'protocol', 'slug', 'revision', 'preparation', 'flow', 'cohestra_task', 'revision_base', 'changed_fields'}),
        ('run', run, {'protocol', 'run_id', 'status', 'execution_mode', 'tasks', 'reports'}),
    ]:
        if not required <= keys(block):
            failures.append(f'{label} template missing fields: {required - keys(block)}')
        match = re.search(r'^protocol:\s*"([\d.]+)"$', block, re.M)
        if not match or match[1] != release['protocol_version']:
            failures.append(f'{label} protocol mismatch')
    if {'status', 'state', 'budget', 'calls', 'result', 'current_run'} & keys(task):
        failures.append('Task template stores execution state')
    if (ROOT / 'cadra/assets/project/queue').exists():
        failures.append('Obsolete queue template remains')
    for entry in ('add', 'ready', 'list', 'run', 'resume', 'report'):
        path = ROOT / f'cadra/references/{entry}.md'
        if not path.is_file():
            failures.append(f'Missing entry {entry}')
        if f'references/{entry}.md' not in (ROOT / 'cadra/SKILL.md').read_text():
            failures.append(f'Unreachable entry {entry}')
    contract = (ROOT / 'cadra/references/contract.md').read_text()
    block = re.search(r'```yaml\n(.*?)```', contract, re.S)
    if not block:
        failures.append('Missing contract reference')
    else:
        required = {'contract', 'task', 'status', 'execution_mode', 'stage_result', 'candidate', 'findings', 'acceptance', 'next', 'blocked'}
        if keys(block[1]) != required:
            failures.append('Cohestra contract field mismatch')
        version = re.search(r'^contract:\s*"([\d.]+)"', block[1], re.M)
        source = (ROOT / 'cohestra/references/workflow.md').read_text()
        if not version or f'contract: "{version[1]}"' not in source:
            failures.append('Cohestra contract version mismatch')
    return failures


class CadraPackagingTests(SkillPackageChecks, unittest.TestCase):
    package = ROOT / "cadra"

    def test_task_run_and_cohestra_contracts(self):
        self.assertEqual(check_package(), [])


if __name__ == '__main__':
    unittest.main()

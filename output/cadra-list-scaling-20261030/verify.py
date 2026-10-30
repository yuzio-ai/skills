#!/usr/bin/env python3
"""Compare frozen 0.13 and candidate native list readers on immutable data.

Synthetic queue fixtures have no real agent/tool execution. Real history is
copied byte-for-byte to a stable temporary snapshot. Times are cold Python
process wall times, excluding parent tokenization; not model/billing latency.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

AT = '2026-10-30T08:00:00+08:00'


def load(path):
    spec = importlib.util.spec_from_file_location('scaling_reader', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def doc(value, body=''):
    return '---\n' + packed(value) + '\n---\n' + body


def fingerprints(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in root.rglob('*.md')}


def queue_fixture(project, n, protocol, task_format='json'):
    root = project / '.yuzio/cadra'
    for folder in ('tasks', 'runs'):
        (root / folder).mkdir(parents=True)
    run = dict(protocol=protocol, run_id='run-20261030-01', status='running', execution_mode='unattended',
               skill_version='0.10.0' if protocol == '0.10' else '0.13.0', created_at=AT,
               executor=dict(instance_id='synthetic-owner', generation=1, host_id='fixture-host',
                             thread_id='fixture-thread', turn_id='fixture-turn', claimed_at=AT,
                             progress=dict(at=AT, event='run_created')),
               ownership_history=[], reports=[], append_history=[],
               preflight=[dict(scope='project', status='passed', at=AT, inputs={}, evidence='synthetic project preflight')], tasks=[])
    if protocol == '0.11':
        run['scheduler'] = dict(events=[])
    for i in range(n):
        slug = f'task-{i:05}'
        task = dict(protocol=protocol, slug=slug, title='Synthetic task ' + slug, revision=1, preparation='ready',
                    priority='medium', dependencies=[], flow='code',
                    execution_policy=dict(stop_queue_on_failure=False),
                    cohestra_task=f'.yuzio/cohestra/handoffs/{slug}/', revision_base=None,
                    changed_fields=[], created_at=AT)
        if protocol == '0.11':
            task['ready_scope'] = dict(revision=1, scope=dict(mode='parallel', files=[f'src/{slug}.swift'], dirs=[]), inputs={})
        body = '# Synthetic task\n\n## Requirement\n\nSynthetic requirement.\n'
        source = (doc(task, body) if task_format == 'json' else
                  '---\n' + '\n'.join(k + ': ' + packed(v) for k,v in task.items()) + '\n---\n' + body)
        (root / 'tasks' / (slug + '.md')).write_text(source)
        run['tasks'].append(dict(slug=slug, revision=1, previous_run=None, state='queued',
            definition={**task, 'source_document': source}, start_action=dict(kind='first_start', stage='code'),
            authorization_consumed=False, budget=dict(calls=0, remediation=0, retries={}),
            checkpoint=dict(pending_call=None, last_delivery=None), calls=[], result=None,
            agents=[dict(id='worker-1', role='worker', agent_id='synthetic-worker-' + slug, host_id='fixture-host',
                         created_at=AT, source='synthetic identity only; no actual agent', supersedes=None, stop_observation=None)]))
        run['preflight'].append(dict(scope='task', slug=slug, status='passed', at=AT, inputs={}, evidence='synthetic task preflight'))
    (root / 'runs' / (run['run_id'] + '.md')).write_text(doc(run))
    return run


def role_facts(value):
    result = {}
    details = value.get('role_details', {})
    if isinstance(details, list):
        for row in details:
            result[(row['run'], row['slug'])] = (row['executor'], row['agents'])
    else:
        for rid, run in details.items():
            for slug, agents in run['agents'].items():
                result[(rid, slug)] = (run['executor'], agents)
    for run in value['queues'] + value['runs']:
        if 'executor' in run:
            for slug, agents in run.get('agents', {}).items():
                result[(run['run'], slug)] = (run['executor'], agents)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-package', type=Path, required=True)
    parser.add_argument('--candidate-package', type=Path, required=True)
    parser.add_argument('--history-project', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--sizes', type=int, nargs='+', default=[1000, 10000])
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='cadra-list-scale-'))
    baseline = work / 'baseline/cadra'
    candidate = work / 'candidate/cadra'
    shutil.copytree(args.baseline_package, baseline)
    shutil.copytree(args.candidate_package, candidate)
    # Hold unrelated scheduler changes constant; the reader/guard changes are
    # the intended comparison. Both record validators still run in each mode.
    shutil.copyfile(candidate / 'scripts/scheduler.py', baseline / 'scripts/scheduler.py')
    readers = dict(baseline=baseline / 'scripts/list_summary.py', candidate=candidate / 'scripts/list_summary.py')
    reader = load(readers['candidate'])
    try:
        import tiktoken
    except ImportError:
        encoding = None
    else:
        encoding = tiktoken.get_encoding('o200k_base')
    report = dict(at=datetime.now(timezone.utc).isoformat(), work=str(work),
                  baseline_version=json.loads((baseline / 'release.json').read_text())['version'],
                  candidate_version=json.loads((candidate / 'release.json').read_text())['version'],
                  reader_sha256={k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in readers.items()},
                  shared_scheduler_sha256=hashlib.sha256((candidate / 'scripts/scheduler.py').read_bytes()).hexdigest(),
                  tokenizer='o200k_base' if encoding else None, synthetic=[], history=[],
                  methodology='Cold process samples; immutable input; full record validation before filtering. Token counts cover returned data only. No agent execution, migration, installation or model billing measurement.')

    def query(label, project, options, repeats):
        samples, outputs = [], []
        for _ in range(repeats):
            start = time.perf_counter()
            proc = subprocess.run([sys.executable, '-B', str(readers[label]), '--project', str(project), *options],
                                  text=True, capture_output=True, check=True)
            samples.append(time.perf_counter() - start)
            outputs.append(proc.stdout)
        assert len(set(outputs)) == 1, 'unstable query output'
        result = json.loads(outputs[-1])
        assert result['scan']['stable']
        normalized = outputs[-1].replace(str(project), '/benchmark/project')
        stats = dict(seconds=dict(median=statistics.median(samples), min=min(samples), max=max(samples), samples=samples),
                     bytes=len(normalized.encode()), tokens=len(encoding.encode_ordinary(normalized)) if encoding else None,
                     counts=result['counts'], total=result['total'], issues=len(result['issues']))
        return result, stats

    for protocol in ('0.10', '0.11'):
        for n in args.sizes:
            project = work / f'queue-{protocol}-{n}'
            queue_fixture(project, n, protocol)
            before = fingerprints(project)
            measurement = dict(protocol=protocol, tasks=n, run_entries=n, scenarios={})
            for scenario, flags, repeats in [('default', [], args.repeats), ('roles', ['--roles'], 1),
                                             ('single', ['--slug', f'task-{n//2:05}'], 1)]:
                results, stats = {}, {}
                for label in readers:
                    results[label], stats[label] = query(label, project, flags, repeats)
                    assert stats[label]['counts'] == {'queued': 1 if scenario == 'single' else n}
                    assert stats[label]['issues'] == 0
                    print(packed(dict(protocol=protocol, size=n, scenario=scenario, reader=label,
                                      seconds=round(stats[label]['seconds']['median'], 4))), flush=True)
                if scenario == 'roles':
                    assert role_facts(results['baseline']) == role_facts(results['candidate'])
                stats['speedup'] = stats['baseline']['seconds']['median'] / stats['candidate']['seconds']['median']
                measurement['scenarios'][scenario] = stats
            assert before == fingerprints(project), 'fixture changed by list'
            measurement['records_unchanged'] = True
            # Dense anomalies exercise the per-row issue lookup, independent
            # of active-Run ownership. Change fixture deliberately between tests.
            run_path = project / '.yuzio/cadra/runs/run-20261030-01.md'
            run_path.write_text(doc(dict(protocol=protocol, run_id='run-20261030-01', status='invalid')))
            before_bad = fingerprints(project)
            bad = {}
            for label in readers:
                result, bad[label] = query(label, project, [], 1)
                assert result['counts'] == {'unknown': n} and result['issues']
            assert before_bad == fingerprints(project)
            measurement['scenarios']['dense_anomalies'] = bad
            report['synthetic'].append(measurement)
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    original_root = args.history_project / '.yuzio/cadra'
    source_paths = sum(reader.inventory(original_root), [])
    raw = {p: p.read_bytes() for p in source_paths}
    assert source_paths == sum(reader.inventory(original_root), []) and all(p.read_bytes() == v for p,v in raw.items())
    history = work / 'real-history'
    for p, value in raw.items():
        target = history / p.relative_to(args.history_project)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
    history_before = fingerprints(history)
    run_records = [reader.guard.read_json(reader.guard.split_document(p.read_bytes())[0])
                   for p in reader.inventory(history / '.yuzio/cadra')[1]]
    rid = max(run_records, key=lambda d:len(d['tasks']))['run_id']
    for scenario, flags in [('default', []), ('roles', ['--roles']), ('run', ['--run', rid])]:
        results, stats = {}, {}
        for label in readers:
            results[label], stats[label] = query(label, history, flags, args.repeats)
        assert results['baseline']['counts'] == results['candidate']['counts']
        assert not results['candidate']['issues']
        if scenario in ('roles', 'run'):
            assert role_facts(results['baseline']) == role_facts(results['candidate'])
        if scenario == 'run':
            full, _ = query('candidate', history, flags + ['--full-results'], 1)
            old_rows = results['baseline']['runs'][0]['queue']
            new_rows = results['candidate']['runs'][0]['queue']
            full_rows = full['runs'][0]['queue']
            for old, new, original in zip(old_rows, new_rows, full_rows):
                assert old['slug'] == new['slug'] == original['slug']
                assert old['result'] == original['result']
                if old['result'] is not None:
                    for key in ('state','reason','findings','acceptance','next','human_intervention','source','at'):
                        if key in old['result']:
                            assert old['result'][key] == new['result'][key]
        if encoding:
            stats['token_reduction_percent'] = 100 * (1 - stats['candidate']['tokens'] / stats['baseline']['tokens'])
        report['history'].append(dict(view=scenario, run=rid if scenario=='run' else None, comparison=stats))
    assert history_before == fingerprints(history)
    report['history_source'] = dict(project=str(args.history_project), tasks=len(reader.inventory(original_root)[0]),
                                    runs=len(run_records), frozen_records_unchanged=True,
                                    source_files=[dict(path=str(p.relative_to(args.history_project)), sha256=hashlib.sha256(v).hexdigest())
                                                  for p,v in raw.items()])
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(packed(dict(report=str(args.report), cases=len(report['synthetic']), history=report['history'])), flush=True)


if __name__ == '__main__':
    main()

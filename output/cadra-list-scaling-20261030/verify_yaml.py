#!/usr/bin/env python3
"""Validate thousand/ten-thousand YAML Tasks with the native reader."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate-package', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    spec = importlib.util.spec_from_file_location('queue_fixtures', Path(__file__).with_name('verify.py'))
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    script = args.candidate_package / 'scripts/list_summary.py'
    rows = []
    work = Path(tempfile.mkdtemp(prefix='cadra-list-yaml-'))
    for protocol in ('0.10', '0.11'):
        for size in (1000, 10000):
            project = work / f'{protocol}-{size}'
            fixtures.queue_fixture(project, size, protocol, task_format='yaml')
            before = fixtures.fingerprints(project)
            start = time.perf_counter()
            proc = subprocess.run([sys.executable, '-B', str(script), '--project', str(project)],
                                  capture_output=True, text=True, check=True)
            elapsed = time.perf_counter() - start
            result = json.loads(proc.stdout)
            assert result['counts'] == {'queued': size} and not result['issues'] and result['scan']['stable']
            assert before == fixtures.fingerprints(project)
            rows.append(dict(protocol=protocol, tasks=size, format='YAML Task / JSON Run', seconds=elapsed,
                             counts=result['counts'], issues=0, records_unchanged=True))
            print(json.dumps(rows[-1]), flush=True)
    report = dict(reader_sha256=hashlib.sha256(script.read_bytes()).hexdigest(), work=str(work), cases=rows,
                  scope='Native CLI, synthetic records and identities; no execution or migration. Single timing sample per format case.')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()

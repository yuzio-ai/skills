"""Assert fault/recovery invariants from archived bytes; does not perform recovery."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
RUN = '.yuzio/cadra/runs/run-20261022-02.md'

def read(path):
    return json.loads(path.read_text())

def front(path):
    return json.loads(path.read_text().split('---', 2)[1])

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify():
    results = {}
    for case in read(ROOT / 'session.json')['cases']:
        name = case['case']; root = ROOT / name
        before = read(root / 'before-hashes.json'); after = read(root / 'after-hashes.json')
        assert case['fault']['writer_exit_code'] == -9
        for label, manifest in [('before', before), ('after', after)]:
            for path, expected in manifest.items():
                assert digest(root / label / path) == expected, (name, label, path)
        changes = [path for path, expected in before.items() if after.get(path) != expected]
        allowed = {RUN, '.yuzio/cohestra/handoffs/greeting-service/README.md'}
        assert set(changes) <= allowed, (name, changes)
        report = read(root / 'after/verification/recovery-result.json')
        repeat = report['repeat_resume']
        prior = repeat.get('before_hashes', repeat.get('before'))
        later = repeat.get('after_hashes', repeat.get('after'))
        assert isinstance(prior, dict) and prior == later, (name, 'repeat resume')
        if name == 'run_primary_partial':
            assert changes == [], changes
            try:
                front(root / 'after' / RUN)
            except (ValueError, IndexError, UnicodeError):
                pass
            else:
                raise AssertionError('Corrupted Run was silently reconstructed')
            added_stages = list((root / 'after/.yuzio/cohestra/handoffs/greeting-service').glob('*-02.md'))
            assert not added_stages
            # No business or skill-state file may be created when the Run is unreadable.
            assert not [p for p in set(after)-set(before) if p.startswith('.yuzio/')]
            results[name] = {'passed': True, 'status': 'record_unknown_stop', 'budget': 'unknown; not reconstructed', 'old_files_changed': changes}
            continue
        initial = front(root / 'before' / RUN)['tasks'][0]
        final_run = front(root / 'after' / RUN)
        final = final_run['tasks'][0]
        assert final_run['status'] in ('completed', 'stopped')
        for field in ['id', 'stage', 'before', 'prepared_at', 'charged']:
            assert initial['calls'][0][field] == final['calls'][0][field], (name, field)
        if name == 'run_replace_ack_lost':
            assert initial['calls'][0] == final['calls'][0]
        assert final['authorization_consumed'] == initial['authorization_consumed']
        if name == 'handoff_partial':
            assert final['state'] == 'failed'
            assert len(final['calls']) == 1 and final['budget'] == initial['budget']
            assert not final['calls'][0]['closed']
            assert not [p for p in set(after)-set(before) if p.startswith('.yuzio/cohestra/')]
        else:
            assert final['state'] == 'completed' and final['result']['acceptance'] == 'passed'
            assert [c['id'] for c in final['calls']] == [1, 2, 3]
            assert [c['stage'] for c in final['calls']] == ['code', 'review', 'validate']
            assert final['budget'] == {'calls': 3, 'remediation': 0, 'retries': {}}
            assert all(c['closed'] for c in final['calls'])
            assert sum(c['charged']['calls'] for c in final['calls']) == final['budget']['calls']
            stages = root / 'after/.yuzio/cohestra/handoffs/greeting-service'
            assert sorted(p.name for p in stages.glob('code-*.md')) == ['code-01.md']
            for stage in ['review', 'validate']:
                assert sorted(p.name for p in stages.glob(stage+'-*.md')) == [stage+'-01.md']
        results[name] = {'passed': True, 'status': final['state'], 'calls': len(final['calls']),
                         'budget': final['budget'], 'original_call_preserved': True,
                         'old_files_changed': changes, 'all_other_old_files_unchanged': len(before)-len(changes)}
    source = read(ROOT / 'source-before.json')
    repo = ROOT.parents[3]
    assert all(digest(repo / p) == sha for p, sha in source.items())
    session = read(ROOT / 'session.json')
    assert all(digest(Path(session['source']) / p) == sha for p, sha in session['source_hashes'].items())
    return {'passed': True, 'cases': results, 'skill_source_files_unchanged': len(source)}

if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))

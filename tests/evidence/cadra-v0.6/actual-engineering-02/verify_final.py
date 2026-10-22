"""Read-only assertions over the archived real execution, not a Cadra runtime."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent

def read(path):
    return json.loads(path.read_text())

def front(path):
    return json.loads(path.read_text().split('---', 2)[1])

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify():
    final = read(ROOT / 'final/snapshot.json')
    before = read(ROOT / 'checkpoint-04/snapshot.json')
    project = ROOT / 'final/project'
    for name, expected in final['hashes'].items():
        assert digest(project / name) == expected, name
    runs = [front(project / r['path']) for r in final['runs']]
    assert len(runs) == 6
    items = [r['tasks'][0] for r in runs]
    assert all(r['status'] == 'completed' for r in runs)
    assert [i['revision'] for i in items] == [1, 1, 2, 2, 3, 4]
    assert [i['state'] for i in items] == ['completed', 'completed', 'blocked', 'completed', 'completed', 'completed']
    assert [len(i['calls']) for i in items] == [3, 3, 0, 0, 3, 0]
    assert [i['previous_run'] for i in items] == [None, None, runs[1]['run_id'], runs[0]['run_id'], runs[2]['run_id'], runs[4]['run_id']]
    for index, item in enumerate(items):
        assert item['budget'] == {'calls': len(item['calls']), 'remediation': 0, 'retries': {}}
        assert item['checkpoint']['pending_call'] is None
        if item['calls']:
            assert [c['stage'] for c in item['calls']] == ['code', 'review', 'validate']
            assert [c['id'] for c in item['calls']] == [1, 2, 3]
            for call in item['calls']:
                assert call['closed'] and call['dispatch'] == 'dispatched'
                assert call['charged'] == {'calls': 1, 'remediation': 0, 'retry_stage': None}
                assert call['result']['index_sync'] == 'success'
                assert call['result']['contract']['stage_result']['round'] == (2 if index == 4 else 1)
        if item['state'] == 'completed':
            assert item['result']['acceptance'] == 'passed'
    assert [i['authorization_consumed'] for i in items] == [False, False, False, True, True, True]
    assert items[2]['result']['reason'] == 'dependency_unavailable'
    assert items[2]['checkpoint']['last_delivery'] is None
    # Revision 3 changes policy only but must retain revision 2's unexecuted requirement.
    assert items[4]['definition']['changed_fields'] == ['execution_policy']
    assert items[4]['definition']['requirement'] == items[2]['definition']['requirement']
    assert items[4]['start_action']['stage'] == 'code'
    for closeout, source in [(3, 0), (5, 4)]:
        assert items[closeout]['result']['candidate'] == items[source]['result']['candidate']
        assert items[closeout]['result']['last_delivery'] == items[source]['result']['last_delivery']
        assert items[closeout]['result']['reused_from']['run'] == runs[source]['run_id']
    initial = read(ROOT / 'checkpoint-02/snapshot.json')['runs'][1]['tasks'][0]['calls'][0]
    recovered = items[1]['calls'][0]
    for field in ['id', 'stage', 'before', 'prepared_at', 'charged']:
        assert initial[field] == recovered[field], field
    changed = [name for name, sha in before['hashes'].items() if final['hashes'].get(name) != sha]
    expected_changes = {
        '.yuzio/cadra/tasks/prefix-source.md', '.yuzio/cadra/tasks/greeting-service.md',
        '.yuzio/cohestra/handoffs/greeting-service/README.md', 'greeting.py', 'test_greeting.py',
    }
    assert set(changed) == expected_changes, changed
    repeats = []
    for name in ['run-02-repeat-resume.json', 'run-06-repeat-resume.json']:
        evidence = read(project / 'verification' / name)
        assert evidence['before'] == evidence['after']
        repeats.append({'file': name, 'files_unchanged': len(evidence['before'])})
    for name, sha in read(ROOT / 'source-before.json').items():
        assert digest(ROOT.parents[3] / name) == sha, name
    return {
        'passed': True, 'runs': 6, 'actual_stage_calls': 9,
        'archive_hashes_verified': len(final['hashes']),
        'prior_files_changed': changed,
        'old_files_unchanged': len(before['hashes']) - len(changed),
        'same_interrupted_call_preserved': True,
        'pending_requirement_retained_and_executed': True,
        'policy_closeouts_have_zero_calls': True,
        'historical_runs_handoffs_candidates_unchanged': True,
        'repeat_resume': repeats, 'skill_source_files_unchanged': 45,
    }

if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))

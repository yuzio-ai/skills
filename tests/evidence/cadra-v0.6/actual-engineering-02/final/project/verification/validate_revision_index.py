"""Validate one supplied publication; no dispatch or stage selection."""
import json, sys
from pathlib import Path
from record_io import read, sha, now

p = Path(sys.argv[1])
e = json.loads(Path(sys.argv[2]).read_text())
c, body = read(p)
assert c == e['contract']
assert c['contract'] == '0.8' and c['task'] == 'greeting-service'
assert c['execution_mode'] == 'unattended'
assert c['stage_result'] == {'stage': e['stage'], 'status': 'completed', 'round': e['round']}
assert c['candidate'] == e['candidate']
assert c['blocked'] == {'value': False, 'reason': None}
assert c['next']['stage'] == e['next_stage']
if e['stage'] == 'validate':
    assert c['status'] == 'completed'
    assert c['acceptance'] == {'status': 'passed'}
    assert c['next'] == {'stage': None, 'allowed': False, 'reason': 'task_completed'}
else:
    assert c['status'] == 'in_progress'
    assert c['next'] == {'stage': e['next_stage'], 'allowed': True, 'reason': 'stage_completed'}
    assert c.get('acceptance', {}).get('status') != 'passed'
if e['stage'] != 'code':
    assert c['findings'] == {'blocking': 0, 'non_blocking': 0, 'unresolved': 0}
h = Path(e['handoff'])
assert sha(h) == e['handoff_sha256']
assert h.name == f"{e['stage']}-{e['round']:02d}.md"
for word in ['cohestra v0.8', '0.10.1', 'unattended']:
    assert word in h.read_text()
for phrase in e['required_body']:
    assert phrase in body
assert sha(e['manifest']) == e['manifest_sha256']
for item in json.loads(Path(e['manifest']).read_text())['files'].values():
    assert sha(item['snapshot']) == item['sha256']
proof = {'validated': True, 'parser': 'JSON subset of YAML 1.2', 'pending_path': str(p),
         'sha256': sha(p), 'stage': e['stage'], 'round': e['round'],
         'candidate': c['candidate'], 'handoff_sha256': sha(h), 'time': now()}
Path(str(p) + '.validation.json').write_text(json.dumps(proof, indent=2))
print(json.dumps(proof))

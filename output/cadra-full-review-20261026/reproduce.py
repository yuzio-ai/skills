"""Read-only source audit; all Run mutations use disposable fixture projects.

Run with: python3 -B output/cadra-full-review-20261026/reproduce.py
Acceptance here demonstrates a validation gap, not a real agent/tool dispatch.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from cadra.test_run_guard import AT, binding, document, example, guard, pending
from cadra.model import result_valid
from cadra.test_cadra import contract


def create(root, flow='code'):
    runs = root / '.yuzio/cadra/runs'
    runs.mkdir(parents=True)
    path = runs / 'run-20261025-01.md'
    data = example(flow=flow)
    sha = guard.publish(path, document(data), None, 'first', 1, 'create')
    return path, data, sha


def save(path, data, sha):
    return guard.publish(path, document(data), sha, 'first', 1)


def skipped_pending():
    with tempfile.TemporaryDirectory() as tmp:
        path, data, sha = create(Path(tmp).resolve())
        data['tasks'][0]['agents'].append(binding())
        sha = save(path, data, sha)
        pending(data)
        sha = save(path, data, sha)
        task = data['tasks'][0]
        task['calls'][0].update(dispatch='dispatched', dispatch_evidence={
            'agent_id': 'agent-worker', 'source': 'synthetic audit fixture', 'at': AT})
        sha = save(path, data, sha)
        task.update(state='skipped', result={'state': 'skipped', 'reason': 'user stop fixture'})
        data['status'] = 'stopped'
        save(path, data, sha)
        saved, _ = guard.current(path.read_bytes())
        other = example()
        other['run_id'] = 'run-20261025-02'
        guard.publish(path.with_name(other['run_id'] + '.md'), document(other), None, 'first', 1, 'create')
        return {'invalid_transition_published': True, 'call_closed': task['calls'][0]['closed'],
                'pending_call': task['checkpoint']['pending_call'],
                'unfinished': guard.unfinished(saved), 'next_run_create_accepted': True}


def undercharged_budget():
    with tempfile.TemporaryDirectory() as tmp:
        path, data, sha = create(Path(tmp).resolve(), 'review')
        task = data['tasks'][0]
        before = None
        for round_ in range(1, 5):
            for stage in ('review', 'fix'):
                role = 'reviewer' if stage == 'review' else 'worker'
                if not any(b['role'] == role for b in task['agents']):
                    task['agents'].append(binding(role, 'agent-' + role, role + '-1'))
                    sha = save(path, data, sha)
                number = len(task['calls']) + 1
                call = {'id': number, 'stage': stage, 'execution_mode': 'unattended',
                        'reason': 'blocking_findings' if stage == 'fix' else 'review fixture',
                        'agent_ref': role + '-1', 'dispatch_evidence': None,
                        'before': deepcopy(before), 'dispatch': 'prepared', 'closed': False,
                        'result': None, 'prepared_at': AT,
                        'charged': {'calls': 1, 'remediation': 0, 'retry_stage': None}}
                task['state'] = 'running'
                task['calls'].append(call)
                task['budget']['calls'] += 1
                task['checkpoint']['pending_call'] = number
                sha = save(path, data, sha)
                call.update(dispatch='dispatched', dispatch_evidence={
                    'agent_id': 'agent-' + role, 'source': 'synthetic audit fixture', 'at': AT})
                sha = save(path, data, sha)
                before = contract(stage, 'fix' if stage == 'review' else 'review',
                                  'blocking_findings' if stage == 'review' else 'stage_completed', round_)
                before['task'] = 'camera'
                before['candidate']['snapshot'] = f'candidate-{round_}'
                call.update(closed=True, result={'contract': deepcopy(before), 'handoff': f'{stage}-{round_:02d}.md'})
                task['checkpoint'].update(pending_call=None, last_delivery=deepcopy(call['result']))
                sha = save(path, data, sha)
        return {'stage_sequence': [c['stage'] for c in task['calls']],
                'blocking_finding_fix_calls': 4, 'charged_remediation': task['budget']['remediation']}


def invalid_retry_stage():
    with tempfile.TemporaryDirectory() as tmp:
        path, data, sha = create(Path(tmp).resolve())
        data['tasks'][0]['agents'].append(binding())
        sha = save(path, data, sha)
        pending(data)
        task = data['tasks'][0]
        task['calls'][0]['charged']['retry_stage'] = 'made-up-stage'
        task['budget']['retries'] = {'made-up-stage': 1}
        save(path, data, sha)
        return {'published': True, 'call_stage': 'code', 'charged_retry_stage': 'made-up-stage'}


def stale_model_round():
    # This is explicitly a test-oracle gap, not proof that a live controller
    # would ignore handoff identity, candidate or dispatch/source verification.
    accepted = result_valid(contract('review', 'validate', 'stage_completed', 1),
                            'review', contract('fix', 'review', 'stage_completed', 1))
    return {'previous_review_round': 1, 'before_stage': 'fix', 'reused_review_round': 1,
            'accepted_by_result_valid': accepted, 'evidence_scope': 'test model only'}


if __name__ == '__main__':
    result = {'skipped_pending': skipped_pending(), 'undercharged_budget': undercharged_budget(),
              'invalid_retry_stage': invalid_retry_stage(), 'stale_model_round': stale_model_round()}
    print(json.dumps(result, ensure_ascii=False, indent=2))

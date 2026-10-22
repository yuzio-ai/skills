"""SIGKILL real file writers in relocated copies of an actual engineering checkpoint.

This is fault injection, not a Cadra runtime or a new historical stage execution.
"""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCE = HERE.parent / 'actual-engineering-02/checkpoint-02/project'
OLD = '/private/tmp/cadra-engineering-recovery-kvs3043i'
RUN = '.yuzio/cadra/runs/run-20261022-02.md'
HANDOFF = '.yuzio/cohestra/handoffs/greeting-service'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inventory(root):
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(root.rglob('*'))
            if p.is_file() and not any(x in p.parts for x in ('.git', '__pycache__'))}

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def writer(spec_path):
    spec = json.loads(Path(spec_path).read_text())
    target, temporary = Path(spec['target']), Path(spec['temporary'])
    payload = Path(spec['payload']).read_bytes()
    output = target if spec['mode'] == 'primary_partial' else temporary
    data = payload if spec['mode'] == 'replace' else payload[:len(payload)//2]
    with output.open('wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if spec['mode'] == 'replace':
        os.replace(temporary, target)
    print(json.dumps({'ready_to_kill': True, 'pid': os.getpid(), 'bytes_written': len(data)}), flush=True)
    sys.stdin.buffer.read(1)  # Parent sends SIGKILL before acknowledging this write.

def main():
    if (HERE / 'session.json').exists():
        raise SystemExit('Evidence already exists; use verify.py for read-only verification. Do not overwrite this run.')
    root = Path(tempfile.mkdtemp(prefix='cadra-crash-recovery-', dir='/private/tmp'))
    specs = []
    for name in ['run_temp_partial', 'run_replace_ack_lost', 'handoff_partial', 'index_temp_partial', 'run_primary_partial']:
        project = root / name
        project.mkdir()
        # Relocation is fixture preparation; original checkpoint remains untouched.
        original = {str(p.relative_to(SOURCE)): p.read_bytes() for p in SOURCE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        transformed = {k: v.replace(OLD.encode(), str(project).encode()) for k, v in original.items()}
        for _ in range(20):
            mapping = {sha(original[k]).encode(): sha(v).encode() for k, v in transformed.items() if original[k] != v}
            updated = {k: v for k, v in transformed.items()}
            for key, value in transformed.items():
                for old_hash, new_hash in mapping.items():
                    updated[key] = updated[key].replace(old_hash, new_hash)
            if updated == transformed:
                break
            transformed = updated
        else:
            raise AssertionError('relocation hash references did not converge')
        # Keep raw stage artifacts and dispatch evidence; drop prior checkpoint conclusions.
        for key, value in transformed.items():
            if key.startswith('verification/') and Path(key).name not in ('dispatch-call-01.json', 'record_io.py', 'publish_index.py'):
                continue
            path = project / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        (project / 'AGENTS.md').write_text(
            '# Isolated crash recovery fixture\n\n'
            'Use explicitly supplied source Cadra/Cohestra skills. This project is a relocated copy of a real code-01 delivery checkpoint, not a newly executed code stage. Absolute paths and dependent hashes were rebased before fault injection. A real file writer was terminated with SIGKILL. Read verification/fault.json for the boundary.\n\n'
            'Resume the specified Run according to the skills. Write only this project; no network, installs, commits, publication, or source-repository writes. Do not consult previous validation reports/models or sibling projects. If recovery requires a Cohestra index repair, it is authorized, but follow publication checks and preserve existing stage evidence. If evidence cannot support safe progress, preserve the fault and report the missing evidence. Do not invent historical executions or repair uncertain bytes by copying another fixture. Keep verification/fault.json and original fault bytes intact.\n')
        subprocess.run(['git', 'init', '-q', str(project)], check=True)
        target = project / RUN
        mode = 'partial'
        payload = target.read_bytes()
        if name == 'run_replace_ack_lost':
            text = payload.decode(); data = json.loads(text.split('---', 2)[1])
            # Acknowledgement content is based on the real completed delivery, not a stage replay.
            delivery = json.loads((project / HANDOFF / 'README.md').read_text().split('---', 2)[1])
            result = {'contract': delivery, 'handoff': str(project / HANDOFF / 'code-01.md'),
                      'index_sync': 'success', 'index_sha256': sha((project / HANDOFF / 'README.md').read_bytes()),
                      'verified_at': '2026-10-22T13:20:21.454558+08:00'}
            item = data['tasks'][0]
            item['calls'][0]['closed'] = True; item['calls'][0]['result'] = result
            item['checkpoint'] = {'pending_call': None, 'last_delivery': result}
            payload = ('---\n'+json.dumps(data,ensure_ascii=False,indent=2)+'\n---\n'+text.split('---',2)[2]).encode()
            mode = 'replace'
        elif name in ('handoff_partial', 'index_temp_partial'):
            target = project / HANDOFF / ('code-01.md' if name == 'handoff_partial' else 'README.md')
            payload = target.read_bytes()
            # First delivery: old index does not yet exist at this publication boundary.
            (project / HANDOFF / 'README.md').unlink()
            for p in (project / HANDOFF / 'scratch').glob('*index*'):
                if p.is_file(): p.unlink()
            if name == 'handoff_partial':
                mode = 'primary_partial'
        elif name == 'run_primary_partial':
            mode = 'primary_partial'
        prepared = inventory(project)
        control = root / (name + '-control')
        control.mkdir()
        (control / 'payload').write_bytes(payload)
        spec = {'target': str(target), 'temporary': str(target.with_name('.'+target.name+'.crashed.tmp')),
                'mode': mode, 'payload': str(control / 'payload')}
        save(control / 'spec.json', spec)
        process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), 'writer', str(control/'spec.json')],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        marker = json.loads(process.stdout.readline())
        assert marker['ready_to_kill'] and marker['pid'] == process.pid
        os.kill(process.pid, signal.SIGKILL)
        process.communicate(timeout=10)
        assert process.returncode == -signal.SIGKILL
        fault = {'case': name, 'mechanism': 'actual file-writer subprocess SIGKILL; relocated replay fixture',
                 'writer_pid': process.pid, 'writer_exit_code': process.returncode, 'boundary': mode,
                 'target': str(target), 'temporary': spec['temporary'], 'bytes_written': marker['bytes_written'],
                 'complete_payload_bytes': len(payload), 'readback_acknowledgement_received': False,
                 'original_call_stage': 'code', 'original_call_id': 1, 'original_budget_calls': 1,
                 'dispatch_evidence': str(project/'verification/dispatch-call-01.json')}
        save(project/'verification/fault.json', fault)
        case_evidence = HERE / name
        save(case_evidence/'prepared-hashes.json', prepared)
        save(case_evidence/'before-hashes.json', inventory(project))
        for p in project.rglob('*'):
            if p.is_file() and '.git' not in p.parts:
                dest=case_evidence/'before'/p.relative_to(project)
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
        specs.append({'case':name,'project':str(project),'fault':fault})
    save(HERE/'session.json', {'root':str(root),'source':str(SOURCE),'source_hashes':inventory(SOURCE),'cases':specs})
    save(HERE/'source-before.json', {str(p.relative_to(REPO)):sha(p.read_bytes()) for package in ('cadra','cohestra') for p in (REPO/package).rglob('*') if p.is_file()})
    print(json.dumps({'root':str(root),'cases':specs},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    writer(sys.argv[2]) if len(sys.argv)>1 and sys.argv[1]=='writer' else main()

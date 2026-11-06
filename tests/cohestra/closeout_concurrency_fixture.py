"""Isolated inputs and real process probes for live closeout-agent tests.

This generates projects, not agent decisions or stage results. Cadra records
are explicitly synthetic and validated by the shipped guard. Runtime probes
write observations only; successful closeout still requires actual agents.
"""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo


REPO = Path(__file__).resolve().parents[2]

PROBE = r'''"""Project-provided validation-resource guard and test observations."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / ".test"
FACTS.mkdir(exist_ok=True)

def emit(kind, **details):
    record = dict(kind=kind, pid=os.getpid(), wall_ns=time.time_ns(), monotonic_ns=time.monotonic_ns(), **details)
    with (FACTS / "events.jsonl").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(record, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(record, sort_keys=True), flush=True)

def wait_for(path, seconds=1800):
    end = time.monotonic() + seconds
    while not path.exists():
        if time.monotonic() >= end:
            raise TimeoutError(str(path))
        time.sleep(0.1)

mode = sys.argv[1]
if mode == "cadra-owner":
    # Liveness is real; the Run is still a declared synthetic control input.
    emit("cadra_fixture_owner_started")
    (FACTS / "cadra-owner.json").write_text(json.dumps(dict(pid=os.getpid(), source="controlled live fixture process")))
    wait_for(FACTS / "stop-cadra-owner")
    emit("cadra_fixture_owner_stopped")
elif mode == "hold-validator":
    with (FACTS / "validator.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        emit("holder_acquired", resource="shared-validator")
        wait_for(FACTS / "release-validator")
        emit("holder_releasing", resource="shared-validator")
elif mode == "validate":
    task = sys.argv[2]
    source = ROOT / ("shared.py" if (ROOT / "shared.py").exists() else task + ".py")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    emit("validation_attempt", task=task, resource="shared-validator", source_sha256=before)
    deadline = time.monotonic() + 1800
    with (FACTS / "validator.lock").open("a+") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    emit("validation_resource_unavailable", task=task)
                    sys.exit(75)
                time.sleep(0.1)
        emit("validation_acquired", task=task, resource="shared-validator")
        try:
            if hashlib.sha256(source.read_bytes()).hexdigest() != before:
                raise RuntimeError("candidate changed while waiting")
            spec = importlib.util.spec_from_file_location("candidate", source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            function = getattr(module, "normalize_" + task)
            expected = task.title() + " Untitled"
            cases = [("  Mewoo  ", "Mewoo"), ("", expected), ("   ", expected)]
            results = [dict(input=value, actual=function(value), expected=want) for value, want in cases]
            if not all(row["actual"] == row["expected"] for row in results):
                raise AssertionError(results)
            time.sleep(1)
            (FACTS / "validator-output.txt").write_text(task + "\n")
            emit("validation_passed", task=task, results=results, source_sha256=before)
        finally:
            emit("validation_releasing", task=task, resource="shared-validator")
elif mode == "watch-shared":
    previous = None
    emit("watch_started")
    deadline = time.monotonic() + 1800
    while not (FACTS / "stop-watch").exists():
        content = (ROOT / "shared.py").read_bytes()
        current = hashlib.sha256(content).hexdigest()
        if current != previous:
            emit("shared_file_observed", sha256=current, content=content.decode())
            previous = current
        if time.monotonic() >= deadline:
            raise TimeoutError("watch-shared")
        time.sleep(0.02)
    emit("watch_stopped")
else:
    raise SystemExit("unknown probe mode")
'''


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observations(project):
    """Read a complete audit snapshot while writers use the same OS lock."""
    import fcntl
    with (project / ".test/events.jsonl").open() as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        return [json.loads(line) for line in stream if line.strip()]


def shared_resource_result(project):
    """Report real invocation overlap and exclusive critical sections."""
    events = observations(project)
    attempts = [row for row in events if row["kind"] == "validation_attempt"]
    pending, intervals = {}, []
    failures = []
    for row in events:
        if row["kind"] == "validation_acquired":
            if pending:
                failures.append("overlapping validation critical sections")
            pending[row["pid"]] = row
        elif row["kind"] == "validation_releasing":
            start = pending.pop(row["pid"], None)
            if start is None:
                failures.append("release without observed acquisition")
            else:
                intervals.append(dict(task=row["task"], pid=row["pid"],
                                      start_ns=start["monotonic_ns"], end_ns=row["monotonic_ns"]))
    holder_release = next((row for row in events if row["kind"] == "holder_releasing"), None)
    if holder_release and any(row["kind"] == "validation_acquired" and row["monotonic_ns"] < holder_release["monotonic_ns"] for row in events):
        failures.append("validation entered while controller still held the resource")
    queued_tasks = sorted({row["task"] for row in attempts if holder_release and row["monotonic_ns"] < holder_release["monotonic_ns"]})
    passed_tasks = sorted({row["task"] for row in events if row["kind"] == "validation_passed"})
    return dict(attempts=attempts, intervals=intervals, pending_pids=sorted(pending),
                queued_before_holder_release=queued_tasks, passed_tasks=passed_tasks,
                failures=failures, events=events,
                complete=not failures and not pending and queued_tasks == ["alpha", "beta"]
                         and passed_tasks == ["alpha", "beta"] and len(intervals) >= 2)


def seed_cadra(project, now):
    sys.path.insert(0, str(REPO / "tests"))
    from cadra.test_run_guard import guard, example, raw_document, AT
    data = example()

    def dates(value):
        if isinstance(value, dict):
            return {key: dates(item) for key, item in value.items()}
        if isinstance(value, list):
            return [dates(item) for item in value]
        return now if value == AT else value

    data = dates(data)
    data.update(run_id="run-20261104-91", skill_version="0.17.0")
    data["executor"].update(instance_id="controlled-cadra-fixture", host_id=None,
                            thread_id=None, turn_id=None)
    data["preflight"][0]["evidence"] = "synthetic admission record for isolated concurrency test"
    data["preflight"][1]["evidence"] = "synthetic; scope restricted to cadra-owned.txt"
    inputs = {"cadra-owned.txt": digest(project / "cadra-owned.txt")}
    definition = data["tasks"][0]["definition"]
    definition["ready_scope"] = dict(revision=1, scope=dict(mode="parallel", files=["cadra-owned.txt"], dirs=[]), inputs=inputs)
    definition["requirement"] = "Controlled unrelated task; only cadra-owned.txt. Not a real engineering dispatch."
    data["scheduler"] = guard.scheduler.initial()
    data = guard.scheduler.append_event(data, "group", now, members=["camera"],
             before={"camera": inputs}, before_refs={"camera": "controlled fixture baseline"})
    path = project / ".yuzio/cadra/runs/run-20261104-91.md"
    path.parent.mkdir(parents=True)
    guard.publish(path, raw_document(data), None, "controlled-cadra-fixture", 1, "create")
    return path


def create(destination, mode):
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    skill = destination / "skill"
    shutil.copytree(REPO / "cohestra", skill)
    release = json.loads((skill / "release.json").read_text())
    project = destination / "project"
    project.mkdir()
    write(project, ".gitignore", "/.yuzio/\n/.test/\n__pycache__/\n/reply-*.md\n")
    write(project, "cadra-owned.txt", "unrelated Cadra task input; preserve\n")
    write(project, "other-session.txt", "another session's material; preserve\n")
    write(project, "tools/probe.py", PROBE)
    write(project, "AGENTS.md", """# Local project rules

The task requirements identify business write scopes. Preserve other tasks.
Review may run scoped unit checks and inspect the validation probe, but this
environment authorizes access to the shared validator only during validate.
Final acceptance requires an actual successful invocation of:
`python3 -B tools/probe.py validate <alpha|beta>` from this project root.
The project-provided process lock is mandatory. A queued invocation is still
running, not a test failure; do not bypass it with a direct resource call.
Test controller owns .test resource release/stop controls and other-session.txt.
Do not modify tools/probe.py, these rules, Cadra records, or controller inputs.
No commits, pushes, installations, or access to real devices are authorized.
""")
    for task in ("alpha", "beta"):
        function = f'def normalize_{task}(name):\n    return name.strip() or "{task.title()} Untitled"\n'
        if mode == "overlap":
            if task == "alpha":
                write(project, "shared.py", function.replace("Alpha Untitled", "wrong-alpha"))
            else:
                with (project / "shared.py").open("a") as stream:
                    stream.write("\n" + function.replace("Beta Untitled", "wrong-beta"))
        else:
            write(project, task + ".py", function)
        module = "shared" if mode == "overlap" else task
        write(project, f"tests/test_{task}.py", f'''import unittest
from {module} import normalize_{task}

class NormalizationTests(unittest.TestCase):
    def test_name(self):
        self.assertEqual(normalize_{task}("  Mewoo  "), "Mewoo")
''')
        write(project, f"docs/{task}.md", f"# {task.title()}\n\nTrim surrounding whitespace; blank names produce `{task.title()} Untitled`.\n")
    cmd = ["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=Concurrency fixture", "-c", "user.email=fixture@example.invalid"]
    for args in (["init", "--quiet", "--initial-branch=main"], ["add", "."], ["commit", "--quiet", "-m", "controlled candidate"]):
        subprocess.run(cmd + args, cwd=project, check=True)
    baseline = subprocess.check_output(cmd + ["rev-parse", "HEAD"], cwd=project, text=True).strip()
    container = project / ".yuzio/cohestra"
    shutil.copytree(skill / "assets/project", container)
    text = ((container / "README.md").read_text()
            .replace("<实际项目名称>", "Closeout concurrency fixture")
            .replace("<实际发行版本；仅记录初始化来源，不锁定后续调用>", release["version"]))
    (container / "README.md").write_text(text)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    run = seed_cadra(project, now)
    metadata = dict(mode=mode, baseline=baseline, project=str(project), skill=str(skill),
                    cadra_run=str(run), cadra_sha256=digest(run),
                    preserved={name:digest(project/name) for name in ["other-session.txt", "cadra-owned.txt", "tools/probe.py", "AGENTS.md"]},
                    skill_hashes={str(p.relative_to(skill)):digest(p) for p in skill.rglob("*") if p.is_file()})
    write(destination, "metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    create(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "disjoint")

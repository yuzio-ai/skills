"""Check the live-test probes, without simulating an agent's stage decisions."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from . import closeout_concurrency_fixture as fixture
from .closeout_concurrency_fixture import create, observations, shared_resource_result


class ConcurrencyProbeTests(unittest.TestCase):
    def test_container_initialization_uses_frozen_skill(self):
        with tempfile.TemporaryDirectory(prefix="closeout-source-") as folder:
            suite = (Path(folder) / "suite").resolve()
            frozen = suite / "skill"
            copytree = fixture.shutil.copytree

            def copy_with_distinct_frozen_source(source, destination, *args, **kwargs):
                result = copytree(source, destination, *args, **kwargs)
                if Path(destination) == frozen:
                    manifest = frozen / "release.json"
                    release = json.loads(manifest.read_text())
                    release["version"] = "9.8.7"
                    manifest.write_text(json.dumps(release))
                    (frozen / "assets/project/source-marker.txt").write_text("frozen template\n")
                return result

            with patch.object(fixture.shutil, "copytree", side_effect=copy_with_distinct_frozen_source), contextlib.redirect_stdout(io.StringIO()):
                create(suite, "disjoint")

            container = suite / "project/.yuzio/cohestra"
            version = json.loads((frozen / "release.json").read_text())["version"]
            self.assertIn(f"初始化时 Skill 发行版本：{version}", (container / "README.md").read_text())
            self.assertEqual((container / "source-marker.txt").read_bytes(),
                             (frozen / "assets/project/source-marker.txt").read_bytes())

    def test_two_real_validation_processes_wait_then_use_one_resource(self):
        with tempfile.TemporaryDirectory(prefix="closeout-resource-") as folder:
            suite = Path(folder) / "suite"
            with contextlib.redirect_stdout(io.StringIO()):
                create(suite, "disjoint")
            project = suite / "project"
            processes = []

            def start(*arguments):
                process = subprocess.Popen([sys.executable, "-B", "tools/probe.py", *arguments],
                                           cwd=project, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True)
                processes.append(process)
                return process

            try:
                holder = start("hold-validator")
                self.assertEqual(json.loads(holder.stdout.readline())["kind"], "holder_acquired")
                alpha = start("validate", "alpha")
                beta = start("validate", "beta")
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    rows = observations(project)
                    if len([row for row in rows if row["kind"] == "validation_attempt"]) == 2:
                        break
                    time.sleep(0.02)
                self.assertEqual({row["task"] for row in rows if row["kind"] == "validation_attempt"}, {"alpha", "beta"})
                self.assertFalse(any(row["kind"] == "validation_acquired" for row in rows))
                self.assertFalse(shared_resource_result(project)["complete"])
                (project / ".test/release-validator").touch()
                for process in (holder, alpha, beta):
                    _, error = process.communicate(timeout=10)
                    self.assertEqual(process.returncode, 0, error)
                result = shared_resource_result(project)
                self.assertTrue(result["complete"], result)
                self.assertEqual(result["failures"], [])
                self.assertLessEqual(result["intervals"][0]["end_ns"], result["intervals"][1]["start_ns"])
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)
                    for stream in (process.stdout, process.stderr):
                        stream.close()

    def test_audit_rejects_overlapping_critical_sections(self):
        with tempfile.TemporaryDirectory(prefix="closeout-audit-") as folder:
            root = Path(folder)
            (root / ".test").mkdir()
            rows = [
                dict(kind="validation_attempt", task="alpha", pid=1, monotonic_ns=1),
                dict(kind="validation_attempt", task="beta", pid=2, monotonic_ns=2),
                dict(kind="holder_releasing", pid=0, monotonic_ns=10),
                dict(kind="validation_acquired", task="alpha", pid=1, monotonic_ns=11),
                dict(kind="validation_acquired", task="beta", pid=2, monotonic_ns=12),
                dict(kind="validation_passed", task="alpha", pid=1, monotonic_ns=13),
                dict(kind="validation_releasing", task="alpha", pid=1, monotonic_ns=14),
                dict(kind="validation_passed", task="beta", pid=2, monotonic_ns=15),
                dict(kind="validation_releasing", task="beta", pid=2, monotonic_ns=16),
            ]
            (root / ".test/events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = shared_resource_result(root)
            self.assertFalse(result["complete"])
            self.assertIn("overlapping validation critical sections", result["failures"])


if __name__ == "__main__":
    unittest.main()

"""Run isolated verification probes against the three cleanup scenarios.

These tests observe processes and files. Stage decisions and publication are
covered by the maintainer scenarios, not emulated here.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY = """
import json
import shutil
import sys
from pathlib import Path

mode, directory, source = sys.argv[1:]
root = Path(directory)
inputs = root / 'inputs'
inputs.mkdir()
fixture = root / 'fixture.app'
fixture.mkdir()
if mode == 'build-fails':
    candidate = Path(shutil.copy2(source, inputs))
    try:
        compile(candidate.read_text(), candidate.name, 'exec')
    except SyntaxError as error:
        (root / 'build.log').write_text(f'{error.filename}: {error.msg}\\n')
        sys.exit(7)
if mode == 'wrapper-leaves-derived-data':
    (root / 'DerivedDataCandidate-fixture').mkdir()
    inputs.rmdir()
    fixture.rmdir()
    print(json.dumps({'artifact_cleanup': {'removed': [str(inputs), str(fixture)], 'skipped': []}}))
else:
    print('fixture check passed')
"""


class SandboxCleanupScenarios(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cohestra-cleanup-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.project = root / "project"
        self.project.mkdir()
        self.task = self.project / ".yuzio/cohestra/handoffs/sample"
        self.task.mkdir(parents=True)
        self.scratch = root / "scratch"
        self.scratch.mkdir()
        self.cache = self.scratch / "DerivedData"
        self.cache.mkdir()
        self.candidate = self.project / "candidate.py"
        self.candidate.write_text("def unfinished(\n")

    def run_probe(self, mode, parent):
        sandbox = Path(tempfile.mkdtemp(prefix="verify-", dir=parent))
        result = subprocess.run([sys.executable, "-B", "-c", VERIFY, mode, str(sandbox),
                                 str(self.candidate)],
                                capture_output=True, text=True, timeout=5)
        return sandbox, result

    def test_failed_build_preserves_diagnostic_then_cleans_only_its_sandbox(self):
        sandbox, result = self.run_probe("build-fails", self.scratch)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertTrue((sandbox / "fixture.app").is_dir())
        original = (sandbox / "build.log").read_text()
        evidence = self.task / "build.log"
        evidence.write_text(f"Exit code: {result.returncode}\n{original}")
        saved = evidence.read_text()
        self.assertIn("candidate.py: ", saved)
        self.assertIn("Exit code: 7", saved)

        shutil.rmtree(sandbox)

        self.assertFalse(os.path.lexists(sandbox))
        self.assertEqual(evidence.read_text(), saved)
        self.assertTrue(self.cache.is_dir())
        self.assertEqual(self.candidate.read_text(), "def unfinished(\n")

    def test_successful_wrapper_with_empty_skips_still_leaves_run_owned_data(self):
        sandbox, result = self.run_probe("wrapper-leaves-derived-data", self.project)
        self.assertEqual(result.returncode, 0, result.stderr)
        cleanup = json.loads(result.stdout)["artifact_cleanup"]
        self.assertEqual(cleanup["skipped"], [])
        self.assertFalse(any(os.path.lexists(path) for path in cleanup["removed"]))
        derived_data = sandbox / "DerivedDataCandidate-fixture"
        self.assertTrue(derived_data.is_dir())
        self.assertNotIn(str(derived_data), cleanup["removed"])

        shutil.rmtree(sandbox)

        self.assertFalse(os.path.lexists(derived_data))
        self.assertTrue(self.cache.is_dir())

    def test_unavailable_process_observation_preserves_fixture_and_evidence(self):
        sandbox, result = self.run_probe("process-observation-unavailable", self.scratch)
        self.assertEqual(result.returncode, 0, result.stderr)
        observer = subprocess.run(
            [sys.executable, "-B", "-c", "raise SystemExit('process observation unavailable')"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(observer.returncode, 1)
        self.assertEqual(observer.stdout, "")
        evidence = self.task / "verification.log"
        evidence.write_text(result.stdout + observer.stderr)

        self.assertTrue((sandbox / "fixture.app").is_dir())
        self.assertEqual(evidence.read_text(), "fixture check passed\nprocess observation unavailable\n")


if __name__ == "__main__":
    unittest.main()

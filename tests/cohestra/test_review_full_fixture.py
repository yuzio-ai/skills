"""Exercise the actual publication faults used by the live review suite."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from .review_full_fixture import prepare_full


class FullReviewFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cohestra-full-review-")
        self.addCleanup(self.temp.cleanup)
        self.suite = prepare_full(Path(self.temp.name) / "suite")
        spec = importlib.util.spec_from_file_location("publication_driver", self.suite / "publication-driver.py")
        self.driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.driver)

    def proposal(self, case):
        root = self.suite / case
        index = root / ".yuzio/cohestra/handoffs/sample/README.md"
        draft = index.with_name("synthetic-proposal.md")
        draft.write_text(index.read_text() + "\nSynthetic publication probe.\n")
        return root, index, draft, hashlib.sha256(index.read_bytes()).hexdigest()

    def test_replace_failure_keeps_original_index(self):
        root, index, draft, base = self.proposal("publish-failure")
        original = index.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.driver.preflight(root, draft), 0)
            self.assertEqual(self.driver.publish(root, draft, base), 1)
        self.assertEqual(index.read_bytes(), original)
        log = json.loads(next((self.suite / "events").glob("*.json")).read_text())
        self.assertEqual(log["error"]["type"], "PermissionError")
        self.assertNotIn("replaced", log["events"])

    def test_conflict_preserves_competing_write(self):
        root, index, draft, base = self.proposal("publish-conflict")
        before = index.read_text()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.driver.publish(root, draft, base), 1)
        self.assertTrue(index.read_text().startswith(before))
        self.assertNotEqual(index.read_text(), draft.read_text())
        log = json.loads(next((self.suite / "events").glob("*.json")).read_text())
        self.assertNotIn("replaced", log["events"])
        self.assertIn("README changed", log["error"]["message"])

    def test_recovered_interface_can_publish_validated_bytes(self):
        root, index, draft, base = self.proposal("publish-failure")
        cases = json.loads((self.suite / "controller.json").read_text())
        cases[0].pop("fault")
        (self.suite / "controller.json").write_text(json.dumps(cases))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.driver.preflight(root, draft), 0)
            self.assertEqual(self.driver.publish(root, draft, base), 0)
        self.assertEqual(index.read_bytes(), draft.read_bytes())
        log = json.loads(next((self.suite / "events").glob("*.json")).read_text())
        self.assertEqual(log["events"], ["temp-written-and-read", "replaced", "readback"])


if __name__ == "__main__":
    unittest.main()

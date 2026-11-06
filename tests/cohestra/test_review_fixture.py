"""Verify live-review inputs, not language-model behavior or review conclusions."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

from cohestra.review_fixture import REPO, prepare


class StandaloneReviewFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cohestra-review-")
        self.addCleanup(self.temp.cleanup)
        self.suite = prepare(Path(self.temp.name) / "suite")

    def test_fixed_candidate_is_clean_and_contains_all_inputs(self):
        for case in ("default", "unavailable", "self-review"):
            with self.subTest(case=case):
                root = self.suite / case
                status = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)
                self.assertEqual(status, "")
                committed = subprocess.check_output(["git", "-C", str(root), "show", "HEAD:names.py"])
                self.assertEqual(committed, (root / "names.py").read_bytes())
                self.assertFalse((root / ".yuzio").exists())

    def test_fixture_exposes_a_real_requirement_violation(self):
        path = self.suite / "default/names.py"
        spec = importlib.util.spec_from_file_location("review_candidate", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.normalize_name("  Mewoo  "), "Mewoo")
        self.assertEqual(module.normalize_name(""), "Untitled")
        self.assertNotEqual(module.normalize_name("   "), "Untitled")

    def test_frozen_skill_is_complete_and_independent(self):
        source = REPO / "cohestra"
        files = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
        frozen = self.suite / "skill"
        self.assertEqual(files, {p.relative_to(frozen): p.read_bytes() for p in frozen.rglob("*") if p.is_file()})
        (frozen / "release.json").write_text("isolated mutation")
        self.assertEqual((source / "release.json").read_bytes(), files[Path("release.json")])

    def test_existing_suite_cannot_be_overwritten(self):
        marker = self.suite / "default/names.py"
        before = marker.read_bytes()
        with self.assertRaises(FileExistsError):
            prepare(self.suite)
        self.assertEqual(marker.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

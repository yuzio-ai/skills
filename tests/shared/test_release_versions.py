"""Exercise version enforcement on actual isolated Git histories."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from .release_checks import HistoryUnavailable, release_issues


class ReleaseVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-release-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.run_git("init", "--quiet", "--initial-branch=main")
        (self.root / "sample").mkdir()
        self.manifest("0.1.0", "1")
        (self.root / "sample/SKILL.md").write_text("original\n")
        self.commit()

    def run_git(self, *args):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=Release test",
             "-c", "user.email=release@example.invalid", *args],
            cwd=self.root, env=self.env, check=True, capture_output=True, text=True,
        )

    def commit(self):
        self.run_git("add", ".")
        self.run_git("commit", "--quiet", "-m", "fixture")

    def manifest(self, number, protocol):
        (self.root / "sample/release.json").write_text(json.dumps({
            "version": number, "protocol_version": protocol,
        }))

    def issues(self):
        return release_issues(self.root, "sample")

    def test_clean_package_and_repository_only_changes_do_not_require_bump(self):
        self.assertEqual(self.issues(), [])
        (self.root / "README.md").write_text("guide\n")
        self.commit()
        self.assertEqual(self.issues(), [])

    def test_uncommitted_and_committed_same_version_changes_fail(self):
        (self.root / "sample/SKILL.md").write_text("changed\n")
        self.assertIn("different package contents", "\n".join(self.issues()))
        self.commit()
        self.assertIn("different package contents", "\n".join(self.issues()))
        self.manifest("0.1.1", "1")
        self.assertEqual(self.issues(), [])
        self.commit()
        self.assertEqual(self.issues(), [])
        (self.root / "sample/SKILL.md").write_text("changed again\n")
        self.assertTrue(self.issues())

    def test_untracked_hidden_resource_and_deletion_require_bump(self):
        extra = self.root / "sample/.hidden-template"
        extra.write_text("new\n")
        self.assertTrue(self.issues())
        extra.unlink()
        (self.root / "sample/SKILL.md").unlink()
        self.assertTrue(self.issues())

    def test_metadata_only_edit_does_not_reset_original_version(self):
        path = self.root / "sample/release.json"
        data = json.loads(path.read_text())
        path.write_text(json.dumps(data, indent=2))
        self.commit()
        self.assertTrue(self.issues())

    def test_package_and_protocol_rollback_are_rejected(self):
        self.manifest("0.2.0", "2")
        self.commit()
        self.manifest("0.1.0", "1")
        failures = "\n".join(self.issues())
        self.assertIn("package version rollback", failures)
        self.assertIn("protocol version rollback", failures)
        self.manifest("0.3.0", "1")
        self.assertIn("protocol version rollback", "\n".join(self.issues()))

    def test_protocol_change_also_requires_package_bump(self):
        self.manifest("0.1.0", "2")
        self.assertTrue(self.issues())
        self.manifest("0.2.0", "2")
        self.assertEqual(self.issues(), [])

    def test_shallow_history_is_explicitly_unavailable(self):
        target = self.root / "shallow-copy"
        self.run_git("clone", "--quiet", "--depth=1", self.root.as_uri(), str(target))
        with self.assertRaises(HistoryUnavailable):
            release_issues(target, "sample")


if __name__ == "__main__":
    unittest.main()

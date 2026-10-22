"""Exercise storage rules with real Git; not an agent recovery simulation."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LocalStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="yuzio-storage-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "--quiet", "--initial-branch=main")

    def git(self, *args, check=True):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", *args],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=check,
        )

    def write(self, path, text="local record\n"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def install_root_rule(self):
        self.write(".gitignore", (ROOT / ".gitignore").read_text())

    def test_root_rule_ignores_all_skills_but_keeps_formal_docs_and_fixtures(self):
        self.install_root_rule()
        for skill in ("cohestra", "cadra", "vistra", "relatra"):
            path = f".yuzio/{skill}/records/nested/result.md"
            self.write(path)
            self.assertEqual(self.git("check-ignore", "--quiet", path, check=False).returncode, 0)
        for path in ("docs/design/decision.md", "tests/fixtures/project/.yuzio/cadra/tasks/a.md"):
            self.write(path)
            self.assertEqual(self.git("check-ignore", "--quiet", path, check=False).returncode, 1)
        self.git("add", ".")
        indexed = self.git("ls-files").stdout.splitlines()
        self.assertIn("docs/design/decision.md", indexed)
        self.assertIn("tests/fixtures/project/.yuzio/cadra/tasks/a.md", indexed)
        self.assertFalse(any(path.startswith(".yuzio/") for path in indexed))

    def test_container_templates_protect_new_records_without_root_rule(self):
        for skill in ("cohestra", "cadra"):
            self.write(f".yuzio/{skill}/.gitignore",
                       (ROOT / skill / "assets/project/.gitignore").read_text())
            self.write(f".yuzio/{skill}/README.md")
            self.write(f".yuzio/{skill}/records/one.md")
        self.git("add", ".")
        self.assertEqual(self.git("ls-files").stdout, "")

    def test_existing_tracked_records_remain_tracked(self):
        path = ".yuzio/cohestra/handoffs/a/README.md"
        self.write(path)
        self.git("add", path)
        self.install_root_rule()
        self.write(path, "updated record\n")
        self.assertIn(path, self.git("ls-files").stdout.splitlines())
        self.assertIn(path, self.git("diff", "--name-only").stdout.splitlines())

if __name__ == "__main__":
    unittest.main()

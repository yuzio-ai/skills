"""Cohestra package structure; actual stage acceptance remains separate."""

import json
import re
import unittest
from pathlib import Path

from shared.package_checks import SkillPackageChecks, frontmatter, keys


class CohestraPackagingTests(SkillPackageChecks, unittest.TestCase):
    package = Path(__file__).resolve().parents[2] / "cohestra"

    def test_routes_and_contract(self):
        skill = (self.package / "SKILL.md").read_text()
        for entry in ("init", "need", "design", "code", "review", "fix", "validate", "verify", "report"):
            with self.subTest(entry=entry):
                self.assertIn(f"references/{entry}.md", skill)
                self.assertTrue((self.package / f"references/{entry}.md").is_file())
        workflow = (self.package / "references/workflow.md").read_text()
        version = json.loads((self.package / "release.json").read_text())["protocol_version"]
        self.assertIn(f'contract: "{version}"', workflow)
        self.assertIn(f"cohestra v{version}", (self.package / "assets/handoff.md").read_text())
        block = re.search(r"```yaml\n(.*?)```", workflow, re.S)
        self.assertIsNotNone(block)
        self.assertEqual(keys(frontmatter(self.package / "assets/task-index.md")), keys(block[1]))


if __name__ == "__main__":
    unittest.main()

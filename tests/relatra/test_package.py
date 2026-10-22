"""Relatra package resources; script behavior is covered by test_relatra.py."""

import ast
import json
import unittest
from pathlib import Path

from shared.package_checks import SkillPackageChecks


class RelatraPackagingTests(SkillPackageChecks, unittest.TestCase):
    package = Path(__file__).resolve().parents[2] / "relatra"
    extra_resources = ("scripts/relatra.py", "agents/openai.yaml")

    def test_script_versions_match_release(self):
        release = json.loads((self.package / "release.json").read_text())
        tree = ast.parse((self.package / "scripts/relatra.py").read_text())
        constants = {
            target.id: ast.literal_eval(node.value)
            for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name) and target.id in {"VERSION", "SCHEMA"}
        }
        self.assertEqual(constants["VERSION"], release["version"])
        self.assertEqual(str(constants["SCHEMA"]), release["protocol_version"])


if __name__ == "__main__":
    unittest.main()

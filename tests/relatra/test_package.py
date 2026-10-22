"""Relatra package resources; script behavior is covered by test_relatra.py."""

import unittest
from pathlib import Path

from shared.package_checks import SkillPackageChecks


class RelatraPackagingTests(SkillPackageChecks, unittest.TestCase):
    package = Path(__file__).resolve().parents[2] / "relatra"
    extra_resources = ("scripts/relatra.py", "agents/openai.yaml")


if __name__ == "__main__":
    unittest.main()

"""Check maintained path contracts, excluding captured historical evidence."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ProjectDataPathTests(unittest.TestCase):
    def test_maintained_resources_use_shared_root(self):
        paths = [ROOT / "README.md", ROOT / "README.zh-CN.md"]
        for folder in ("cohestra", "cadra", "relatra", "vistra", "docs"):
            paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file())
        for fixtures in (ROOT / "tests").glob("*/fixtures"):
            paths.extend(p for p in fixtures.rglob("*") if p.is_file())
        obsolete = re.compile(r"\.(?:cohestra|cadra|relatra|vistra)(?=/|[\s`\"'])")
        for path in paths:
            if path.suffix not in {".md", ".py", ".json", ".yaml", ".yml", ".txt"}:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNone(obsolete.search(path.read_text(encoding="utf-8")))



if __name__ == "__main__":
    unittest.main()

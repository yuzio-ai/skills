"""Check maintained path contracts, excluding captured historical evidence."""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cadra_static", ROOT / "tests/cadra-static-checks.py"
)
checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checks)


class ProjectDataPathTests(unittest.TestCase):
    def test_maintained_resources_use_shared_root(self):
        paths = [ROOT / "README.md", ROOT / "README.zh-CN.md"]
        for folder in ("cohestra", "cadra", "relatra", "vistra", "docs", "tests/fixtures"):
            paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file())
        obsolete = re.compile(r"\.(?:cohestra|cadra|relatra|vistra)(?=/|[\s`\"'])")
        for path in paths:
            if path.suffix not in {".md", ".py", ".json", ".yaml", ".yml", ".txt"}:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNone(obsolete.search(path.read_text(encoding="utf-8")))

    def test_link_checker_resolves_url_path_and_detects_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "page one.html").write_text("<p>fixture</p>")
            doc = root / "report.md"
            doc.write_text("[preview](page%20one.html?layout=A#preview)\n")
            checks.FAILURES.clear()
            self.assertEqual(checks.check_links([str(doc)]), (1, 0))
            doc.write_text("[missing](missing.html?layout=A#preview)\n")
            self.assertEqual(checks.check_links([str(doc)]), (1, 1))
            self.assertEqual(len(checks.FAILURES), 1)
            checks.FAILURES.clear()


if __name__ == "__main__":
    unittest.main()

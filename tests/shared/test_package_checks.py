"""Shared checker regressions and repository documentation links."""

import re
import tempfile
import unittest
from pathlib import Path

from .package_checks import check_links, resource_graph


ROOT = Path(__file__).resolve().parents[2]


class PackageCheckTests(unittest.TestCase):
    def test_link_checker_resolves_url_path_and_detects_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "page one.html").write_text("<p>fixture</p>")
            doc = root / "report.md"
            doc.write_text("[preview](page%20one.html?layout=A#preview)\n")
            self.assertEqual(check_links([doc]), (1, []))
            doc.write_text("[missing](missing.html?layout=A#preview)\n")
            total, failures = check_links([doc])
            self.assertEqual(total, 1)
            self.assertEqual(len(failures), 1)
            # Calls do not retain failures from earlier checks.
            self.assertEqual(check_links([]), (0, []))

    def test_missing_dependency_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "SKILL.md").write_text("[mode](references/missing.md)\n")
            with self.assertRaisesRegex(ValueError, "Missing resource"):
                resource_graph(root)

    def test_repository_dependency_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = parent / "skill"
            root.mkdir()
            (parent / "only-in-repo.md").write_text("not installed")
            (root / "SKILL.md").write_text("[rules](../only-in-repo.md)\n")
            with self.assertRaisesRegex(ValueError, "escapes package"):
                resource_graph(root)

    def test_template_directories_include_hidden_files_and_allow_cycles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "assets").mkdir()
            (root / "SKILL.md").write_text("[template](assets/)\n")
            (root / "assets/.gitignore").write_text("*\n")
            (root / "assets/.gitkeep").touch()
            (root / "assets/README.md").write_text("[back](../SKILL.md)\n")
            self.assertEqual(resource_graph(root), {p.resolve() for p in root.rglob("*") if p.is_file()})

    def test_directory_symlink_cannot_escape_package(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = parent / "skill"
            root.mkdir()
            (root / "SKILL.md").write_text("[template](assets/)\n")
            (root / "assets").symlink_to(parent, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "escapes package"):
                resource_graph(root)

    def test_repository_documentation_links(self):
        files = [ROOT / "README.md", ROOT / "README.zh-CN.md"]
        files.extend((ROOT / "tests").rglob("*.md"))
        self.assertEqual(check_links(files)[1], [])

    def test_bilingual_readme_navigation_matches(self):
        english = (ROOT / "README.md").read_text()
        chinese = (ROOT / "README.zh-CN.md").read_text()
        self.assertIn("(README.zh-CN.md)", english)
        self.assertIn("(README.md)", chinese)
        def structure(text):
            links = re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)
            return (
                re.findall(r"^(#+) ", text, re.M),
                [line.count("|") for line in text.splitlines() if line.startswith("|")],
                re.findall(r"```[^\n]*\n(.*?)```", text, re.S),
                [link for link in links if link not in ("README.md", "README.zh-CN.md")],
            )
        self.assertEqual(structure(english), structure(chinese))


if __name__ == "__main__":
    unittest.main()

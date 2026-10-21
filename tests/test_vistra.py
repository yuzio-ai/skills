"""Offline packaging checks. These do not simulate agent behavior or image quality."""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "vistra"


def resource_graph(package):
    """Resolve local Markdown links from the entrypoint in a standalone install."""
    package = package.resolve()
    pending = [package / "SKILL.md"]
    visited = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        if not current.is_relative_to(package):
            raise ValueError(f"Resource escapes package: {current}")
        if not current.is_file():
            raise ValueError(f"Missing resource: {current}")
        visited.add(current)
        if current.suffix != ".md":
            continue
        content = current.read_text(encoding="utf-8")
        for link in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", content):
            parsed = urlsplit(link)
            if parsed.scheme or not parsed.path:
                continue
            pending.append((current.parent / unquote(parsed.path)).resolve())
    return visited


class VistraPackagingTests(unittest.TestCase):
    def test_standalone_install_resource_closure(self):
        # The install must work with only this skill, without sibling skills or Spec.
        with tempfile.TemporaryDirectory(prefix="vistra-install-") as temp:
            installed = (Path(temp) / "vistra").resolve()
            shutil.copytree(PACKAGE, installed)
            reachable = resource_graph(installed)
            actual = {p.resolve() for p in installed.rglob("*") if p.is_file()}
            self.assertEqual(actual, reachable, "Undiscoverable package resource")
            self.assertEqual(
                {p.relative_to(installed): p.read_bytes() for p in reachable},
                {p.relative_to(PACKAGE): p.read_bytes() for p in PACKAGE.rglob("*") if p.is_file()},
            )

    def test_missing_dependency_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "SKILL.md").write_text("[mode](references/missing.md)\n")
            with self.assertRaisesRegex(ValueError, "Missing resource"):
                resource_graph(root)

    def test_repository_dependency_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = parent / "vistra"
            root.mkdir()
            (parent / "only-in-repo.md").write_text("not installed")
            (root / "SKILL.md").write_text("[rules](../only-in-repo.md)\n")
            with self.assertRaisesRegex(ValueError, "escapes package"):
                resource_graph(root)

    def test_release_metadata(self):
        release = json.loads((PACKAGE / "release.json").read_text())
        self.assertRegex(release["version"], r"^\d+\.\d+\.\d+$")
        self.assertRegex(release["protocol_version"], r"^[1-9]\d*$")
        self.assertEqual(release["skill_path"], PACKAGE.name)
        self.assertEqual(release["repository"], "https://github.com/yuzio-ai/skills")

    def test_portable_package_contents(self):
        self.assertFalse((PACKAGE / "agents").exists())
        self.assertFalse((PACKAGE / "scripts").exists())
        self.assertFalse((PACKAGE / ".yuzio").exists())
        for path in PACKAGE.rglob("*"):
            if not path.is_file():
                continue
            with self.subTest(path=path.relative_to(PACKAGE)):
                self.assertFalse(path.is_symlink())
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"/(?:Users|home)/[^\s/]+/")
                self.assertNotRegex(text, r"\bsk-[A-Za-z0-9]{20,}\b")
                self.assertTrue(text.endswith("\n"))
                self.assertTrue(all(line == line.rstrip() for line in text.splitlines()))

    def test_taste_provenance_is_pinned(self):
        for reference in (PACKAGE / "references").rglob("*.md"):
            content = reference.read_text()
            for paragraph in content.split("\n\n"):
                urls = re.findall(r"https://github.com/Leonxlnx/taste-skill/blob/([^/)]+)/([^\s)]+)", paragraph)
                for commit, source in urls:
                    with self.subTest(reference=reference.name, source=source):
                        self.assertRegex(commit, r"^[0-9a-f]{40}$")
                        self.assertTrue(source.startswith("skills/"))
                        self.assertTrue(source.endswith("/SKILL.md"))
                        self.assertRegex(paragraph, r"SHA-256 `[0-9a-f]{64}`")
            if reference.parent.name == "domains":
                self.assertIn("https://github.com/Leonxlnx/taste-skill/blob/", content)
        license_text = (PACKAGE / "LICENSE").read_text()
        self.assertIn("Copyright (c) 2026 YUZIO", license_text)
        self.assertIn("Copyright (c) 2026 Leonxlnx", license_text)


if __name__ == "__main__":
    unittest.main()

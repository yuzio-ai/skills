"""Offline packaging checks. These do not simulate agent behavior or image quality."""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
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


def validate_provenance(package):
    """Check pinned sources and bidirectional mappings, not wording or visual quality."""
    path = package / "references/provenance.md"
    sections = re.split(r"^## ", path.read_text(), flags=re.MULTILINE)[1:]
    mapped = set()
    for section in sections:
        anchor, body = section.split("\n", 1)
        targets = re.findall(r"\[[^\]]+\]\(((?:domains|modes)/[^)]+\.md)\)", body)
        if len(targets) != 1 or targets[0] in mapped:
            raise ValueError("Missing or duplicate rule mapping")
        mapped.add(targets[0])
        target = path.parent / targets[0]
        if not target.is_file() or f"../provenance.md#{anchor}" not in target.read_text():
            raise ValueError("Missing rule file or source backlink")
        sources = 0
        for paragraph in body.split("\n\n"):
            urls = re.findall(r"https://github.com/Leonxlnx/taste-skill/blob/([^/)]+)/([^\s)]+)", paragraph)
            for commit, source in urls:
                if not re.fullmatch(r"[0-9a-f]{40}", commit):
                    raise ValueError("Unpinned source")
                if not source.startswith("skills/") or not source.endswith("/SKILL.md"):
                    raise ValueError("Invalid source path")
                if not re.search(r"SHA-256 `[0-9a-f]{64}`", paragraph):
                    raise ValueError("Missing source hash")
                sources += 1
        if not sources or not re.search(r"202\d-\d{2}-\d{2}", body):
            raise ValueError("Missing source or read date")
    expected = {str(p.relative_to(path.parent)) for p in (path.parent / "domains").glob("*.md")}
    expected.update({"modes/review.md", "modes/handoff.md"})
    if mapped != expected:
        raise ValueError("Incomplete rule coverage")


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
        validate_provenance(PACKAGE)
        license_text = (PACKAGE / "LICENSE").read_text()
        self.assertIn("Copyright (c) 2026 YUZIO", license_text)
        self.assertIn("Copyright (c) 2026 Leonxlnx", license_text)

    def test_provenance_rejects_broken_sources_and_mappings(self):
        mutations = [
            (lambda s: s.replace("f624f37a8c650b9cc550253104925efe4c8de246", "main"), "Unpinned"),
            (lambda s: re.sub(r"SHA-256 `[0-9a-f]{64}`", "", s, count=1), "Missing source hash"),
            (lambda s: s.replace("(domains/mobile.md)", "(domains/missing.md)"), "Missing rule"),
            (lambda s: re.sub(r"## mobile\n.*?(?=## desktop)", "", s, flags=re.DOTALL), "Incomplete rule"),
        ]
        for mutate, error in mutations:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temp:
                package = Path(temp) / "vistra"
                shutil.copytree(PACKAGE, package)
                source = package / "references/provenance.md"
                source.write_text(mutate(source.read_text()))
                with self.assertRaisesRegex(ValueError, error):
                    validate_provenance(package)


if __name__ == "__main__":
    unittest.main()

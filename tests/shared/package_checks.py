"""Repository-only checks shared by independently installable skill packages."""

import json
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .release_checks import HistoryUnavailable, release_issues


def local_links(path):
    """Yield inline Markdown file targets; fragments are not checked."""
    content = Path(path).read_text(encoding="utf-8")
    # Code examples are not resource declarations.
    content = re.sub(r"^```.*?^```[^\n]*", "", content, flags=re.M | re.S)
    for link in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", content):
        parsed = urlsplit(link)
        if not parsed.scheme and parsed.path:
            yield unquote(parsed.path)


def check_links(files):
    total, failures = 0, []
    for path in map(Path, files):
        for target in local_links(path):
            total += 1
            if not (path.parent / target).exists():
                failures.append(f"{path}: missing {target}")
    return total, failures


def frontmatter(path):
    """Read the package's simple YAML header without a runtime YAML dependency."""
    text = Path(path).read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        raise ValueError(f"{path}: missing Front Matter")
    return match[1]


def keys(block):
    return set(re.findall(r"^([a-z_]+):", block, re.M))


def resource_graph(package, entrypoints=("SKILL.md",)):
    """Follow links and template directories without leaving the installed package."""
    package = Path(package).resolve()
    pending = [package / entry for entry in entrypoints]
    visited = set()
    while pending:
        current = pending.pop().resolve()
        if current in visited:
            continue
        if not current.is_relative_to(package):
            raise ValueError(f"Resource escapes package: {current}")
        if not current.exists():
            raise ValueError(f"Missing resource: {current}")
        visited.add(current)
        if current.is_dir():
            pending.extend(current.iterdir())
        elif current.suffix == ".md":
            pending.extend(current.parent / link for link in local_links(current))
    return {path for path in visited if path.is_file()}


class SkillPackageChecks:
    """Mixin: inherited tests run once in each skill's own test suite."""

    extra_resources = ()

    def test_package_version_history(self):
        try:
            issues = release_issues(self.package.parent, self.package.name)
        except HistoryUnavailable as error:
            self.skipTest(str(error))
        self.assertEqual(issues, [], "\n".join(issues))

    def test_package_metadata(self):
        release = json.loads((self.package / "release.json").read_text())
        self.assertRegex(release["version"], r"^\d+\.\d+\.\d+$")
        self.assertRegex(release["protocol_version"], r"^\d+(?:\.\d+)*$")
        self.assertEqual(release["skill_path"], self.package.name)
        self.assertEqual(release["repository"], "https://github.com/yuzio-ai/skills")
        header = frontmatter(self.package / "SKILL.md")
        for field in ("name", "description"):
            self.assertRegex(header, rf"(?m)^{field}:\s*\S[^\n]*$")
        name = re.search(r"(?m)^name:\s*([^\n]+)$", header)[1]
        self.assertEqual(name.strip().strip("\"'"), self.package.name)
        self.assertTrue((self.package / "LICENSE").read_text().strip())

    def test_standalone_package_resources(self):
        # Host-discovered metadata and non-link script references are explicit roots.
        entries = ("SKILL.md", "release.json", "LICENSE") + self.extra_resources
        for path in self.package.rglob("*"):
            self.assertFalse(path.is_symlink(), f"Package symlink: {path}")
        with tempfile.TemporaryDirectory(prefix=f"{self.package.name}-package-") as folder:
            installed = Path(folder) / self.package.name
            shutil.copytree(self.package, installed)
            reachable = resource_graph(installed, entries)
            actual = {p.resolve() for p in installed.rglob("*") if p.is_file()}
            self.assertEqual(actual, reachable, "Undiscoverable package resource")
            self.assertEqual(check_links(installed.rglob("*.md"))[1], [])
            self.assertEqual(
                {p.relative_to(installed): p.read_bytes() for p in installed.rglob("*") if p.is_file()},
                {p.relative_to(self.package): p.read_bytes() for p in self.package.rglob("*") if p.is_file()},
            )

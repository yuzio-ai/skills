"""Check release identity against Git history without adding installed dependencies."""

import json
import re
import subprocess
from pathlib import Path


class HistoryUnavailable(RuntimeError):
    pass


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE,
    ).strip()


def version(value, pattern):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError(f"Invalid version: {value!r}")
    return tuple(map(int, value.split(".")))


def release_issues(root, skill):
    root = Path(root).resolve()
    try:
        if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
            raise HistoryUnavailable("Package repository root does not match")
        if git(root, "rev-parse", "--is-shallow-repository") == "true":
            raise HistoryUnavailable("Full Git history required for release checks")
        git(root, "rev-parse", "HEAD")
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise HistoryUnavailable("Git history unavailable for release checks") from error

    manifest = f"{skill}/release.json"
    current = json.loads((root / manifest).read_text())
    number = version(current["version"], r"\d+\.\d+\.\d+")
    protocol = version(current["protocol_version"], r"\d+(?:\.\d+)*")
    history = []
    for commit in git(root, "log", "--first-parent", "--format=%H", "HEAD", "--", manifest).splitlines():
        # A deletion commit has no manifest. Earlier versions still reserve their numbers.
        if not git(root, "ls-tree", commit, "--", manifest):
            continue
        release = json.loads(git(root, "show", f"{commit}:{manifest}"))
        history.append((commit, release))
    if not history:
        return []  # First publication of a new skill.

    issues = []
    highest = max(version(r["version"], r"\d+\.\d+\.\d+") for _, r in history)
    if number < highest:
        issues.append(f"{skill}: package version rollback or reuse: {current['version']}")
    previous_protocol = version(history[0][1]["protocol_version"], r"\d+(?:\.\d+)*")
    if protocol < previous_protocol:
        issues.append(f"{skill}: protocol version rollback: {current['protocol_version']}")

    matches = [commit for commit, r in history if r["version"] == current["version"]]
    if matches:
        original = matches[-1]
        changed = git(root, "diff", "--no-ext-diff", "--name-only", original, "--", skill)
        added = git(root, "ls-files", "--others", "--exclude-standard", "--", skill)
        if changed or added:
            issues.append(
                f"{skill}: version {current['version']} has different package contents "
                f"from {original[:7]}; bump release.json.version\n{changed}\n{added}".rstrip()
            )
    return issues

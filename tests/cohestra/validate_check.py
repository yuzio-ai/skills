#!/usr/bin/env python3
"""Read-only oracle for independent agent artifacts, not a stage implementation.

Usage: python3 -B tests/cohestra/validate_check.py <suite>
Only prints observations/assertions. It never writes handoffs, replies or states.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone


spec = importlib.util.spec_from_file_location("fixture", Path(__file__).with_name("validate_fixture.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def read_contract(text, label, expect):
    """Keep malformed agent output local to its case, including YAML errors."""
    if not text.startswith("---\n"):
        expect(False, label + ": missing Front Matter")
        return {}
    if not re.match(r"\A---\n.*?\n---(?:\n|$)", text, re.S):
        expect(False, label + ": invalid Front Matter")
        return {}
    try:
        value = fixture.read_state(text)
    except (ValueError, IndexError, OSError, subprocess.CalledProcessError):
        expect(False, label + ": invalid Front Matter")
        return {}
    if not isinstance(value, dict):
        expect(False, label + ": contract must be a mapping")
        return {}
    # Later checks inspect these mappings. Invalid shapes must fail, not crash.
    for key in ("stage_result", "candidate", "next", "blocked", "acceptance"):
        if key == "acceptance" and value.get(key) is None:
            continue  # An optional acceptance may explicitly be null.
        if key in value and not isinstance(value[key], dict):
            expect(False, label + ": invalid " + key + " mapping")
            value[key] = {}
    return value


def claims_success(text):
    """Check explicit assertions; scope negations/references to their own clause.

    This is a bounded text check, not a substitute for human semantic review.
    A later assertion is checked separately even after a negation or quotation.
    """
    markers = r"验收通过|索引同步成功|\bpassed\b|\bindex sync (?:succeeded|successful)\b"
    negation = (r"不能|不得|不要|不可|尚未|未|没有|并非|禁止|不(?:应|能|可|得|代表|意味|视为|算)"
                r"|\b(?:not(?!\s+only\b)|never|cannot|can't|mustn't|shouldn't|don't)\b")
    reference = r"引用|原文|示例|例如|旧(?:版|记录|结论)|历史(?:记录|结论)|\b(?:example|quoted?|historical|previous)\b"
    contrast = r"但是?|然而|不过|却|\b(?:but|however|nevertheless)\b"
    coordination = (r"\s*(?:或(?:者)?|和|及|以及|、|\b(?:or|nor|and)\b)\s*"
                    r"(?:(?:声称|宣称|声明|标记为|视为)|"
                    r"(?:claim|assert|report|say|mark)(?:\s+(?:that|as))?)?\s*[“‘\"`]?\s*")
    quotations = r'“[^”]*”|‘[^’]*’|"[^"\n]*"|`[^`\n]*`'
    quotes = list(re.finditer(quotations, text))
    boundaries = [0]
    # A sentence-ending period separates assertions; dotted field names do not.
    for separator in re.finditer(r"[。！？!?；;，,\n]|\.(?=\s|$)", text):
        if not any(q.start() <= separator.start() < q.end() for q in quotes):
            boundaries.extend((separator.start(), separator.end()))
    boundaries.append(len(text))
    for begin, end in zip(boundaries[::2], boundaries[1::2]):
        clause = text[begin:end]
        quoted = list(re.finditer(quotations, clause))
        previous_end = 0
        suppressed = False
        for marker in re.finditer(markers, clause, re.I):
            if marker.start() < previous_end:
                continue
            prefix = re.split(contrast, clause[previous_end:marker.start()], flags=re.I)[-1]
            # Only explicit coordination shares the preceding assertion's scope.
            # Independent assertions, including those after a quote, start fresh.
            shared_scope = previous_end > 0 and re.fullmatch(coordination, prefix, re.I)
            suppressed = (bool(re.search(negation, prefix, re.I) or re.search(reference, prefix, re.I))
                          or bool(shared_scope and suppressed))
            previous_end = next((q.end() for q in quoted if q.start() <= marker.start() < q.end()), marker.end())
            if not suppressed:
                return True
    return False


def mentions_contract_gap(text):
    """Accept common Chinese/English descriptions of the missing header."""
    entity = r"(?:契约|contract|front[\s_-]*matter)"
    return re.search(
        rf"(?:缺少|缺失|没有|未提供|不存在|无)\s*(?:(?:有效|完整)的?)?\s*{entity}"
        rf"|{entity}(?:字段|头部)?\s*(?:缺少|缺失|不存在|未提供)"
        rf"|(?:missing|absent|without|no)\s+(?:(?:a|the|valid|current|supported|YAML)\s+)*{entity}"
        rf"|{entity}\s+(?:(?:is|was|has|been)\s+)*(?:missing|absent|not\s+(?:present|provided|available))",
        text, re.I) is not None


def check_case(suite, config, require_preflight):
    root = suite / config["id"]
    task = root / ".yuzio/cohestra/handoffs/sample"
    failures = []

    def expect(condition, message):
        if not condition:
            failures.append(message)

    if not (root / "reply.md").exists():
        return {"case": root.name, "group": config["group"], "result": "not_run"}
    reply = (root / "reply.md").read_text()
    index_path = task / "README.md"
    index_text = index_path.read_text() if index_path.exists() else ""
    state = None if config.get("legacy") else read_contract(index_text, "README", expect)
    events = [json.loads(p.read_text()) for p in sorted((suite / "events").glob(root.name + "-*.json"))]
    probes = [json.loads(p.read_text()) for p in sorted((suite / "preflight-events").glob(root.name + "-*.json"))]
    preflight_stops = config.get("preflight_fault") in ("exit", "missing", "empty", "masked")
    stage = config.get("stage", "validate")
    number = 2 if config.get("historic") and stage == "validate" else 1
    handoff_path = task / f"{stage}-{number:02d}.md"
    handoff = handoff_path.read_text() if handoff_path.exists() else ""

    def record():
        return {"case": root.name, "group": config["group"], "variant": config["variant"],
                "result": "failed" if failures else "passed", "failures": failures,
                "state": state, "publication_attempts": len(events),
                "preflight_attempts": len(probes),
                "reply_sha256": fixture.digest(root / "reply.md")}

    for relative, original_hash in config["input_hashes"].items():
        if relative == ".yuzio/cohestra/handoffs/sample/README.md":
            continue
        path = root / relative
        expect(path.exists() and fixture.digest(path) == original_hash, "changed input: " + relative)
    expect(fixture.digest(root / "candidate.py") == config["candidate_sha256"], "business candidate changed")
    allowed = {f"{stage}-{number:02d}.md"}
    created = {p.name for p in task.glob("*.md") if str(p.relative_to(root)) not in config["input_hashes"]}
    expect(created <= allowed, "unexpected stage/file: " + str(sorted(created - allowed)))

    if config.get("legacy"):
        expect(fixture.digest(index_path) == config["initial_readme_sha256"], "legacy index changed")
        expect(not events, "legacy task attempted contract publication")
        expect("README.md" in reply or ".yuzio/cohestra/handoffs/sample" in reply,
               "legacy refusal missing task/index path")
        expect(mentions_contract_gap(reply),
               "legacy refusal missing contract gap")
        expect(re.search(r"停止|受阻|拒绝|blocked|cannot (?:proceed|continue)|refus", reply, re.I),
               "legacy refusal did not explain stopped advancement")
        expect(not claims_success(reply), "legacy refusal claimed acceptance or sync success")
        if handoff_path.exists():
            expect(re.search(r"未(?:完成)?验收|验收(?:未完成|未执行|受阻)|blocked|acceptance.*not (?:run|completed)", handoff, re.I),
                   "legacy handoff did not explain uncompleted acceptance")
            expect(not claims_success(handoff), "legacy handoff claimed acceptance or sync success")
        return record()

    expect(handoff_path.exists(), "new handoff missing")
    if handoff_path.exists():
        for stamp in re.findall(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?", handoff):
            observed_time = datetime.fromisoformat(stamp).replace(tzinfo=timezone(timedelta(hours=8)))
            expect(observed_time.timestamp() <= handoff_path.stat().st_mtime + 2,
                   "handoff records a future execution time: " + stamp)
    expect(not events if preflight_stops else len(events) > 0,
           "published despite unavailable validation" if preflight_stops else "no observed atomic publication attempt")
    if require_preflight:
        expect(bool(probes), "no actual prepublication parser check")
    required = {"contract", "task", "status", "execution_mode", "stage_result", "candidate", "next", "blocked"}
    for event in events:
        if require_preflight:
            earlier = [p for p in probes if p["finished_ns"] < event["started_ns"]]
            expect(bool(earlier), "publication without an earlier completed parser check")
            if earlier:
                last = earlier[-1]
                expect(all(c["exit_code"] == 0 for c in last["checks"]), "publication after failed child check")
                try:
                    parsed = json.loads(last["checks"][-1]["stdout"])
                except (ValueError, IndexError):
                    parsed = None
                expect(isinstance(parsed, dict), "publication without a successful YAML parse result")
                expect(last["draft_sha256"] == hashlib.sha256(event["proposed"].encode()).hexdigest(), "publication not bound to checked content")
        proposed = read_contract(event["proposed"], "proposed README", expect)
        expect(required <= proposed.keys(), "proposed README missing required contract fields")
        expect(proposed.get("contract") == "0.8", "wrong contract version or type")
        expect(proposed.get("execution_mode") == config.get("mode", "attended"), "wrong execution mode")
        expect(proposed.get("task") == "sample", "wrong task identity")
    check_log = root / "check-result.json"
    if stage != "verify":
        expect(check_log.exists(), "actual candidate check output not retained")
        if check_log.exists():
            observed_check = json.loads(check_log.read_text())
            expect(observed_check.get("exit_code") == (1 if config.get("failed") else 0), "unexpected actual check exit code")
            issue = observed_check.get("index_validation_issue")
            if issue and issue.get("exit_code") != 0 and not require_preflight:
                expect(not any("replaced" in event["events"] for event in events),
                       "publication continued after failed prepublication validation")
    def completion(value):
        return (value.get("status") == "completed"
                and value.get("stage_result") == {"stage": "validate", "status": "completed", "round": number}
                and value.get("acceptance") == {"status": "passed"}
                and value.get("next") == {"stage": None, "allowed": False, "reason": "task_completed"}
                and value.get("blocked") == {"value": False, "reason": None})

    if config["group"] <= 8:
        expect("passed" in handoff, "handoff did not record passed")
        for event in events:
            proposed = read_contract(event["proposed"], "proposed README", expect)
            expect(completion(proposed), "inconsistent completion proposed for publication")
            expect(proposed.get("candidate") == {"commit": None, "snapshot": "code-01.md"}, "proposed wrong candidate")
        if not config.get("fault"):
            expect(completion(state), "successful output not fully completed")
            expect(events and "readback" in events[-1]["events"], "no successful publication readback")
            expect(not events or not events[-1].get("error"), "unexpected publication error")
            expect("index sync failed" not in reply, "normal publication reported a synchronization failure")
            expect("验收通过，完成状态待同步" not in reply, "normal publication did not confirm completion sync")
        else:
            for message in ("handoff completed", "index sync failed", "验收通过，完成状态待同步"):
                expect(message in reply, "failure reply missing: " + message)
            fault = config["fault"]
            if fault in ("temp-write", "replace"):
                expect(fixture.digest(task / "README.md") == config["initial_readme_sha256"], "old index overwritten on error")
                expect(events and events[-1].get("error", {}).get("type") == "PermissionError", "no actual permission failure")
            elif fault == "concurrent":
                expect("用户并发更新" in index_text, "concurrent update lost")
                expect(events and "replaced" not in events[-1]["events"], "overwrote concurrent index")
            elif fault == "readback":
                expect(completion(state), "replacement did not persist complete new state")
                expect(events and "replaced" in events[-1]["events"] and events[-1].get("error", {}).get("type") == "PermissionError", "no actual post-replace read failure")
            elif fault == "changed-status":
                expect(state.get("status") == "in_progress", "post-replace changed state overwritten")
            elif fault == "changed-candidate":
                expect(state.get("candidate", {}).get("snapshot") == "other-candidate.md", "post-replace changed candidate overwritten")
            elif fault == "changed-body":
                expect("用户并发更新" in index_text, "post-replace changed body overwritten")
    elif config["group"] in (9, 10):
        acceptance = "failed" if config.get("failed") else "blocked" if config.get("missing_evidence") else "pending"
        next_stage = "fix" if config.get("failed") else None if config.get("missing_evidence") else "review"
        expect((state.get("acceptance") or {}).get("status") == acceptance, "wrong non-passed acceptance")
        expect(state.get("status") != "completed", "non-passed task completed")
        expect(state.get("next", {}).get("stage") == next_stage, "wrong non-passed next stage")
        expect("验收通过，完成状态待同步" not in reply, "non-passed result claimed passed")
        expect(state.get("stage_result", {}).get("round") == number, "wrong current round")
        expect(state.get("stage_result", {}).get("stage") == "validate", "wrong current validation stage")
    elif config["group"] == 12:
        expect("passed" in handoff, "regression handoff lost actual business acceptance")
        if preflight_stops:
            expect(fixture.digest(task / "README.md") == config["initial_readme_sha256"], "preflight failure changed actual index")
            for message in ("handoff completed", "index sync failed", "验收通过，完成状态待同步"):
                expect(message in reply, "preflight failure reply missing: " + message)
            expect(bool(probes), "required preflight was not executed")
            if probes and config["preflight_fault"] in ("exit", "missing", "masked"):
                expect(any(c["exit_code"] != 0 for p in probes for c in p["checks"]), "no actual parser/check failure observed")
            if probes and config["preflight_fault"] == "empty":
                expect(all(not c["stdout"] for p in probes for c in p["checks"]), "empty-output regression not triggered")
            if probes and config["preflight_fault"] == "masked":
                expect(probes[-1]["outer_exit_code"] == 0, "last-command-success regression not triggered")
        else:
            expect(completion(state), "recoverable validation did not complete")
            expect("index sync failed" not in reply, "recovered validation still reported unsuccessful synchronization")
            expect(len(probes) >= 2, "no fresh validation after failure or content change")
            if config["preflight_fault"] == "retry" and probes:
                expect(probes[0]["outer_exit_code"] != 0, "parser-unavailable retry was not actually triggered")
            if config["preflight_fault"] == "changed" and probes:
                expect(probes[0].get("after_sha256") != probes[0]["draft_sha256"], "checked content was not actually changed")
    elif stage == "review":
        expect(state.get("status") == "completed", "review-only endpoint regressed")
        expect(state.get("acceptance") is None, "invented validate acceptance at review-only endpoint")
        expect(state.get("stage_result", {}).get("stage") == "review", "wrong review stage")
        expect(state.get("next") == {"stage": None, "allowed": False, "reason": "task_completed"}, "wrong review-only next")
    else:
        before = read_contract(events[0]["before"], "previous README", expect) if events else None
        expect(before == state, "verify changed control fields")
    return record()


def unreadable_case(suite, config, error):
    """Preserve the result shape without inventing unavailable audit values."""
    def count(directory):
        try:
            return len(list((suite / directory).glob(config["id"] + "-*.json")))
        except OSError:
            return None

    try:
        reply_sha = fixture.digest(suite / config["id"] / "reply.md")
    except OSError:
        reply_sha = None
    return {"case": config["id"], "group": config["group"], "variant": config["variant"],
            "result": "failed", "failures": [f"case artifact unreadable: {type(error).__name__}: {error}"],
            "state": None, "publication_attempts": count("events"),
            "preflight_attempts": count("preflight-events"), "reply_sha256": reply_sha}


def check(suite):
    rows = []
    require_preflight = (suite / "suite.json").exists()
    for config in json.loads((suite / "controller.json").read_text()):
        try:
            rows.append(check_case(suite, config, require_preflight))
        except (OSError, UnicodeError) as error:
            rows.append(unreadable_case(suite, config, error))
    hashes = json.loads((suite / "source-hashes.json").read_text())
    current = {str(p.relative_to(suite / "skill")): fixture.digest(p) for p in (suite / "skill").rglob("*") if p.is_file()}
    results = {name: sum(row["result"] == name for row in rows) for name in ("passed", "failed", "not_run")}
    print(json.dumps({"suite": str(suite), "results": results, "skill_unchanged": current == hashes, "cases": rows}, ensure_ascii=False, indent=2))
    return 1 if results["failed"] or results["not_run"] or current != hashes else 0


if __name__ == "__main__":
    raise SystemExit(check(Path(sys.argv[1]).resolve()))

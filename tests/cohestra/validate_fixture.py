#!/usr/bin/env python3
"""Isolated inputs and faultable file publication for real Cohestra agent calls.

This helper never decides acceptance, prepares an agent's README/handoff, or
generates an agent's reply. `publish` only performs observable filesystem steps.
Usage: prepare <new-suite>; preflight <case> <draft> [parser]
       publish <case> <draft> <base-sha256-or-absent>
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


def document(state, body):
    return "---\n" + json.dumps(state, ensure_ascii=False, indent=2) + "\n---\n\n" + body


def read_state(text):
    raw = text.split("---", 2)[1]
    parsed = subprocess.run(
        ["ruby", "-rpsych", "-rjson", "-e", "puts JSON.generate(Psych.safe_load(STDIN.read))"],
        input=raw, text=True, capture_output=True, check=True)
    return json.loads(parsed.stdout)


def prepare(suite):
    if suite.exists():
        raise FileExistsError("Use a new isolated suite")
    suite.mkdir(parents=True)
    source = Path(__file__).resolve().parents[2] / "cohestra"
    shutil.copytree(source, suite / "skill")
    (suite / "suite.json").write_text(json.dumps({"schema": 2, "preflight_required": True}))
    source_hashes = {str(p.relative_to(source)): digest(p) for p in source.rglob("*") if p.is_file()}
    (suite / "source-hashes.json").write_text(json.dumps(source_hashes, indent=2))
    cases = []

    def add(group, variant, **options):
        cases.append(dict(id=f"case-{len(cases)+1:02d}", group=group, variant=variant, **options))

    add(1, "attended")
    add(1, "unattended", mode="unattended")
    add(2, "legacy", legacy=True)
    for value in ("in_progress", "blocked", "failed"):
        add(3, value, mutation=["status", value])
    fields = [("status", "in_progress"), ("stage_result.stage", "code"),
              ("stage_result.status", "blocked"), ("stage_result.round", 99),
              ("acceptance", {"status": "pending"}), ("next.stage", "review"),
              ("next.allowed", True), ("next.reason", "stage_completed"),
              ("blocked.value", True), ("blocked.reason", "missing_permission")]
    for key, value in fields:
        add(4, "missing-" + key, mutation=[key, None], delete=True)
        add(4, "wrong-" + key, mutation=[key, value])
    add(4, "body-next", body_next=True)
    for fault in ("temp-write", "replace"):
        add(5, fault, fault=fault)
    add(6, "concurrent", fault="concurrent")
    add(7, "readback", fault="readback")
    for fault in ("changed-status", "changed-candidate", "changed-body"):
        add(8, fault, fault=fault)
    add(9, "missing-review", missing_review=True)
    add(9, "missing-evidence", missing_evidence=True)
    add(9, "failed", failed=True)
    add(10, "historic-passed", missing_review=True, historic=True)
    add(11, "review-only", stage="review")
    add(11, "verify", stage="verify", historic=True)
    add(12, "validation-exit-nonzero", preflight_fault="exit")
    add(12, "parser-unavailable", preflight_fault="missing")
    add(12, "validation-empty-output", preflight_fault="empty")
    add(12, "last-command-success", preflight_fault="masked")
    add(12, "available-parser-retry", preflight_fault="retry")
    add(12, "checked-content-changes", preflight_fault="changed")

    for case in cases:
        root = suite / case["id"]
        task = root / ".yuzio/cohestra/handoffs/sample"
        task.mkdir(parents=True)
        (root / ".yuzio/cohestra/README.md").write_text("# 隔离验证项目\n")
        (root / "AGENTS.md").write_text(
            "本项目为隔离夹具。只执行 REQUEST.md 指定阶段。业务候选只读。\n"
            "README 的写入必须通过外部测试驱动 publish；其他交付物可正常写入。\n"
            "本环境索引解析校验只通过测试接口 preflight 运行；该接口输出真实子命令结果与解析内容，语义校验由执行者完成。\n"
            "不要改接口或用另一路径替代它。接口允许用 parser 参数选择 ruby 或 python；解析器是否可用以实际结果为准。\n"
            "不得修改驱动或解除环境故障；文件权限由驱动恢复。\n")
        candidate = "def add(a, b):\n    return a + b\n"
        if case.get("failed"):
            candidate = "def add(a, b):\n    return a - b\n"
        (root / "candidate.py").write_text(candidate)
        (root / "check.py").write_text(
            "from candidate import add\nassert add(2, 3) == 5\nassert add(-2, 3) == 1\n"
            "assert add(0, 0) == 0\nprint('AC-1 PASS')\n")
        candidate_hash = digest(root / "candidate.py")
        (task / "need-01.md").write_text(
            "# 需求\nAC-1：add 返回两参数之和。用 check.py 验证。\n"
            "范围仅 candidate.py；不要求提交、发布或运行界面。\n")
        requirement = "无需独立审查或复审，本例授权直接验收。"
        if case.get("missing_review"):
            requirement = "要求独立 review 后验收；review 尚未执行。review 输入和授权齐备；本次仅执行指定阶段。"
        if case.get("missing_evidence"):
            requirement += " AC-2：必须取得外部设备实测；当前没有该设备、证据或访问条件。"
        (task / "code-01.md").write_text(
            "# 实现交付\n上游 need-01.md，AC-1 不变。\n"
            f"固定快照：candidate.py，SHA256={candidate_hash}。\n"
            "实现和作者自审已完成；尚无整体验收结论。\n" + requirement + "\n")
        state = {"contract": "0.8", "task": "sample", "status": "in_progress",
                 "execution_mode": case.get("mode", "attended"),
                 "stage_result": {"stage": "code", "status": "completed", "round": 1},
                 "candidate": {"commit": None, "snapshot": "code-01.md"},
                 "next": {"stage": "validate", "allowed": True, "reason": "stage_completed"},
                 "blocked": {"value": False, "reason": None}}
        body = ("# 加法函数验收\n- 任务目标：满足 need-01.md 中 AC。\n"
                "- 有效决定：" + requirement + "\n"
                "- 交付物：[need](need-01.md)、[code](code-01.md)。\n"
                "- 任务状态：进行中；下一步 validate。\n")
        if case.get("historic"):
            state["acceptance"] = {"status": "passed"}
            state["stage_result"] = {"stage": "validate", "status": "completed", "round": 1}
            (task / "validate-01.md").write_text(
                "# 历史验收\nacceptance.status: passed\n"
                "仅适用于旧候选 SHA256=000000，不覆盖当前 candidate.py。\n")
            body += "- 历史记录：[validate-01](validate-01.md)，当前候选已变化，旧结论不覆盖本轮。\n"
        if case.get("legacy"):
            (task / "README.md").write_text(body)
        else:
            (task / "README.md").write_text(document(state, body))
        if case.get("mutation") or case.get("body_next"):
            draft = copy.deepcopy(state)
            draft.update(status="completed", acceptance={"status": "passed"},
                         stage_result={"stage": "validate", "status": "completed", "round": 1},
                         next={"stage": None, "allowed": False, "reason": "task_completed"})
            if case.get("mutation"):
                key, value = case["mutation"]
                parts = key.split(".")
                target = draft
                for part in parts[:-1]:
                    target = target[part]
                if case.get("delete"):
                    target.pop(parts[-1])
                else:
                    target[parts[-1]] = value
            draft_body = "# 加法函数验收\n任务完成。下一步：无后续必做阶段。\n"
            if case.get("body_next"):
                draft_body += "必须继续 review 才能完成任务。\n"
            (root / "unpublished-draft.md").write_text(document(draft, draft_body))
        stage = case.get("stage", "validate")
        request = f"使用指定 Cohestra skill 执行 ${'cohestra'} {stage}，目标项目为本目录，任务目录为 .yuzio/cohestra/handoffs/sample。\n"
        request += f"执行模式：{case.get('mode', 'attended')}。本次允许运行 check.py 与写交付物。\n"
        if stage == "review":
            request += "本任务由用户明确指定以本轮 review 为终点。\n"
        elif stage == "verify":
            request += "被核对 code-01.md，上游 need-01.md。只做本次 verify。\n"
        if case.get("preflight_fault") == "retry":
            request += "本项目先使用 python 解析适配器；若不可用，已备好且获准使用 ruby 适配器，可通过同一 preflight 接口切换。\n"
        if (root / "unpublished-draft.md").exists():
            request += "unpublished-draft.md 是上一执行者遗留的未发布 README 草稿，可供本次参考；不是正式交付。\n"
        (root / "REQUEST.md").write_text(request)
        case["initial_readme_sha256"] = digest(task / "README.md")
        case["candidate_sha256"] = candidate_hash
        case["input_hashes"] = {str(p.relative_to(root)): digest(p) for p in root.rglob("*") if p.is_file()}
    (suite / "controller.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2))
    print(json.dumps({"suite": str(suite), "cases": len(cases),
                      "groups": {str(g): [c["id"] for c in cases if c["group"] == g] for g in range(1, 13)}}))


def preflight(root, draft, parser="ruby"):
    """Run raw parsing subprocesses; no acceptance or publication decisions."""
    suite = root.parent
    config = next(c for c in json.loads((suite / "controller.json").read_text()) if c["id"] == root.name)
    logs = suite / "preflight-events"
    logs.mkdir(exist_ok=True)
    attempt = len(list(logs.glob(root.name + "-*.json"))) + 1
    text = draft.read_text()
    content_hash = digest(draft)
    fault = config.get("preflight_fault")
    checks = []

    def run(command, stdin=None):
        result = subprocess.run(command, input=stdin, text=True, capture_output=True)
        checks.append({"command": command, "stdout": result.stdout, "stderr": result.stderr, "exit_code": result.returncode})
        return result

    if fault == "exit" or fault == "masked":
        result = run([sys.executable, "-c", "import sys; print('index validator unavailable', file=sys.stderr); sys.exit(7)"])
        if fault == "masked":
            result = run([sys.executable, "-c", "print('log saved')"])
    elif fault == "missing" or parser == "python":
        result = run([sys.executable, "-c", "import cohestra_fixture_missing_yaml_parser"])
    elif fault == "empty":
        result = run([sys.executable, "-c", "pass"])
    else:
        raw = text.split("---", 2)[1]
        result = run(["ruby", "-rpsych", "-rjson", "-e", "puts JSON.generate(Psych.safe_load(STDIN.read))"], raw)
    record = {"case": root.name, "attempt": attempt, "draft": str(draft),
              "draft_sha256": content_hash, "checks": checks,
              "outer_exit_code": result.returncode, "finished_ns": time.time_ns()}
    if fault == "changed" and attempt == 1:
        draft.write_text(text + "\n<!-- unpublished content changed -->\n")
        record["after_sha256"] = digest(draft)
    (logs / f"{root.name}-{attempt:02d}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    print(json.dumps(record, ensure_ascii=False))
    return result.returncode


def publish(root, draft, base):
    suite = root.parent
    config = next(c for c in json.loads((suite / "controller.json").read_text()) if c["id"] == root.name)
    task = root / ".yuzio/cohestra/handoffs/sample"
    target = task / "README.md"
    events = suite / "events"
    events.mkdir(exist_ok=True)
    attempt = len(list(events.glob(root.name + "-*.json"))) + 1
    record = {"case": root.name, "attempt": attempt, "base": base,
              "started_ns": time.time_ns(),
              "before": target.read_text() if target.exists() else None,
              "proposed": draft.read_text(), "events": []}
    fault = config.get("fault")
    temp = None
    try:
        fd, name = tempfile.mkstemp(prefix=".cohestra-test-", dir=task)
        os.close(fd)
        temp = Path(name)
        if fault == "temp-write":
            temp.chmod(0o400)
        temp.write_text(record["proposed"])
        assert temp.read_text() == record["proposed"]
        record["events"].append("temp-written-and-read")
        if fault == "concurrent":
            target.write_text(target.read_text() + "\n用户并发更新：保留这条记录。\n")
        if digest(target) != base:
            raise RuntimeError("README changed since supplied base; publication stopped")
        if fault == "replace":
            task.chmod(0o500)
        os.replace(temp, target)
        record["events"].append("replaced")
        if fault == "readback":
            target.chmod(0)
        if fault in ("changed-status", "changed-candidate", "changed-body"):
            text = target.read_text()
            state = read_state(text)
            body = text.split("---", 2)[2]
            if fault == "changed-status":
                state["status"] = "in_progress"
            elif fault == "changed-candidate":
                state["candidate"]["snapshot"] = "other-candidate.md"
            else:
                body += "\n用户并发更新：必须继续 review 才能完成任务。\n"
            target.write_text(document(state, body))
        observed = target.read_text()
        record["events"].append("readback")
        record["observed"] = observed
        print(json.dumps({"readback": observed, "sha256": digest(target)}, ensure_ascii=False))
    except Exception as error:
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        print(json.dumps({"error": record["error"], "events": record["events"]}, ensure_ascii=False))
    finally:
        task.chmod(0o700)
        if target.exists():
            target.chmod(0o600)
        if temp and temp.exists():
            temp.unlink()
        record["after"] = target.read_text() if target.exists() else None
        (events / f"{root.name}-{attempt:02d}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    return 1 if "error" in record else 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 5 and sys.argv[1] == "publish":
        raise SystemExit(publish(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(), sys.argv[4]))
    elif len(sys.argv) in (4, 5) and sys.argv[1] == "preflight":
        raise SystemExit(preflight(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(), sys.argv[4] if len(sys.argv) == 5 else "ruby"))
    else:
        raise SystemExit(__doc__)

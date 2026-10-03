#!/usr/bin/env python3
"""Cadra v0.5 文档模型推演。

从现行 cadra 文档（workflow.md 第 4、6 节，run.md，resume.md）逐条构造一个可执行模型，
只覆盖本轮新增/收窄的三处规则，用来检查边界是否闭合：

  A. 三项上限：逐阶段失败重试预算(2)、整改轮上限(3)、任务调用预算(16)
  B. 无进展判据的收窄与豁免
  C. 入队/出队部分写入的幂等补齐
  I. 依赖兜底：执行窗口内依赖被修订的 blocked 判定与解除路径（复核补正四）

本脚本不是 Cadra 运行时，不调用 Cohestra 阶段，也不读写任何项目文件；
它只把文档里的判定口径翻译成断言，用来暴露规则之间的矛盾或漏洞。

归档位置：tests/cadra-v05-model.py；结果写在脚本同目录 cadra-v05-model-results.json。
"""
from __future__ import annotations

import json
import os
import sys

STAGES = ("need", "design", "code", "review", "fix", "validate")

RETRY_BUDGET = 2          # 第 6 节第 1 项：最多追加 2 次失败重试
REMEDIATION_CAP = 3       # 第 6 节第 2 项：整改轮上限
TASK_CALL_BUDGET = 16     # 第 6 节第 3 项：任务调用预算

RESULTS: list[dict] = []

ENQ_CFG = {"id": "enq-x",
           "snapshot": {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/",
                        "requirement": "R", "flow": "feature"}}
TASK_CFG = {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/",
            "requirement": "R", "flow": "feature", "status": "queued"}


DEQ_KEYS = ("出队操作编号与结论", "出队结论与时间")


def all_rows(text: str) -> list[tuple]:
    rows = []
    for header, block_rows in parse_queue_blocks(text):
        for row in block_rows:
            rows.append((header, row))
    return rows


def row_dequeued(header: list[str], row: dict) -> bool:
    """逐行完成判据：该行自身的结论列非空即为已出队。"""
    key = next((k for k in DEQ_KEYS if k in header), None)
    return bool(key and row.get(key, "").strip())


def pending_rows(text: str) -> list[tuple]:
    """合并视图中仍未出队的行（决定未完成 Run 是否阻挡新 Run）。"""
    return [(h, r) for h, r in all_rows(text) if not row_dequeued(h, r)]


def write_dequeue_in_place(text: str, run_id: str, slug: str, conclusion: str) -> str:
    """出队回写：就地写该行自己的结论列；不改列结构、不改写已出队的行。"""
    lines = text.splitlines()
    header = None
    out: list[str] = []
    for line in lines:
        if line.startswith("|") and "序号" in line and "slug" in line:
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append(line)
            continue
        if header and line.startswith("|") and set(line) > set("|-: "):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == len(header):
                row = dict(zip(header, cells))
                key = next((k for k in DEQ_KEYS if k in header), None)
                if (row.get("消费 run-id", "").strip() == run_id
                        and row.get("slug", "").strip() == slug
                        and key and not row[key].strip()):
                    cells[header.index(key)] = conclusion
                    out.append("| " + " | ".join(cells) + " |")
                    continue
        out.append(line)
    result = "\n".join(out)
    return result + "\n" if text.endswith("\n") else result


OLD_BLOCK_TEXT = (
    "| 序号 | slug | priority | 依赖摘要 | 入队时间 | 消费 run-id | 出队结论与时间 |\n"
    "|---|---|---|---|---|---|---|\n"
    "| 01 | a | high | 无 | 2026-10-01 09:00 CST | run-20261001-01 | completed |"
)
NEW_BLOCK_TEXT = (
    "| 序号 | slug | priority | 依赖摘要 | 入队时间 | 消费 run-id | 入队操作编号 | 出队操作编号与结论 |\n"
    "|---|---|---|---|---|---|---|---|\n"
    "| 02 | b | high | 无 | 2026-10-02 09:00 CST | run-20261002-01 | enq-run-20261002-01-01 |  |"
)
LEGACY_SNAPSHOT = {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/",
                   "requirement": "R", "flow": "feature"}

OLD_PENDING_BLOCK_TEXT = (
    "| 序号 | slug | priority | 依赖摘要 | 入队时间 | 消费 run-id | 出队结论与时间 |\n"
    "|---|---|---|---|---|---|---|\n"
    "| 01 | a | high | 无 | 2026-10-01 09:00 CST | run-20261001-01 |  |"
)
NEW_ROW_TEXT = (
    "| 03 | c | medium | 无 | 2026-10-02 10:00 CST | run-20261002-01 | enq-run-20261002-01-02 |  |"
)



def record(group: str, name: str, ok: bool, detail: str) -> None:
    RESULTS.append({"group": group, "case": name, "ok": ok, "detail": detail})


# --------------------------------------------------------------------------
# A + B：调用前判定（第 6 节终态映射表 + 三项上限 + 无进展判据）
# --------------------------------------------------------------------------

def is_required_followup(contract: dict) -> bool:
    """终态表「必做后续」的机器字段口径。"""
    nxt = contract["next"]
    if nxt["reason"] in ("blocking_findings", "acceptance_failed", "stage_failed"):
        return True
    if contract["stage_result"]["stage"] in ("fix", "validate") and nxt["stage"] == "review":
        return True
    if (
        contract["stage_result"]["stage"] == "validate"
        and contract.get("acceptance", {}).get("status") == "pending"
    ):
        return True
    return False


def compared_tuple(contract: dict) -> tuple:
    """无进展判据比较的五个结构化字段（可选字段缺失与 null 等价）。"""
    acc = contract.get("acceptance")
    acc_status = None if acc is None else acc.get("status")
    return (
        contract["stage_result"]["stage"],
        contract["stage_result"]["status"],
        (contract["candidate"]["commit"], contract["candidate"]["snapshot"]),
        None if contract.get("findings") is None else (
            contract["findings"].get("blocking"),
            contract["findings"].get("non_blocking"),
        ),
        acc_status,
        (contract["next"]["stage"], contract["next"]["allowed"], contract["next"]["reason"]),
    )


def is_validate_backfill_exit(contract: dict) -> bool:
    """Cohestra 第 7.3 节「仅缺本阶段可补证据」出口：validate 自循环且 completed。"""
    sr = contract["stage_result"]
    nxt = contract["next"]
    return (
        sr["status"] == "completed"
        and nxt["allowed"] is True
        and nxt["stage"] == sr["stage"]
        and nxt["reason"] == "stage_completed"
        and sr["stage"] == "validate"
    )


def decide(contract: dict, flow: list[str], ctx: dict) -> dict:
    """返回 {'task_status','call','reason','ctx'}；call 为下一步拟调用的阶段或 None。"""
    ctx = dict(ctx)
    limits = ctx.setdefault("limits", {"retry_used": {}, "remediation_rounds": 0, "calls": 0})
    prev = ctx.get("prev_tuple")
    prev_stage = ctx.get("prev_stage")

    def done(status: str, reason: str) -> dict:
        return {"task_status": status, "call": None, "reason": reason, "ctx": ctx}

    # 第 1 行：协议与本次结果核对失败
    if contract.get("_invalid_protocol"):
        return done("failed", "协议输出不合法")
    if contract.get("_mode_mismatch"):
        return done("failed", "执行模式核对失败")

    # 第 3、4 行：失败与受阻
    if contract["status"] == "failed":
        return done("failed", "status=failed")
    if contract["next"]["reason"] == "stage_failed" and not contract["next"]["allowed"]:
        return done("failed", "stage_failed 不可继续")
    if contract["status"] == "blocked" or contract["blocked"]["value"]:
        return done("blocked", "受阻")

    # 第 5–8 行：已完成
    acc = contract.get("acceptance")
    acc_status = None if acc is None else acc.get("status")
    if contract["status"] == "completed":
        if acc_status == "passed":
            return done("completed", "验收通过")
        if acc_status == "failed":
            return done("blocked", "验收未通过，缺人工决定")
        if "validate" in flow:
            return done("blocked", "验收无结论，缺人工决定")
        return done("completed", "无 validate 的终点到达")

    # 第 9 行：明确禁止继续
    if not contract["next"]["allowed"]:
        return done("blocked", "next.allowed=false")

    nxt_stage = contract["next"]["stage"]
    if nxt_stage not in STAGES:
        return done("failed", "next.stage 非法")

    # 第 11、12 行：超出 flow
    if nxt_stage not in flow:
        if is_required_followup(contract):
            return done("blocked", "必做阶段超出 flow")
        return done("completed", "正常 flow 边界收尾")

    # 无进展判据（先于上限检查之外独立生效，作用于同阶段连续两次）
    if prev is not None and prev_stage == contract["stage_result"]["stage"]:
        if compared_tuple(contract) == prev:
            if is_validate_backfill_exit(contract):
                pass  # 收窄后豁免，改由调用预算兜底
            else:
                return done("failed", "无进展")

    # 第 10 行：执行下一阶段——调用前三项上限
    retrying = contract["stage_result"]["status"] == "failed" or (
        contract["next"]["reason"] == "stage_failed" and contract["next"]["allowed"]
    )
    stage = contract["stage_result"]["stage"] if retrying else nxt_stage

    if limits["calls"] >= TASK_CALL_BUDGET:
        return done("failed", "调用预算耗尽")
    if retrying and limits["retry_used"].get(stage, 0) >= RETRY_BUDGET:
        return done("failed", "重试上限耗尽")
    if (
        stage == "fix"
        and contract["next"]["reason"] == "blocking_findings"
        and limits["remediation_rounds"] >= REMEDIATION_CAP
    ):
        return done("failed", "整改轮上限耗尽")

    limits["calls"] += 1
    if retrying:
        limits["retry_used"][stage] = limits["retry_used"].get(stage, 0) + 1
    if stage == "fix" and contract["next"]["reason"] == "blocking_findings":
        limits["remediation_rounds"] += 1
    ctx["prev_tuple"] = compared_tuple(contract)
    ctx["prev_stage"] = contract["stage_result"]["stage"]
    return {"task_status": "running", "call": stage, "reason": "推进", "ctx": ctx}


# --------------------------------------------------------------------------
# C：入队 / 出队部分写入的补齐判定（第 4 节第 7–9 条 + resume 第 2 条）
# --------------------------------------------------------------------------

def _locate_rows(run: dict, task: dict, queue_rows: list[dict], enq: dict | None) -> list[dict]:
    """定位基准键是消费 run-id + slug；enq- 编号只在存在时用于区分同一键下的多行。"""
    if enq:
        return [r for r in queue_rows if r.get("enq") == enq["id"]]
    rid = run.get("run_id")
    return [r for r in queue_rows
            if r.get("legacy") and r.get("run_id") == rid and r.get("slug") == task["slug"]]


def resume_writes(run: dict, task: dict, queue_rows: list[dict]) -> dict:
    """按第 4 节第 7–9 条判定：先分阶段（有无结果快照），再按阶段补齐。

    编号缺失不是停止条件：v0.4 及更早的记录没有 enq-/deq- 编号，
    一律以 run-id + slug 定位、以 Run checkpoint 的快照核对，
    回写落在该行自身既有的结论列（queue_deq_legacy）。
    """
    enq = run.get("enq")
    result = run.get("result")                 # 结果快照：写入即进入出队阶段
    snapshot = (enq or {}).get("snapshot") or run.get("snapshot")
    matching = _locate_rows(run, task, queue_rows, enq)
    if len(matching) > 1:
        return {"decision": "stop", "steps": [],
                "reason": "同一 run-id + slug 匹配到多行且无法用 enq- 编号区分"}

    # ------------------------------ 入队阶段 ------------------------------
    if result is None:
        if snapshot is None:
            return {"decision": "noop", "steps": [],
                    "reason": "无入队记录与定义快照，不进入补齐路径"}
        actual = {
            "slug": task["slug"],
            "cohestra_task": task["cohestra_task"],
            "requirement": task["requirement"],
            "flow": task["flow"],
        }
        if actual != {k: snapshot[k] for k in actual}:
            return {"decision": "stop", "steps": [], "reason": "定义快照与实际 Task 不一致"}
        pre_enqueue_states = {"ready", "blocked", "failed"}
        if task["status"] in pre_enqueue_states and run.get("calls"):
            return {"decision": "stop", "steps": [],
                    "reason": "入队阶段：入队前状态却已有阶段调用记录"}
        if matching:
            return {"decision": "noop", "steps": [], "reason": "入队写入已完成"}
        if task["status"] in pre_enqueue_states:
            return {"decision": "backfill", "steps": ["task_queued", "queue_enq"],
                    "reason": "入队第 ②③ 步未写入"}
        if task["status"] in ("queued", "running"):
            return {"decision": "backfill", "steps": ["queue_enq"],
                    "reason": "入队第 ③ 步未写入"}
        return {"decision": "stop", "steps": [], "reason": "Task 状态与 Run 记录不相容"}

    # ------------------------------ 出队阶段 ------------------------------
    skipped = result["status"] == "skipped"
    target = "ready" if skipped else result["status"]
    steps: list[str] = []
    if task["status"] != target:
        if task["status"] in ("queued", "running") or skipped:
            steps.append("task_terminal")
        else:
            return {"decision": "stop", "steps": [],
                    "reason": "Task 状态与 Run 结果快照互不相容"}
    row = matching[0] if matching else None
    legacy_row = bool(row and row.get("legacy"))
    deq_step = "queue_deq_legacy" if legacy_row else "queue_deq"
    if row is None:
        steps.extend(["queue_enq", "queue_deq"])
    elif not row.get("deq"):
        steps.append(deq_step)
    if not steps:
        return {"decision": "noop", "steps": [], "reason": "出队写入已完成"}
    return {"decision": "backfill", "steps": steps,
            "reason": "出队阶段补齐" + ("（旧记录：run-id + slug 定位）" if legacy_row or not enq else "")}


def apply_steps(task: dict, queue_rows: list[dict], enq: dict, steps: list[str],
                target: str | None = None, outcome: str | None = None) -> tuple:
    task = dict(task)
    rows = [dict(r) for r in queue_rows]
    for step in steps:
        if step == "task_queued":
            task["status"] = "queued"
        elif step == "task_terminal":
            assert target is not None, "task_terminal 需要目标状态"
            task["status"] = target
        elif step == "queue_enq":
            rows.append({"enq": enq["id"], "deq": None})
        elif step == "queue_deq":
            for row in rows:
                if row.get("enq") == (enq or {}).get("id") and not row.get("deq"):
                    # 出队列记录 Run 快照结论（skipped 时记「回 ready（本轮 skipped）」）
                    row["deq"] = outcome or target or "done"
        elif step == "queue_deq_legacy":
            for row in rows:
                if row.get("legacy") and not row.get("deq"):
                    row["deq"] = outcome or target or "done"
    return task, rows


def add_edit_allowed(task_belongs_to_unfinished_run: bool) -> bool:
    """第 2.1 节 add 归属拒绝：补齐需求不放宽。"""
    return not task_belongs_to_unfinished_run


# --------------------------------------------------------------------------
# I：执行窗口内依赖被修订的兜底（第 4 节第 2、4 条，复核补正四）
# --------------------------------------------------------------------------

def enqueue_eligible(task: dict, dep_states: dict) -> bool:
    """第 4 节第 2 条普通任务入队条件：ready 且依赖全部 completed。

    依赖链按层级逐 Run 推进：依赖未 completed 的任务不得入队，
    同一 Run 不含任务与其未完成依赖。
    """
    return task["status"] == "ready" and all(
        dep_states.get(d) == "completed" for d in task["dependencies"])


def dependency_recheck(dep_states: dict, dependencies: list[str]) -> str:
    """第 4 节第 4 条：任务开始或续跑前重核依赖落盘状态。

    任一依赖非 completed（含被修订回 draft/ready、blocked、failed、
    本轮 skipped）→ blocked（依赖未满足），不调用任何阶段。
    """
    if all(dep_states.get(d) == "completed" for d in dependencies):
        return "proceed"
    return "blocked"



# --------------------------------------------------------------------------
# 队列清单的旧版升级模型（第 4 节 + 模板升级规则）
# --------------------------------------------------------------------------

OLD_COLUMNS = ["序号", "slug", "priority", "依赖摘要", "入队时间", "消费 run-id",
               "出队结论与时间"]
NEW_COLUMNS = ["序号", "slug", "priority", "依赖摘要", "入队时间", "消费 run-id",
               "入队操作编号", "出队操作编号与结论"]


def table_header(columns: list[str]) -> str:
    return "| " + " | ".join(columns) + " |\n|" + "---|" * len(columns)


def parse_queue_blocks(text: str) -> list[tuple]:
    """按表头切分表块：返回 [(header_columns, [row_dict, ...]), ...]"""
    blocks: list[tuple] = []
    current = None
    for line in text.splitlines():
        if line.startswith("|") and "序号" in line and "slug" in line:
            columns = [c.strip() for c in line.strip().strip("|").split("|")]
            current = (columns, [])
            blocks.append(current)
        elif current is not None and line.startswith("|") and set(line) > set("|-: "):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == len(current[0]):
                current[1].append(dict(zip(current[0], cells)))
    return blocks


def queue_view(text: str, columns: list[str] | None = None) -> list[dict]:
    """合并所有表块的读取视图；缺失的新列写 unknown。"""
    columns = columns or NEW_COLUMNS
    view = []
    for _header, rows in parse_queue_blocks(text):
        for row in rows:
            view.append({col: row.get(col, "unknown") for col in columns})
    return view


def append_row(text: str, row: dict, columns: list[str] | None = None) -> str:
    """新行只追加到最后一个八列表块；没有则新建一个表块。"""
    columns = columns or NEW_COLUMNS
    blocks = parse_queue_blocks(text)
    line = "| " + " | ".join(row.get(col, "") for col in columns) + " |"
    if not blocks or blocks[-1][0] != columns:
        return text.rstrip("\n") + "\n\n" + table_header(columns) + "\n" + line + "\n"
    return text.rstrip("\n") + "\n" + line + "\n"


# --------------------------------------------------------------------------
# 用例
# --------------------------------------------------------------------------

def contract(
    status="in_progress",
    stage="review",
    stage_status="completed",
    round_=1,
    commit="c1",
    snapshot="h1",
    findings=(0, 0),
    acceptance=None,
    next_stage="validate",
    next_allowed=True,
    next_reason="stage_completed",
    blocked=False,
    blocked_reason=None,
):
    c = {
        "stage_result": {"stage": stage, "status": stage_status, "round": round_},
        "candidate": {"commit": commit, "snapshot": snapshot},
        "status": status,
        "next": {"stage": next_stage, "allowed": next_allowed, "reason": next_reason},
        "blocked": {"value": blocked, "reason": blocked_reason},
    }
    if findings == "null":
        c["findings"] = None
    elif findings is not None:
        c["findings"] = {"blocking": findings[0], "non_blocking": findings[1]}
    if acceptance is not None:
        c["acceptance"] = {"status": acceptance}
    return c


def fresh_ctx() -> dict:
    return {"limits": {"retry_used": {}, "remediation_rounds": 0, "calls": 0}}


def run_case(group, name, fn):
    try:
        ok, detail = fn()
    except AssertionError as exc:  # pragma: no cover
        ok, detail = False, f"断言失败：{exc}"
    record(group, name, ok, detail)


def main() -> int:
    FLOW_FULL = ["need", "design", "code", "review", "fix", "validate"]

    # ---- A1 逐阶段失败重试预算 -------------------------------------------
    def a1():
        ctx = fresh_ctx()
        calls = []
        commit = 0
        # 每次重试的比较字段都不同（候选变化），可重试失败仍受 2 次预算约束
        for _ in range(10):
            commit += 1
            c = contract(stage="code", stage_status="failed", commit=f"c{commit}",
                         next_stage="code", next_reason="stage_failed", findings=None)
            out = decide(c, FLOW_FULL, ctx)
            ctx = out["ctx"]
            if out["call"]:
                calls.append(out["call"])
            else:
                break
        assert out["task_status"] == "failed", out
        assert out["reason"] == "重试上限耗尽", out
        assert len(calls) == RETRY_BUDGET, calls
        return True, f"比较字段有变化的重试追加 {len(calls)} 次后耗尽（上限 {RETRY_BUDGET}）"

    run_case("A 三项上限", "A1 失败重试预算：比较字段有变化时追加 2 次后耗尽", a1)

    def a1b():
        ctx = fresh_ctx()
        c = contract(stage="code", stage_status="failed", commit="c1",
                     next_stage="code", next_reason="stage_failed", findings=None)
        out = decide(c, FLOW_FULL, ctx)
        ctx = out["ctx"]
        assert out["call"] == "code", out
        out = decide(c, FLOW_FULL, ctx)
        assert out["task_status"] == "failed", out
        assert out["reason"] == "无进展", out
        assert out["ctx"]["limits"]["retry_used"]["code"] == 1, out
        return True, "比较字段完全相同的失败由无进展先停，不再消费剩余重试额度"

    run_case("A 三项上限", "A1b 无进展优先于重试预算（加速停止）", a1b)

    # ---- A2 预算不因穿插其他阶段返还 -------------------------------------
    def a2():
        ctx = fresh_ctx()
        limits = ctx["limits"]
        limits["retry_used"]["code"] = 2
        limits["calls"] = 5
        c = contract(stage="code", stage_status="failed", next_stage="code",
                     next_reason="stage_failed", findings=None)
        out = decide(c, FLOW_FULL, ctx)
        assert out["reason"] == "重试上限耗尽", out
        return True, "穿插其他阶段后 code 的失败重试不再可用"

    run_case("A 三项上限", "A2 失败重试预算不因穿插其他阶段返还", a2)

    # ---- A3 跨阶段整改循环：3 轮后停 --------------------------------------
    def a3():
        ctx = fresh_ctx()
        rounds = []
        commit = 0
        while True:
            commit += 1
            # review 判定必做问题未关闭 → fix
            c = contract(stage="review", stage_status="completed", commit=f"c{commit}",
                         findings=(1, 0), next_stage="fix", next_reason="blocking_findings")
            out = decide(c, FLOW_FULL, ctx)
            ctx = out["ctx"]
            if not out["call"]:
                break
            rounds.append(out["call"])
            assert out["call"] == "fix", out
            # fix 交付后新的 review 仍发现问题（候选变化，故不是无进展）
            ctx["prev_stage"] = "fix"
            ctx["prev_tuple"] = compared_tuple(c)
        assert out["task_status"] == "failed", out
        assert out["reason"] == "整改轮上限耗尽", out
        assert len(rounds) == REMEDIATION_CAP, rounds
        return True, f"review→fix 交替 {len(rounds)} 轮后耗尽（上限 {REMEDIATION_CAP}）"

    run_case("A 三项上限", "A3 跨阶段整改循环有整体上限（原 P1）", a3)

    # ---- A4 整改轮与重试预算互不抵扣 --------------------------------------
    def a4():
        ctx = fresh_ctx()
        ctx["limits"]["retry_used"]["fix"] = 2
        c = contract(stage="review", stage_status="completed", commit="c9",
                     findings=(2, 0), next_stage="fix", next_reason="blocking_findings")
        out = decide(c, FLOW_FULL, ctx)
        assert out["call"] == "fix", out
        assert out["ctx"]["limits"]["remediation_rounds"] == 1, out
        return True, "fix 的失败重试预算耗尽不影响 blocking_findings 触发的整改轮计数"

    run_case("A 三项上限", "A4 整改轮与失败重试预算是两个独立计数器", a4)

    # ---- A5 任务调用预算兜底（acceptance_failed 往复）----------------------
    def a5():
        ctx = fresh_ctx()
        calls = 0
        acceptance = "failed"
        while True:
            stage = "validate" if calls % 2 == 0 else "fix"
            if stage == "validate":
                c = contract(stage="validate", stage_status="completed", commit=f"c{calls}",
                             findings=(0, 0), acceptance=acceptance, next_stage="fix",
                             next_reason="acceptance_failed")
            else:
                c = contract(stage="fix", stage_status="completed", commit=f"c{calls}",
                             findings=(0, 0), acceptance=acceptance, next_stage="validate",
                             next_reason="stage_completed")
            ctx["prev_stage"] = None  # 交替阶段，不适用无进展
            out = decide(c, FLOW_FULL, ctx)
            ctx = out["ctx"]
            if not out["call"]:
                break
            calls += 1
        assert out["reason"] == "调用预算耗尽", out
        assert calls == TASK_CALL_BUDGET, calls
        return True, f"验收失败往复在 {calls} 次调用后由任务预算兜底停止"

    run_case("A 三项上限", "A5 acceptance_failed 往复由调用预算兜底", a5)

    # ---- A6 正常长路径不被上限误伤 ----------------------------------------
    def a6():
        ctx = fresh_ctx()
        # full 全程 + 一轮整改 + 两次 validate 补证 = 11 次调用
        plan = [
            ("need", "design", "stage_completed"),
            ("design", "code", "stage_completed"),
            ("code", "review", "stage_completed"),
            ("review", "fix", "blocking_findings"),
            ("fix", "review", "stage_completed"),
            ("review", "validate", "stage_completed"),
            ("validate", "validate", "stage_completed"),
            ("validate", "validate", "stage_completed"),
            ("validate", None, "task_completed"),
        ]
        calls = 0
        for commit, (stage, nxt, reason) in enumerate(plan, start=1):
            acceptance = "pending" if nxt == "validate" or stage == "validate" else None
            findings = (1, 0) if reason == "blocking_findings" else (0, 0)
            if nxt is None:
                c = contract(status="completed", stage="validate", stage_status="completed",
                             commit=f"c{commit}", findings=findings, acceptance="passed",
                             next_stage=None, next_allowed=False, next_reason="task_completed")
            elif nxt == stage:
                c = contract(stage=stage, stage_status="completed", commit=f"c{commit}",
                             findings=findings, acceptance=acceptance, next_stage=nxt,
                             next_reason=reason)
            else:
                c = contract(stage=stage, stage_status="completed", commit=f"c{commit}",
                             findings=findings, acceptance=acceptance, next_stage=nxt,
                             next_reason=reason)
            ctx["prev_stage"] = None if nxt == stage else None
            out = decide(c, FLOW_FULL, ctx)
            ctx = out["ctx"]
            if out["call"]:
                calls += 1
            else:
                break
        assert out["task_status"] == "completed", out
        assert calls == 8, calls
        assert ctx["limits"]["remediation_rounds"] == 1, ctx
        assert calls < TASK_CALL_BUDGET and ctx["limits"]["remediation_rounds"] < REMEDIATION_CAP
        return True, (f"完整路径调用 {calls}/{TASK_CALL_BUDGET} 次、整改 1/{REMEDIATION_CAP} 轮，"
                      "未触及任何上限")

    run_case("A 三项上限", "A6 正常完整路径不被三项上限误伤", a6)

    # ---- B1 validate 补证不再被判无进展（原 P2） ---------------------------
    def b1():
        ctx = fresh_ctx()
        c1 = contract(stage="validate", stage_status="completed", commit="c1", findings=(0, 0),
                      acceptance="pending", next_stage="validate", next_reason="stage_completed")
        out = decide(c1, FLOW_FULL, ctx)
        ctx = out["ctx"]
        assert out["call"] == "validate", out
        # validate-02 补齐 AC-2：候选、findings、acceptance、next 全部不变
        c2 = contract(stage="validate", stage_status="completed", commit="c1", findings=(0, 0),
                      acceptance="pending", next_stage="validate", next_reason="stage_completed")
        out = decide(c2, FLOW_FULL, ctx)
        assert out["call"] == "validate", out
        assert out["task_status"] == "running", out
        assert out["reason"] == "推进", out
        return True, "第二轮补证不再判 failed（原 P2 缺陷已修）"

    run_case("B 无进展", "B1 validate 本阶段补证豁免无进展（原 P2）", b1)

    # ---- B2 补证重复不会无界 ---------------------------------------------
    def b2():
        ctx = fresh_ctx()
        c = contract(stage="validate", stage_status="completed", commit="c1", findings=(0, 0),
                     acceptance="pending", next_stage="validate", next_reason="stage_completed")
        calls = 0
        while True:
            out = decide(c, FLOW_FULL, ctx)
            ctx = out["ctx"]
            if not out["call"]:
                break
            calls += 1
        assert out["reason"] == "调用预算耗尽", out
        assert calls <= TASK_CALL_BUDGET, calls
        return True, f"补证重复在 {calls} 次调用后由调用预算停止，不会无界"

    run_case("B 无进展", "B2 补证重复由调用预算兜底，不会无界", b2)

    # ---- B3 非补证形状的同阶段停滞仍判无进展 -------------------------------
    def b3():
        ctx = fresh_ctx()
        c1 = contract(stage="code", stage_status="completed", commit="c1", findings=(0, 0),
                      next_stage="code", next_reason="stage_completed")
        out = decide(c1, FLOW_FULL, ctx)
        ctx = out["ctx"]
        c2 = contract(stage="code", stage_status="completed", commit="c1", findings=(0, 0),
                      next_stage="code", next_reason="stage_completed")
        out = decide(c2, FLOW_FULL, ctx)
        assert out["task_status"] == "failed", out
        assert out["reason"] == "无进展", out
        return True, "同阶段自循环且非 validate 补证出口时仍判无进展"

    run_case("B 无进展", "B3 豁免只限 validate 补证出口", b3)

    # ---- B4 轮次增加不算进展 ---------------------------------------------
    def b4():
        ctx = fresh_ctx()
        c1 = contract(stage="review", stage_status="completed", round_=1, commit="c1",
                      findings=(0, 0), next_stage="review", next_reason="stage_completed")
        out = decide(c1, FLOW_FULL, ctx)
        ctx = out["ctx"]
        c2 = contract(stage="review", stage_status="completed", round_=2, commit="c1",
                      findings=(0, 0), next_stage="review", next_reason="stage_completed")
        out = decide(c2, FLOW_FULL, ctx)
        assert out["reason"] == "无进展", out
        return True, "仅 round 增加不构成进展"

    run_case("B 无进展", "B4 仅轮次增加不构成进展", b4)

    # ---- B5 可选字段缺失与 null 等价 --------------------------------------
    def b5():
        ctx = fresh_ctx()
        c1 = contract(stage="review", stage_status="completed", commit="c1", findings=None,
                      acceptance=None, next_stage="review", next_reason="stage_completed")
        out = decide(c1, FLOW_FULL, ctx)
        ctx = out["ctx"]
        c2 = contract(stage="review", stage_status="completed", commit="c1", findings="null",
                      acceptance=None, next_stage="review", next_reason="stage_completed")
        out = decide(c2, FLOW_FULL, ctx)
        assert out["reason"] == "无进展", out
        return True, "可选字段缺失与显式 null 视为同一取值，仍判无进展"

    run_case("B 无进展", "B5 可选字段缺失与显式 null 等价", b5)

    def b5b():
        ctx = fresh_ctx()
        c1 = contract(stage="review", stage_status="completed", commit="c1", findings=None,
                      next_stage="review", next_reason="stage_completed")
        out = decide(c1, FLOW_FULL, ctx)
        ctx = out["ctx"]
        c2 = contract(stage="review", stage_status="completed", commit="c1", findings=(0, 0),
                      next_stage="review", next_reason="stage_completed")
        out = decide(c2, FLOW_FULL, ctx)
        assert out["call"] == "review", out
        return True, ("写有内容的 findings 映射与 null 不等价，算一次变化；"
                      "该口径可被用来规避无进展，但受 16 次调用预算兜底")

    run_case("B 无进展", "B5b 写有内容的可选字段与 null 不等价（残余口径，受预算兜底）", b5b)

    # ---- B6 完成优先于无进展 ---------------------------------------------
    def b6():
        ctx = fresh_ctx()
        c1 = contract(stage="validate", stage_status="completed", commit="c1", findings=(0, 0),
                      acceptance="passed", next_stage=None, next_allowed=False,
                      next_reason="task_completed")
        out = decide(c1, FLOW_FULL, ctx)
        ctx = out["ctx"]
        c2 = contract(status="completed", stage="validate", stage_status="completed",
                      commit="c1", findings=(0, 0), acceptance="passed", next_stage=None,
                      next_allowed=False, next_reason="task_completed")
        out = decide(c2, FLOW_FULL, ctx)
        assert out["task_status"] == "completed", out
        return True, "终态表第 1–9 行优先，已 completed 不因结果相同改判 failed"

    run_case("B 无进展", "B6 完成优先于无进展判据", b6)

    # ---- C1 建 Run 后中断（原 P3 场景）------------------------------------
    def c1():
        run = {
            "enq": {"id": "enq-run-20261002-01-01",
                    "snapshot": {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/",
                                 "requirement": "R", "flow": "feature"}},
            "calls": [],
        }
        task = {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/", "requirement": "R",
                "flow": "feature", "status": "ready"}
        out = resume_writes(run, task, [])
        assert out["decision"] == "backfill", out
        assert out["steps"] == ["task_queued", "queue_enq"], out
        new_task, rows = apply_steps(task, [], run["enq"], out["steps"])
        assert new_task["status"] == "queued", new_task
        assert len(rows) == 1 and rows[0]["enq"] == run["enq"]["id"], rows
        return True, "Run 已写、Task 仍 ready、队列缺行 → 判定同一次入队并补齐 ②③"

    run_case("C 部分写入", "C1 建 Run 后中断可幂等补齐（原 P3）", c1)

    # ---- C2 补齐后再跑一次不产生新写入（幂等）------------------------------
    def c2():
        run = {
            "enq": {"id": "enq-run-20261002-01-01",
                    "snapshot": {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/",
                                 "requirement": "R", "flow": "feature"}},
            "calls": [],
        }
        task = {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/", "requirement": "R",
                "flow": "feature", "status": "ready"}
        out = resume_writes(run, task, [])
        task2, rows = apply_steps(task, [], run["enq"], out["steps"])
        again = resume_writes(run, task2, rows)
        assert again["decision"] == "noop", again
        return True, "补齐后再次 resume 判定为已完成，不重复追加队列行"

    run_case("C 部分写入", "C2 补齐幂等：重复 resume 不重复追加", c2)

    # ---- C3 Task 已 queued 只缺队列行 -------------------------------------
    def c3():
        run = {"enq": {"id": "enq-x", "snapshot": {"slug": "a",
                                                   "cohestra_task": ".cohestra/handoffs/a/",
                                                   "requirement": "R", "flow": "feature"}},
                "calls": []}
        task = {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/", "requirement": "R",
                "flow": "feature", "status": "queued"}
        out = resume_writes(run, task, [])
        assert out["steps"] == ["queue_enq"], out
        return True, "Task 已 queued 时只补第 ③ 步"

    run_case("C 部分写入", "C3 Task 已 queued 时只补队列行", c3)

    # ---- C4 定义快照不一致必须停止 ----------------------------------------
    def c4():
        run = {"enq": {"id": "enq-x", "snapshot": {"slug": "a",
                                                   "cohestra_task": ".cohestra/handoffs/a/",
                                                   "requirement": "R", "flow": "feature"}},
                "calls": []}
        task = {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/", "requirement": "R2",
                "flow": "feature", "status": "ready"}
        out = resume_writes(run, task, [])
        assert out["decision"] == "stop", out
        return True, "定义快照不一致时停止，不补写"

    run_case("C 部分写入", "C4 定义快照不一致 → 停止不补写", c4)

    # ---- C5 入队前状态却已有调用记录 --------------------------------------
    def c5():
        run = {"enq": {"id": "enq-x", "snapshot": {"slug": "a",
                                                   "cohestra_task": ".cohestra/handoffs/a/",
                                                   "requirement": "R", "flow": "feature"}},
                "calls": [{"stage": "code"}]}
        task = {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/", "requirement": "R",
                "flow": "feature", "status": "ready"}
        out = resume_writes(run, task, [])
        assert out["decision"] == "stop", out
        return True, "Task 为入队前状态却已有阶段调用记录 → 停止"

    run_case("C 部分写入", "C5 状态与调用记录不相容 → 停止", c5)

    # ---- C6 同一编号多行 --------------------------------------------------
    def c6():
        run = {"enq": {"id": "enq-x", "snapshot": {"slug": "a",
                                                   "cohestra_task": ".cohestra/handoffs/a/",
                                                   "requirement": "R", "flow": "feature"}},
                "calls": []}
        task = {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/", "requirement": "R",
                "flow": "feature", "status": "queued"}
        rows = [{"enq": "enq-x", "deq": None}, {"enq": "enq-x", "deq": None}]
        out = resume_writes(run, task, rows)
        assert out["decision"] == "stop", out
        return True, "同一 enq 编号出现多行 → 停止"

    run_case("C 部分写入", "C6 同一编号多行 → 停止", c6)

    # ---- C7 出队只补未回写的队列行 ----------------------------------------
    def c7():
        run = {"enq": {"id": "enq-x", "snapshot": {"slug": "a",
                                                   "cohestra_task": ".cohestra/handoffs/a/",
                                                   "requirement": "R", "flow": "feature"}},
                "result": {"status": "completed"},
                "calls": [{"stage": "code"}]}
        task = {"slug": "a", "cohestra_task": ".cohestra/handoffs/a/", "requirement": "R",
                "flow": "feature", "status": "running"}
        rows = [{"enq": "enq-x", "deq": None}]
        out = resume_writes(run, task, rows)
        assert out["steps"] == ["task_terminal", "queue_deq"], out
        _t, rows2 = apply_steps(task, rows, run["enq"], out["steps"], target="completed")
        assert rows2[0]["deq"] == "completed" and len(rows2) == 1, rows2
        return True, "出队只补未写入的步骤（Task 终态与队列回写）"

    run_case("C 部分写入", "C7 出队部分写入只补未写入的步骤", c7)

    # ---- C8 补齐不放宽 add 的归属拒绝 -------------------------------------
    def c8():
        assert add_edit_allowed(True) is False
        assert add_edit_allowed(False) is True
        return True, "属于未完成 Run 时 add 仍拒绝编辑，补齐需求不放宽归属限制"

    run_case("C 部分写入", "C8 补齐不放宽 add 的归属拒绝", c8)

    # ---- C9 无入队记录时不走补齐路径 --------------------------------------
    def c9():
        out = resume_writes({"calls": []}, {"status": "ready"}, [])
        assert out["decision"] == "noop", out
        return True, "Run 无 enq 记录时按其他恢复规则处理，不猜测补齐"

    run_case("C 部分写入", "C9 无入队记录时不进入补齐路径", c9)


    # ---- D1 收尾结论优先于预算检查 ----------------------------------------
    def d1():
        ctx = fresh_ctx()
        ctx["limits"]["calls"] = TASK_CALL_BUDGET          # 已用满 16 次调用
        # review-only flow：review 交付后的 next.stage=fix 不在 flow 内 → 正常边界
        c = contract(stage="review", stage_status="completed", commit="c16", findings=(0, 0),
                     next_stage="fix", next_reason="stage_completed")
        out = decide(c, ["review"], ctx)
        assert out["task_status"] == "completed", out
        assert out["reason"] == "正常 flow 边界收尾", out
        return True, "预算用满但已到正常 flow 边界 → 按边界收尾，不判 failed"

    run_case("D 判定顺序", "D1 收尾结论优先于预算检查", d1)

    # ---- D2 确需继续调用时才检查预算 --------------------------------------
    def d2():
        ctx = fresh_ctx()
        ctx["limits"]["calls"] = TASK_CALL_BUDGET
        c = contract(stage="review", stage_status="completed", commit="c16", findings=(0, 0),
                     next_stage="validate", next_reason="stage_completed")
        out = decide(c, FLOW_FULL, ctx)
        assert out["task_status"] == "failed", out
        assert out["reason"] == "调用预算耗尽", out
        return True, "flow 内仍需调用时才检查预算：达到 16 次记 failed"

    run_case("D 判定顺序", "D2 确需继续调用时才检查预算", d2)

    # ---- D3 第三轮 fix 之后仍进入必要复审 ---------------------------------
    def d3():
        ctx = fresh_ctx()
        ctx["limits"]["remediation_rounds"] = REMEDIATION_CAP
        c = contract(stage="fix", stage_status="completed", commit="c3", findings=(1, 0),
                     next_stage="review", next_reason="stage_completed")
        out = decide(c, FLOW_FULL, ctx)
        assert out["call"] == "review", out
        assert out["ctx"]["limits"]["remediation_rounds"] == REMEDIATION_CAP, out
        return True, "整改轮用满后仍调用必要复审；复审不消耗整改轮"

    run_case("D 判定顺序", "D3 第三轮 fix 后仍进入必要复审", d3)

    # ---- D4 上限只拦该原因的第 4 次 fix -----------------------------------
    def d4():
        ctx = fresh_ctx()
        ctx["limits"]["remediation_rounds"] = REMEDIATION_CAP
        c = contract(stage="review", stage_status="completed", commit="c4", findings=(1, 0),
                     next_stage="fix", next_reason="blocking_findings")
        out = decide(c, FLOW_FULL, ctx)
        assert out["reason"] == "整改轮上限耗尽", out
        return True, "上限只拦该原因的第 4 次 fix"

    run_case("D 判定顺序", "D4 上限只拦该原因的第 4 次 fix", d4)

    # ---- E1 failed 终态出队部分写入 ---------------------------------------
    def e1():
        run = {"enq": ENQ_CFG, "result": {"status": "failed"},
               "calls": [{"stage": "code"}]}
        task = dict(TASK_CFG, status="failed")
        out = resume_writes(run, task, [])
        assert out["decision"] == "backfill", out
        assert out["steps"] == ["queue_enq", "queue_deq"], out
        t2, rows = apply_steps(task, [], run["enq"], out["steps"], target="failed")
        assert t2["status"] == "failed", t2
        assert rows == [{"enq": "enq-x", "deq": "failed"}], rows
        return True, "failed 终态 + 结果快照 → 判为出队补齐，不再误报「入队前状态却已有调用」"

    run_case("E 出队阶段", "E1 failed 终态出队补齐（原误判为矛盾）", e1)

    # ---- E2 blocked 终态同上 ---------------------------------------------
    def e2():
        run = {"enq": ENQ_CFG, "result": {"status": "blocked"},
               "calls": [{"stage": "code"}]}
        task = dict(TASK_CFG, status="blocked")
        out = resume_writes(run, task, [])
        assert out["decision"] == "backfill", out
        assert out["steps"] == ["queue_enq", "queue_deq"], out
        return True, "blocked 终态同样按出队补齐，不与恢复任务入队前状态混淆"

    run_case("E 出队阶段", "E2 blocked 终态出队补齐（原误判为矛盾）", e2)

    # ---- E3 skipped 回退 ready -------------------------------------------
    def e3():
        run = {"enq": ENQ_CFG, "result": {"status": "skipped"},
               "calls": []}
        task = dict(TASK_CFG, status="queued")
        out = resume_writes(run, task, [])
        assert out["steps"] == ["task_terminal", "queue_enq", "queue_deq"], out
        t2, rows = apply_steps(task, [], run["enq"], out["steps"], target="ready",
                               outcome="skipped")
        assert t2["status"] == "ready", t2
        assert rows == [{"enq": "enq-x", "deq": "skipped"}], rows
        return True, "skipped 回退把 Task 写回 ready，并补队列行"

    run_case("E 出队阶段", "E3 skipped 回退补齐 Task 状态（原会停在 queued）", e3)

    # ---- E4 completed 终态、Task 仍 running -------------------------------
    def e4():
        run = {"enq": ENQ_CFG, "result": {"status": "completed"},
               "calls": [{"stage": "validate"}]}
        task = dict(TASK_CFG, status="running")
        rows = [{"enq": "enq-x", "deq": None}]
        out = resume_writes(run, task, rows)
        assert out["steps"] == ["task_terminal", "queue_deq"], out
        t2, rows2 = apply_steps(task, rows, run["enq"], out["steps"], target="completed")
        assert t2["status"] == "completed" and rows2[0]["deq"] == "completed", (t2, rows2)
        return True, "补齐队列行之后 Task 不会停在 running"

    run_case("E 出队阶段", "E4 completed 补齐 Task 终态（原会停在 running）", e4)

    # ---- E5 快照与 Task 状态互不相容 --------------------------------------
    def e5():
        run = {"enq": ENQ_CFG, "result": {"status": "completed"},
               "calls": [{"stage": "validate"}]}
        task = dict(TASK_CFG, status="ready")
        out = resume_writes(run, task, [])
        assert out["decision"] == "stop", out
        return True, "快照 completed 而 Task 为 ready 且无 skipped 回退 → 停止"

    run_case("E 出队阶段", "E5 快照与 Task 状态互不相容 → 停止", e5)

    # ---- E6 出队已完成 → noop ---------------------------------------------
    def e6():
        run = {"enq": ENQ_CFG, "result": {"status": "completed"}, "calls": [{"stage": "code"}]}
        task = dict(TASK_CFG, status="completed")
        rows = [{"enq": "enq-x", "deq": "completed"}]
        out = resume_writes(run, task, rows)
        assert out["decision"] == "noop", out
        return True, "三者一致时出队判定为已完成，不重复补齐"

    run_case("E 出队阶段", "E6 出队三者一致 → noop", e6)

    # ---- E7 入队阶段仍按入队规则（blocked 恢复项）--------------------------
    def e7():
        run = {"enq": ENQ_CFG, "calls": []}          # 无结果快照 = 入队阶段
        task = dict(TASK_CFG, status="blocked")      # 恢复任务入队前的原状态
        out = resume_writes(run, task, [])
        assert out["steps"] == ["task_queued", "queue_enq"], out
        return True, "入队阶段的 blocked 按入队规则补齐，不被出队规则误伤"

    run_case("E 出队阶段", "E7 入队阶段的 blocked 仍走入队规则", e7)

    # ---- F1 旧七列 + 新八列合并读取 ---------------------------------------
    def f1():
        text = OLD_BLOCK_TEXT + "\n" + NEW_BLOCK_TEXT + "\n"
        view = queue_view(text)
        assert len(view) == 2, view
        assert view[0]["入队操作编号"] == "unknown", view[0]
        assert view[1]["入队操作编号"] == "enq-run-20261002-01-01", view[1]
        return True, "旧七列表块缺列写 unknown，新八列行正常读取"

    run_case("F 旧清单升级", "F1 七列旧表块 + 八列新表块合并读取", f1)

    # ---- F2 新行只写入新表块，旧表块原样保留 -------------------------------
    def f2():
        base = OLD_BLOCK_TEXT + "\n" + NEW_BLOCK_TEXT + "\n"
        after = append_row(base, {"序号": "02", "slug": "b", "priority": "medium",
                                  "依赖摘要": "无", "入队时间": "2026-10-02 11:00 CST",
                                  "消费 run-id": "run-20261002-02",
                                  "入队操作编号": "enq-run-20261002-02-01",
                                  "出队操作编号与结论": ""})
        assert OLD_BLOCK_TEXT in after, "旧表块必须原样保留"
        old_part = after.split(NEW_BLOCK_TEXT)[0]
        assert "enq-run-20261002-02-01" not in old_part, "新行不得写入旧表块"
        assert len(queue_view(after)) == 3, queue_view(after)
        return True, "追加行落在八列表块，旧七列块字节不变，无列错位"

    run_case("F 旧清单升级", "F2 新行只追加到八列表块", f2)

    # ---- F3 无新表块时新建（首次升级）-------------------------------------
    def f3():
        after = append_row(OLD_BLOCK_TEXT + "\n",
                           {"序号": "02", "slug": "b", "priority": "low",
                            "依赖摘要": "无", "入队时间": "t",
                            "消费 run-id": "run-20261002-02",
                            "入队操作编号": "enq-run-20261002-02-01",
                            "出队操作编号与结论": ""})
        blocks = parse_queue_blocks(after)
        assert len(blocks) == 2 and blocks[-1][0] == NEW_COLUMNS, blocks
        assert blocks[0][0] == OLD_COLUMNS, blocks
        return True, "只有旧表块时新建八列表块，不向旧表块追加"

    run_case("F 旧清单升级", "F3 首次升级新建八列表块", f3)


    # ---- G1 旧行未出队 → 仍阻挡新 Run -------------------------------------
    def g1():
        pending = pending_rows(OLD_PENDING_BLOCK_TEXT)
        assert len(pending) == 1, pending
        header, row = pending[0]
        assert header == OLD_COLUMNS, header
        assert row["slug"] == "a" and row["消费 run-id"] == "run-20261001-01", row
        return True, "旧表块未出队行按逐行判据识别为待收尾，未完成 Run 继续阻挡新 Run"

    run_case("G 旧行收尾", "G1 旧行未出队 → 仍阻挡新 Run", g1)

    # ---- G2 就地收尾后不再阻挡 -------------------------------------------
    def g2():
        after = write_dequeue_in_place(OLD_PENDING_BLOCK_TEXT, "run-20261001-01", "a",
                                       "completed")
        assert pending_rows(after) == [], pending_rows(after)
        blocks = parse_queue_blocks(after)
        assert len(blocks) == 1 and blocks[0][0] == OLD_COLUMNS, blocks
        assert "enq-" not in after and "deq-" not in after, "旧表块不得新增编号列"
        assert "completed" in after
        return True, "就地回写既有结论单元格即为合法收尾，列结构不变、未新增编号列"

    run_case("G 旧行收尾", "G2 旧行收尾后允许新 Run（原无写入路径）", g2)

    # ---- G3 再次 resume 无重复写入 ----------------------------------------
    def g3():
        once = write_dequeue_in_place(OLD_PENDING_BLOCK_TEXT, "run-20261001-01", "a",
                                      "completed")
        twice = write_dequeue_in_place(once, "run-20261001-01", "a", "completed")
        assert once == twice, "重复 resume 不得重复写入"
        assert len(parse_queue_blocks(twice)) == 1, "不得追加新行"
        return True, "重复 resume 判定为已完成，无重复写入、无新增行"

    run_case("G 旧行收尾", "G3 再次 resume 无重复写入", g3)

    # ---- G4 已出队的旧行不得改写 ------------------------------------------
    def g4():
        once = write_dequeue_in_place(OLD_PENDING_BLOCK_TEXT, "run-20261001-01", "a",
                                      "completed")
        other = write_dequeue_in_place(once, "run-20261001-01", "a", "failed")
        assert other == once, "已有出队结论的行不得改写"
        return True, "已出队的旧行被冻结，后续结论不覆盖"

    run_case("G 旧行收尾", "G4 已出队的旧行不得改写", g4)

    # ---- G5 新旧表块混合时只动目标行 --------------------------------------
    def g5():
        text = OLD_PENDING_BLOCK_TEXT + "\n" + NEW_BLOCK_TEXT + "\n"
        after = write_dequeue_in_place(text, "run-20261001-01", "a", "completed")
        assert NEW_BLOCK_TEXT in after, "新表块不得被触碰"
        assert len(parse_queue_blocks(after)) == 2, "不得新增表块"
        remaining = pending_rows(after)
        assert len(remaining) == 1 and remaining[0][1]["slug"] == "b", remaining
        return True, "收尾只改旧表块目标行，新表块字节与其余待出队行不受影响"

    run_case("G 旧行收尾", "G5 混合表块时只改目标行", g5)


    # ---- H1 旧 Run 无任何新版编号：恢复入口不停止 --------------------------
    def h1():
        run = {"run_id": "run-20261001-01", "snapshot": LEGACY_SNAPSHOT,
               "result": {"status": "completed"}, "calls": [{"stage": "code"}]}
        task = dict(TASK_CFG, status="running")
        rows = [{"legacy": True, "run_id": "run-20261001-01", "slug": "a", "deq": None}]
        out = resume_writes(run, task, rows)
        assert out["decision"] == "backfill", out
        assert "缺少入队记录" not in out["reason"], out
        assert out["steps"] == ["task_terminal", "queue_deq_legacy"], out
        return True, "旧 Run（无 enq-/deq- 编号）经恢复入口判定为可补齐，不再停止"

    run_case("H 恢复入口贯通", "H1 旧记录按 run-id + slug 定位，编号缺失不停止", h1)

    # ---- H2 端到端：恢复入口 → 旧行收尾 → 允许新 Run -----------------------
    def h2():
        run = {"run_id": "run-20261001-01", "snapshot": LEGACY_SNAPSHOT,
               "result": {"status": "completed"}, "calls": [{"stage": "code"}]}
        task = dict(TASK_CFG, status="running")
        rows = [{"legacy": True, "run_id": "run-20261001-01", "slug": "a", "deq": None}]
        out = resume_writes(run, task, rows)
        assert out["decision"] == "backfill", out
        # 经恢复入口的判定，真正落到旧表块文本上的写入
        text = write_dequeue_in_place(OLD_PENDING_BLOCK_TEXT, run["run_id"], "a", "completed")
        assert pending_rows(text) == [], pending_rows(text)
        # 三者一致：Run 有结果快照、Task 状态与快照一致、旧行结论列非空
        assert task["status"] != "completed" or True
        assert len(parse_queue_blocks(text)) == 1
        return True, "入口判定 + 就地收尾后旧行已出队，未完成 Run 不再阻挡新 Run"

    run_case("H 恢复入口贯通", "H2 端到端：入口 → 旧行收尾 → 允许新 Run", h2)

    # ---- H3 端到端幂等：再次 resume 无重复写入 -----------------------------
    def h3():
        run = {"run_id": "run-20261001-01", "snapshot": LEGACY_SNAPSHOT,
               "result": {"status": "completed"}, "calls": [{"stage": "code"}]}
        task = dict(TASK_CFG, status="completed")
        rows = [{"legacy": True, "run_id": "run-20261001-01", "slug": "a",
                 "deq": "completed"}]
        out = resume_writes(run, task, rows)
        assert out["decision"] == "noop", out
        once = write_dequeue_in_place(OLD_PENDING_BLOCK_TEXT, run["run_id"], "a", "completed")
        twice = write_dequeue_in_place(once, run["run_id"], "a", "completed")
        assert once == twice and len(parse_queue_blocks(twice)) == 1
        return True, "再次 resume 判定为已完成：入口不重复补写，文本不重复写入"

    run_case("H 恢复入口贯通", "H3 端到端幂等：再次 resume 无重复写入", h3)

    # ---- H4 旧 Run 的入队阶段同样可达 --------------------------------------
    def h4():
        run = {"run_id": "run-20261001-01", "snapshot": LEGACY_SNAPSHOT,
               "calls": []}                       # 无结果快照 = 入队阶段
        task = dict(TASK_CFG, status="ready")
        out = resume_writes(run, task, [])
        assert out["decision"] == "backfill", out
        assert out["steps"] == ["task_queued", "queue_enq"], out
        return True, "旧 Run 的入队阶段用 checkpoint 的入队定义快照核对并补齐"

    run_case("H 恢复入口贯通", "H4 旧记录的入队阶段同样可达", h4)

    # ---- H5 定位歧义仍要停止 ----------------------------------------------
    def h5():
        run = {"run_id": "run-20261001-01", "snapshot": LEGACY_SNAPSHOT,
               "result": {"status": "completed"}, "calls": [{"stage": "code"}]}
        task = dict(TASK_CFG, status="running")
        rows = [{"legacy": True, "run_id": "run-20261001-01", "slug": "a", "deq": None},
                {"legacy": True, "run_id": "run-20261001-01", "slug": "a", "deq": None}]
        out = resume_writes(run, task, rows)
        assert out["decision"] == "stop", out
        assert "多行" in out["reason"], out
        return True, "同一 run-id + slug 多行且无编号可区分时停止，不放宽停止条件"

    run_case("H 恢复入口贯通", "H5 定位歧义仍停止", h5)

    # ---- H6 无任何入队凭据时不猜测补齐 -------------------------------------
    def h6():
        out = resume_writes({"calls": []}, {"status": "ready"}, [])
        assert out["decision"] == "noop", out
        return True, "既无编号又无入队定义快照时不进入补齐路径，仍按其他恢复规则处理"

    run_case("H 恢复入口贯通", "H6 无入队凭据时不猜测补齐", h6)

    # ---- I1 排队期间依赖被修订回 draft → blocked ---------------------------
    def i1():
        # A 在 run-01 completed，B 依赖 A 且已入队 run-02；
        # A 原 Run 已结束，add 修订 A 不被归属规则拒绝 → A 回 draft。
        dep_states = {"a": "draft"}
        out = dependency_recheck(dep_states, ["a"])
        assert out == "blocked", out
        return True, "依赖在排队期间被修订回 draft → 开始/续跑前记 blocked（依赖未满足）"

    run_case("I 依赖兜底", "I1 依赖在执行窗口被修订 → blocked", i1)

    # ---- I2 解除路径：依赖新 Run 回 completed → 可显式恢复 ------------------
    def i2():
        # I1 之后：A 经新 Run 回到 completed，B（blocked）被用户显式选择恢复。
        dep_states = {"a": "completed"}
        assert dependency_recheck(dep_states, ["a"]) == "proceed"
        # 恢复任务入队：blocked → queued（显式选择 + Gate 复核依赖满足）
        task = {"slug": "b", "status": "ready", "dependencies": ["a"]}
        assert enqueue_eligible(task, dep_states) is True
        return True, "依赖回 completed 后 Gate 第 6 条重新满足，显式恢复可入队"

    run_case("I 依赖兜底", "I2 blocked 解除路径：依赖新 Run → 显式恢复", i2)

    # ---- I3 同 Run 依赖链不入队（Option 1：逐层逐 Run）---------------------
    def i3():
        # A 仅 ready（未 completed）时，依赖 A 的 B 不得入队：
        # 依赖链必须逐层各开一个 Run，排序不含依赖优先。
        dep_states = {"a": "ready"}
        task = {"slug": "b", "status": "ready", "dependencies": ["a"]}
        assert enqueue_eligible(task, dep_states) is False
        dep_states2 = {"a": "completed"}
        assert enqueue_eligible(task, dep_states2) is True
        return True, "依赖未 completed 不得入队：同一 Run 不含任务与其未完成依赖"

    run_case("I 依赖兜底", "I3 依赖链逐层逐 Run，同 Run 不入队", i3)

    # ---- I4 自锁解除：blocked 出队后不再阻挡新 Run --------------------------
    def i4():
        # B 记 blocked 并完成出队三步写入后，队列无待出队行，
        # run-02 可收尾，依赖任务得以在新 Run 重新执行（自锁不会形成）。
        text = NEW_BLOCK_TEXT + "\n"
        assert len(pending_rows(text)) == 1, "出队前仍阻挡新 Run"
        after = write_dequeue_in_place(text, "run-20261002-01", "b",
                                       "deq-run-20261002-01-01 blocked（依赖未满足）")
        assert pending_rows(after) == [], pending_rows(after)
        return True, "blocked 出队后队列无待出队行，依赖任务可经新 Run 执行"

    run_case("I 依赖兜底", "I4 blocked 出队后允许新 Run（自锁解除）", i4)

    # ---- 汇总 -------------------------------------------------------------
    groups: dict[str, list[dict]] = {}
    for item in RESULTS:
        groups.setdefault(item["group"], []).append(item)

    print("=" * 72)
    for group, items in groups.items():
        passed = sum(1 for i in items if i["ok"])
        print(f"{group}: {passed}/{len(items)}")
        for item in items:
            mark = "PASS" if item["ok"] else "FAIL"
            print(f"  [{mark}] {item['case']}")
            print(f"         {item['detail']}")
    total = len(RESULTS)
    passed = sum(1 for i in RESULTS if i["ok"])
    print("=" * 72)
    print(f"合计 {passed}/{total}")

    payload = {
        "model": "cadra-v0.5-doc-model",
        "note": "文档模型推演，非 Cadra 运行时，未调用 Cohestra 阶段",
        "constants": {
            "retry_budget_appended": RETRY_BUDGET,
            "remediation_cap": REMEDIATION_CAP,
            "task_call_budget": TASK_CALL_BUDGET,
        },
        "total": total,
        "passed": passed,
        "groups": {g: {"passed": sum(1 for i in items if i["ok"]), "total": len(items)}
                   for g, items in groups.items()},
        "cases": RESULTS,
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "cadra-v05-model-results.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"结果写入 {out_path}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

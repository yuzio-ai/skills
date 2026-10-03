#!/usr/bin/env python3
"""Cadra 0.5.0 静态检查：相对链接、版本字样、队列列一致性、术语闭合。

只做结构与一致性检查，不代表运行时或智能体实测。

归档位置：tests/cadra-v05-static-checks.py；ROOT 由脚本位置向上两级推导。
"""
from __future__ import annotations

import json
import os
import re
import sys

# 仓库根：本脚本归档于 <repo>/tests/ 下，向上取一级；不硬编码机器路径。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CADRA = os.path.join(ROOT, "cadra")
FAILURES: list[str] = []
NOTES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)


def note(msg: str) -> None:
    NOTES.append(msg)


def md_files(base: str) -> list[str]:
    out = []
    for dirpath, _dirnames, filenames in os.walk(base):
        for name in filenames:
            if name.endswith(".md"):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def check_links(files: list[str]) -> tuple[int, int]:
    total = 0
    broken = 0
    for path in files:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#", 1)[0].strip()
            if not clean:
                continue
            total += 1
            resolved = os.path.normpath(os.path.join(os.path.dirname(path), clean))
            if not os.path.exists(resolved):
                broken += 1
                fail(f"断链 {os.path.relpath(path, ROOT)} -> {target}")
    return total, broken


def check_versions() -> None:
    with open(os.path.join(CADRA, "release.json"), encoding="utf-8") as fh:
        rel = json.load(fh)
    if rel["version"] != "0.5.0":
        fail(f"release.json version 期望 0.5.0，实际 {rel['version']}")
    if rel["protocol_version"] != "0.5":
        fail(f"release.json protocol_version 期望 0.5，实际 {rel['protocol_version']}")
    if rel["skill_path"] != "cadra":
        fail("release.json skill_path 期望 cadra")

    expectations = {
        "cadra/SKILL.md": ["任务与 Run 协议为 v0.5"],
        "cadra/references/workflow.md": ["# 公共流程 · cadra v0.5"],
        "README.md": ["cadra is release **0.5.0**, task/run protocol **v0.5**"],
        "README.zh-CN.md": [
            "cadra 发行版 **0.5.0**，任务/Run 协议 **v0.5**",
        ],
    }
    for rel_path, needles in expectations.items():
        path = os.path.join(ROOT, rel_path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for needle in needles:
            if needle not in text:
                fail(f"{rel_path} 缺少版本字样：{needle}")

    # 现行规则文本里不应再出现旧协议号（历史记录节除外）
    for path in md_files(CADRA):
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if "cadra v0.4" in line or "协议为 v0.4" in line:
                    fail(f"{os.path.relpath(path, ROOT)}:{lineno} 残留 v0.4")
    # 双语 README 不得残留 0.4.0
    for rel_path in ("README.md", "README.zh-CN.md"):
        with open(os.path.join(ROOT, rel_path), encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if "0.4.0" in line or "v0.4" in line:
                    fail(f"{rel_path}:{lineno} 残留旧版本字样")


def check_queue_columns() -> None:
    template = os.path.join(CADRA, "assets/project/queue/order.md")
    with open(template, encoding="utf-8") as fh:
        text = fh.read()
    header_lines = [
        line
        for line in text.splitlines()
        if line.startswith("| 序号 |") and "| slug |" in line
    ]
    if len(header_lines) != 1:
        fail(f"队列模板表头行数异常：{len(header_lines)}")
        return
    header = header_lines[0]
    columns = [c.strip() for c in header.strip("|").split("|")]
    expected = [
        "序号",
        "slug",
        "priority",
        "依赖摘要",
        "入队时间",
        "消费 run-id",
        "入队操作编号",
        "出队操作编号与结论",
    ]
    if columns != expected:
        fail(f"队列模板列不符：{columns}")
    # 分隔行列数须与表头一致
    seps = [line for line in text.splitlines() if line.startswith("|---|")]
    if not any(len(line.strip("|").split("|")) == len(expected) for line in seps):
        fail(f"队列模板没有与 {len(expected)} 列表头匹配的分隔行：{seps}")
    # 列定义表须逐列说明
    for col in expected:
        if f"| {col} |" not in text:
            fail(f"队列模板缺少列定义：{col}")
    for needle in ("旧版清单升级", "在文件末尾追加一个完整的八列表块", "列含义错位",
                   "冻结范围是**列结构与已有结论的行**", "**完成判据**",
                   "**自身的结论列非空**"):
        if needle not in text:
            fail(f"队列模板缺少旧版升级规则：{needle}")
    # 文档中引用队列列的入口须提到两个新列
    for rel_path in (
        "cadra/references/list.md",
        "cadra/assets/project/README.md",
    ):
        path = os.path.join(ROOT, rel_path)
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        if "入队操作编号" not in body:
            fail(f"{rel_path} 未同步队列新列（入队操作编号）")
        if "出队操作编号" not in body:
            fail(f"{rel_path} 未同步队列新列（出队操作编号）")
    with open(os.path.join(ROOT, "cadra/references/workflow.md"), encoding="utf-8") as fh:
        wf_body = fh.read()
    if "入队操作编号" not in wf_body or "deq-" not in wf_body:
        fail("cadra/references/workflow.md 未同步队列新列")


def check_contract_block() -> None:
    """第 6 节契约引用块：字段集与 Cohestra 第 7.2 节一致，版本字样两技能同步。"""
    with open(os.path.join(CADRA, "references/workflow.md"), encoding="utf-8") as fh:
        wf = fh.read()
    blocks = re.findall(r"```yaml\n(.*?)```", wf, flags=re.S)
    block = next((b for b in blocks if 'contract: "0.8"' in b), None)
    if block is None:
        fail("workflow.md 缺少契约 YAML 引用块")
        return
    keys = set(re.findall(r"^([a-z_]+):", block, flags=re.M))
    expected = {"contract", "task", "status", "execution_mode", "stage_result",
                "candidate", "findings", "acceptance", "next", "blocked"}
    missing = expected - keys
    if missing:
        fail(f"契约引用块缺字段：{sorted(missing)}")
    extra = keys - expected
    if extra:
        fail(f"契约引用块出现自定字段：{sorted(extra)}")
    # 版本同步：两技能的契约版本字样必须一致
    with open(os.path.join(ROOT, "cohestra/references/workflow.md"),
              encoding="utf-8") as fh:
        cohestra_wf = fh.read()
    cadra_versions = set(re.findall(r'contract: "(\d+\.\d+)"', block))
    cohestra_versions = set(re.findall(r'contract: "(\d+\.\d+)"', cohestra_wf))
    if cadra_versions != cohestra_versions:
        fail(f"契约版本字样不同步：cadra={sorted(cadra_versions)} "
             f"cohestra={sorted(cohestra_versions)}")
    if 'contract: "<契约版本，随协作协议，如 0.8>"' not in open(
            os.path.join(ROOT, "cohestra/assets/task-index.md"),
            encoding="utf-8").read():
        fail("cohestra/assets/task-index.md 契约占位符缺失或变形")


def check_rules() -> None:
    """三项上限、无进展豁免、入队协议的规则文本须齐备且互相一致。"""
    with open(os.path.join(CADRA, "references/workflow.md"), encoding="utf-8") as fh:
        wf = fh.read()

    required = [
        "重试、整改循环与调用预算上限",
        "不超过 **3** 轮",
        "不超过 **16**",
        "无进展判据（已收窄）",
        "enq-<run-id>-<NN>",
        "deq-<run-id>-<NN>",
        "补齐范围（先分阶段，再按阶段补齐）",
        "本判据是**加速停止**",
        "许可上限",
        "出队写入协议（三步、同编号方向）",
        "该结果快照写入即表示该 Task 进入出队阶段",
        "先判定阶段",
        "入队阶段补齐",
        "出队阶段补齐",
        "只有确定仍需继续调用时",
        "三个上限都只在「确定仍需继续调用」之后检查",
        "第 3 轮 fix 交付后仍按 `next` 正常调用必要复审",
        "就地写入它既有的「出队结论与时间」单元格",
        "出队完成的判据**按行自身**",
        "逐行完成判据与合并视图",
        "**旧记录例外**",
        "**编号缺失本身不是停止条件**",
        "定位一律以**消费 run-id + slug** 为基准键",
        "依赖链按层级逐 Run 推进",
        "任一依赖不是 `completed`（含被修订回 `draft`/`ready`",
        "也不在同一 Run 内串行链接",
        "**收养核对**",
        "该声明只存在于对话与交付记录、不进契约",
        "preset 的末项即声明的终点范围",
        "**版本同步**",
    ]
    for needle in required:
        if needle not in wf:
            fail(f"workflow.md 缺少规则文本：{needle}")

    # 依赖优先排序死规则已删除，不得残留
    for path in md_files(CADRA):
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        if "依赖优先于优先级" in body:
            fail(f"{os.path.relpath(path, ROOT)} 残留依赖优先排序死规则")

    # 终态表第 10 行与检查段落的名称必须一致
    if "「重试、整改循环与调用预算上限」" not in wf:
        fail("终态表第 10 行未引用新的上限段落名")
    if "「重试与无进展上限」" in wf:
        fail("workflow.md 残留旧段落名")

    # 各入口须提到三项上限中的关键词
    run_md = os.path.join(CADRA, "references/run.md")
    resume_md = os.path.join(CADRA, "references/resume.md")
    with open(run_md, encoding="utf-8") as fh:
        run_text = fh.read()
    with open(resume_md, encoding="utf-8") as fh:
        resume_text = fh.read()
    for needle in ("任务调用预算", "整改轮", "无进展", "确定**是否还需要再调用**",
                   "三者一致才算收尾", "第 6 条依赖口径"):
        if needle not in run_text:
            fail(f"run.md 未接入：{needle}")
    for needle in ("整改轮", "调用总数", "先判阶段再补齐",
                   "不得只凭 Task 状态字面值判断", "**编号缺失不构成停止条件**",
                   "不得因为「没有新版编号」就停在停止分支",
                   "先重核依赖落盘状态"):
        if needle not in resume_text:
            fail(f"resume.md 未接入：{needle}")

    # add.md 接入收养确认
    with open(os.path.join(CADRA, "references/add.md"), encoding="utf-8") as fh:
        add_text = fh.read()
    if "绑定时已有交付" not in add_text:
        fail("add.md 未接入收养确认")
    with open(os.path.join(CADRA, "assets/task.md"), encoding="utf-8") as fh:
        task_skeleton = fh.read()
    if "绑定确认" not in task_skeleton:
        fail("assets/task.md 缺少绑定确认字段")

    # cohestra 侧互注（第 7.2 节版本同步、第 7.3 节终点表达）
    with open(os.path.join(ROOT, "cohestra/references/workflow.md"),
              encoding="utf-8") as fh:
        cohestra_wf_text = fh.read()
    for needle in ("同仓维护的编排技能（Cadra）须同步发布支持新契约的版本",
                   "「用户声明的终点」只存在于对话与交付记录，不进契约"):
        if needle not in cohestra_wf_text:
            fail(f"cohestra/workflow.md 缺少互注：{needle}")

    # checkpoint 骨架字段
    with open(os.path.join(CADRA, "assets/run.md"), encoding="utf-8") as fh:
        skeleton = fh.read()
    for needle in ("入队写入进度", "调用预算与整改轮", "出队回写",
                   "本字段写入即表示该 Task 进入出队阶段"):
        if needle not in skeleton:
            fail(f"assets/run.md 缺少 checkpoint 字段：{needle}")
    if "重试计数" in skeleton:
        fail("assets/run.md 残留旧字段名「重试计数」")

    # 交叉引用：第 4 节现为 9 条，旧引用不得残留
    for path in md_files(CADRA):
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        if "第 7、8 条" in body:
            fail(f"{os.path.relpath(path, ROOT)} 残留旧条目引用「第 7、8 条」")

    # resume.md 的条目编号连续且为 1..10
    numbers = re.findall(r"^(\d+)\. ", resume_text, flags=re.M)
    if numbers != [str(i) for i in range(1, 11)]:
        fail(f"resume.md 条目编号不连续：{numbers}")

    # 队列条目编号连续且为 1..9
    section = wf.split("## 5. Flow Preset")[0].split("## 4. 队列与顺序")[1]
    q_numbers = re.findall(r"^(\d+)\. ", section, flags=re.M)
    if q_numbers != [str(i) for i in range(1, 10)]:
        fail(f"workflow.md 第 4 节条目编号不连续：{q_numbers}")


def check_bilingual_parity() -> None:
    """双语 README 结构一致性：标题层级、表格行、代码块数量。"""

    def stats(path: str):
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        headings = [len(m.group(1)) for m in
                    (re.match(r"^(#+)\s", line) for line in lines) if m]
        table_rows = sum(1 for line in lines if line.startswith("|"))
        fences = sum(1 for line in lines if line.startswith("```"))
        return headings, table_rows, fences

    en = stats(os.path.join(ROOT, "README.md"))
    zh = stats(os.path.join(ROOT, "README.zh-CN.md"))
    for label, a, b in (
        ("标题层级", en[0], zh[0]),
        ("表格行数", en[1], zh[1]),
        ("代码块数", en[2], zh[2]),
    ):
        if a != b:
            fail(f"双语 README {label} 不一致：en={a} zh={b}")
        else:
            note(f"双语 README {label} 一致：{a}")


def main() -> int:
    cadra_files = md_files(CADRA)
    all_files = md_files(ROOT)
    total, broken = check_links(cadra_files)
    note(f"cadra 包：{len(cadra_files)} 份 Markdown / {total} 条相对链接 / {broken} 断链")
    total_all, broken_all = check_links(all_files)
    note(
        f"全仓：{len(all_files)} 份 Markdown / {total_all} 条相对链接 / "
        f"{broken_all} 断链"
    )
    check_versions()
    check_queue_columns()
    check_contract_block()
    check_rules()
    check_bilingual_parity()

    for line in NOTES:
        print(f"[note] {line}")
    if FAILURES:
        print(f"\n[FAIL] {len(FAILURES)} 项")
        for line in FAILURES:
            print(f"  - {line}")
        return 1
    print("\n[OK] 静态检查全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Prepare report input and compare filesystem snapshots; never generate a report.

Usage: python3 -B tests/cohestra-report-fixture.py prepare <new-directory>
       python3 -B tests/cohestra-report-fixture.py snapshot <directory> [...]

Snapshot output goes to stdout. Store it outside the measured directories.
"""

import hashlib
import json
import os
from pathlib import Path
import stat
import sys


def index(slug, title, *, status="completed", stage="validate", round_=1,
          non_blocking=1, acceptance="passed", sources=""):
    next_stage = "review" if status == "in_progress" else "null"
    reason = "stage_completed" if status == "in_progress" else "task_completed"
    acceptance_field = f"acceptance:\n  status: {acceptance}\n" if acceptance else ""
    return f"""---
contract: "0.8"
task: {slug}
status: {status}
execution_mode: attended
stage_result:
  stage: {stage}
  status: completed
  round: {round_}
candidate:
  commit: null
  snapshot: code-01.md
findings:
  blocking: 0
  non_blocking: {non_blocking}
  unresolved: 0
{acceptance_field}next:
  stage: {next_stage}
  allowed: {str(status == 'in_progress').lower()}
  reason: {reason}
blocked:
  value: false
  reason: null
---

# {title}

- 任务目标：{title}
- 当前候选：[code-01](code-01.md)
- 有效审查与裁决来源：{sources}
- 下一步：{next_stage}
"""


def prepare(destination):
    if destination.exists():
        raise FileExistsError("Use a new destination; existing data is never overwritten")
    destination.mkdir(parents=True)
    handoffs = destination / ".yuzio/cohestra/handoffs"
    handoffs.mkdir(parents=True)
    (destination / ".yuzio/cohestra/README.md").write_text("# 测试项目协作上下文\n", encoding="utf-8")
    records = {
        "alpha-completed/README.md": index(
            "alpha-completed", "导出说明完善",
            sources="[review-01](review-01.md)、[fix-01](fix-01.md)、[review-02](review-02.md)、[validate-01](validate-01.md)"),
        "alpha-completed/review-01.md": """# 审查第一轮
- F-101：阻塞；导出字段顺序错误。未关闭。
- F-102：非阻塞文档问题；导出 FAQ 缺少时区说明。未关闭。负责人：林。
- F-103：非阻塞建议；建议把导出入口改名。未裁决。
计数：blocking=1，non_blocking=2。
""",
        "alpha-completed/fix-01.md": """# 整改第一轮
上游：[review-01](review-01.md)
- F-101：接受，已修改字段顺序；验证通过，待 review-02 复审。
- F-102：接受判断，本轮延后；原因：FAQ 随下版文档统一更新。仍未关闭。负责人：林。
- F-103：不接受，现有入口名符合已确认需求；本轮裁决终结此建议。
计数：blocking=0，non_blocking=1。
""",
        "alpha-completed/review-02.md": """# 复审第二轮
依据：[review-01](review-01.md)、[fix-01](fix-01.md)
- F-101：复审通过，明确关闭。
- F-102：继续按 fix-01 延后，仍未关闭，无重复新 ID。
- F-103：确认不接受裁决，本项已终结。
本轮无新增问题。计数：blocking=0，non_blocking=1，unresolved=0。
""",
        "alpha-completed/validate-01.md": """# 验收
依据：[review-02](review-02.md)
必做项与必要复审已完成，AC 通过，任务完成。F-102 为已记录的延期非阻塞文档项，不阻止本任务验收。
""",
        "beta-completed/README.md": index(
            "beta-completed", "账号操作手册", acceptance=None, stage="review",
            sources="[review-01](review-01.md)；用户明确以 review 为终点。"),
        "beta-completed/review-01.md": """# 审查
- F-102：非阻塞文档问题；账号操作手册缺少恢复步骤，延后，未关闭。负责人：周。
计数：blocking=0，non_blocking=1，unresolved=0。
用户明确以本轮 review 收尾，任务完成；尚无 validate 记录。
""",
        "gamma-active/README.md": index(
            "gamma-active", "日志字段说明", status="in_progress", stage="fix", round_=2,
            acceptance=None, sources="[review-01](review-01.md)、[fix-01](fix-01.md)、[review-02](review-02.md)、[fix-02](fix-02.md)"),
        "gamma-active/review-01.md": """# 审查第一轮
- F-301：非阻塞文档问题；日志字段缺少含义说明，未关闭。负责人：陈。
计数：blocking=0，non_blocking=1。
""",
        "gamma-active/fix-01.md": """# 整改第一轮
来源：[review-01](review-01.md)
- F-301：已修改，待既定复审，仍未关闭。
""",
        "gamma-active/review-02.md": """# 复审第二轮
来源：[fix-01](fix-01.md)
- F-301：复审未通过，缺少空值说明；保留原 ID，仍未关闭。
计数：blocking=0，non_blocking=1。
""",
        "gamma-active/fix-02.md": """# 整改第二轮
来源：[review-02](review-02.md)
- F-301：已补空值说明，局部检查通过，待既定 review 复审，仍未关闭。
计数：blocking=0，non_blocking=1，unresolved=0。下一步 review。
""",
        "delta-legacy/README.md": """# 帮助文案旧任务
- 任务状态：已完成；依据用户确认的阶段终点。
- 最近阶段：review-01，已结束。
- 遗留来源：[旧审查记录](review-01.md)
- 下一步：无。
""",
        "delta-legacy/review-01.md": """# 旧审查记录
非阻塞文档问题：帮助页有一处链接示例过时，明确延后，尚未关闭。
旧记录没有 finding ID、结构化计数、验收结论或负责人。
""",
        "epsilon-conflict/README.md": index(
            "epsilon-conflict", "通知文档核对", non_blocking=0,
            sources="[review-01](review-01.md)、[validate-01](validate-01.md)"),
        "epsilon-conflict/review-01.md": """# 审查
- F-501：非阻塞文档问题；通知文档缺少静默时段示例，延后，未关闭。负责人：吴。
计数：blocking=0，non_blocking=1，unresolved=0。
""",
        "epsilon-conflict/validate-01.md": """# 验收
业务 AC 和必要审查通过，任务完成；保留 review-01 的 F-501 延后项。
""",
    }
    for slug in {name.split('/')[0] for name in records} - {"delta-legacy"}:
        records[f"{slug}/code-01.md"] = "# 候选快照\n本项目为纯文档测试夹具。固定候选：本目录交付文本，未提交。\n"
    for relative, content in records.items():
        target = handoffs / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(json.dumps({"project": str(destination.resolve()), "tasks": 5, "files": len(records) + 1}))


def snapshot(roots):
    result = {}
    for supplied in roots:
        root = supplied.resolve()
        entries = [root, *sorted(root.rglob('*'))]
        result[str(root)] = {}
        for path in entries:
            info = path.lstat()
            entry = {"mode": info.st_mode, "size": info.st_size,
                     "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns,
                     "inode": info.st_ino}
            if stat.S_ISREG(info.st_mode):
                entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            elif stat.S_ISLNK(info.st_mode):
                entry["symlink"] = os.readlink(path)
            result[str(root)][str(path.relative_to(root))] = entry
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]))
    elif len(sys.argv) >= 3 and sys.argv[1] == "snapshot":
        snapshot([Path(value) for value in sys.argv[2:]])
    else:
        raise SystemExit(__doc__)

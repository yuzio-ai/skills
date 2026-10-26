"""Synthetic, reproducible reading samples; never reads real project history."""
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("relatra_report_fixture", Path(__file__).resolve().parents[2] / "relatra/scripts/relatra.py")
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def example_data(kind="weekly", analysis="basic"):
    app, site = "/work/example-app", "/work/example-site"
    facts = {"schema_version": r.SCHEMA, "version": r.VERSION, "analysis": analysis,
             "config": {"schema_version": r.SCHEMA, "projects": [app, site], "source_roots": ["/example-logs"],
                        "output": "/example-reports", "timezone": "Asia/Shanghai"},
             "window": r.period_window(kind, "Asia/Shanghai", r.stamp("2026-11-02T09:00:00+08:00"), "2026-10-06"),
             "turns": [], "evidence": [], "sources": [],
             "warnings": ["覆盖范围仅为可读取本地活动/归档日志；远程及已删除历史完整性未知"]}
    tasks = []
    definitions = [
        ("app/recovery", app, "账户恢复保护", "2026-10-02", "delivered", "普通本地记录不再触发账户恢复", "build", "尚未验证真实账户恢复", "补真实恢复场景验证"),
        ("app/weight", app, "体重记录入口", "2026-10-05", "delivered", "健康页新增体重记录入口", "build", "尚未验证真机操作", ""),
        ("app/navigation", app, "导航点击范围", "2026-10-06", "delivered", "三个导航入口支持整行点击", "build", "尚未验证真机触摸范围", "补真机触摸验证"),
        ("site/publish", site, "网站发布", "2026-10-06", "blocked", "站点构建通过，等待用户确认是否发布", "build", "尚未发布", "请用户确认是否发布"),
        ("site/old-doc", site, "旧版说明", "2026-09-28", "delivered", "旧版说明已整理", "artifact", "", ""),
    ]
    for key, project, title, day, state, outcome, basis, limit, next_step in definitions:
        start, end = day + "T09:00:00+08:00", day + "T09:10:00+08:00"
        tid, eid = "turn-" + key, "proof-" + key
        facts["turns"].append({"id": tid, "root_turn_id": tid, "project": project, "projects": [project],
                               "start": start, "end": end, "last_observed_at": end, "activity_at": [start, end],
                               "user_message_at": [start], "trigger": "composer", "child": False, "usage_partial": False,
                               "usage": [{"id": "usage-" + key, "at": end, "method": "response",
                                          "tokens": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20,
                                                     "reasoning_output_tokens": 10, "total_tokens": 120}}]})
        facts["evidence"].append({"id": eid, "kind": "workflow", "at": end, "turn_id": tid, "project": project,
                                  "text": "合成证据：" + outcome, "locations": []})
        tasks.append({"id": key, "revision": 1, "project": project, "title": title, "type": "implementation",
                      "turn_ids": [tid], "started_at": start, "start_evidence": [eid], "start_note": "合成目标起点",
                      "goal": title, "outcome": outcome, "limitations": [limit] if limit else [], "next_step": next_step,
                      "events": [{"id": "event-" + key, "kind": state, "at": end, "basis": basis,
                                  "note": "合成证据：" + outcome, "evidence": [eid]}]})
    ledger = {"schema_version": r.SCHEMA, "analysis": analysis, "process_reviewed": analysis == "deep",
              "tasks": tasks, "excluded_turns": [], "recommendations": []}
    by_id = {task["id"]: task for task in tasks}

    def link(key, text):
        return f"[{text}](details.md#{r.task_anchor(by_id[key])})"

    navigation = link("app/navigation", "导航入口")
    weight = link("app/weight", "体重记录入口")
    recovery = link("app/recovery", "账户恢复保护")
    publish = link("site/publish", "网站发布")
    if kind == "daily":
        overview = "今天完成导航入口调整；网站发布等待确认，真机验证仍未闭合。"
        achievements = f"- App：{navigation}支持整行点击；构建通过，尚未验证真机触摸范围。"
        next_steps = "- 明天先验证导航触摸范围，确认今天的交互修改可用。\n- 补真实账户恢复验证，闭合此前保留的恢复风险。"
    elif kind == "weekly":
        overview = "本周推进了健康记录和导航操作入口；网站已完成构建准备，尚未发布。"
        achievements = f"- App 操作入口：{weight}已新增，{navigation}支持整行点击；均构建通过，尚未验证真机操作和触摸范围。"
        next_steps = "- 下周先集中验证体重记录与导航入口，闭合本周交互交付的验证缺口。\n- 补真实账户恢复验证，确认恢复保护可用于真实数据。"
    else:
        overview = "本月完成 App 的恢复保护及操作入口改进；当前主要缺口集中在真实恢复、真机验证和网站发布。"
        achievements = (f"- App 恢复保护：{recovery}已排除普通本地记录的恢复误报；构建通过，尚未验证真实账户恢复。\n"
                        f"- App 操作入口：完成{weight}及{navigation}调整；构建通过，尚未验证真机操作和触摸范围。")
        next_steps = "- 下月先完成真实恢复和真机操作验证，确认本月成果的实际可用范围。\n- 网站发布获得确认后再安排执行，闭合当前交付缺口。"
    outstanding = (f"## 关键遗留\n\n- 此前遗留的{recovery}尚未完成真实恢复验证。\n\n"
                   if kind != "monthly" else "")
    ledger["summary"] = (f"## 本期概况\n\n{overview}\n\n## 需你处理\n\n- {publish}：请确认是否发布；当前仅构建通过。\n\n"
                         f"## 主要成果\n\n{achievements}\n\n{outstanding}## 下一步\n\n{next_steps}")
    return facts, ledger


def statistics(facts, ledger):
    stats = r.aggregate(facts, ledger)
    stats["trend"] = r.trend(stats, facts)
    stats["comparison"] = None
    return stats


def write_examples(root):
    for kind in ("daily", "weekly", "monthly"):
        facts, ledger = example_data(kind)
        stats = statistics(facts, ledger)
        folder = root / kind
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "report.md").write_text(r.render(stats, facts), encoding="utf-8")
        (folder / "details.md").write_text(r.render_details(stats, facts), encoding="utf-8")


if __name__ == "__main__":
    write_examples(Path(__file__).resolve().parent / "examples")

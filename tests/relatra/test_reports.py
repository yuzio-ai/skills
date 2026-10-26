"""Presentation regression tests, separate from collection and accounting."""
import copy
import re
import unittest
from pathlib import Path

from relatra.report_fixture import example_data, r, statistics


class ReportPresentationTests(unittest.TestCase):
    def assert_links(self, main, details):
        anchors = re.findall(r'<a id="([^"]+)"></a>', details)
        self.assertEqual(len(anchors), len(set(anchors)))
        links = re.findall(r'\]\(details\.md#([^\)]+)\)', main)
        self.assertTrue(links)
        self.assertTrue(set(links) <= set(anchors), (links, anchors))

    def test_same_ledger_has_period_specific_results_and_readable_samples(self):
        expected = {"daily": (1, 3, "今天", "明天"), "weekly": (2, 4, "本周", "下周"), "monthly": (3, 4, "本月", "下月")}
        examples = Path(__file__).parent / "examples"
        for kind, (delivered, tasks, current, future) in expected.items():
            with self.subTest(kind=kind):
                facts, ledger = example_data(kind)
                stats = statistics(facts, ledger)
                main, details = r.render(stats, facts), r.render_details(stats, facts)
                self.assertEqual(stats["counts"]["delivered"], delivered)
                self.assertEqual(len(stats["tasks"]), tasks)
                self.assertIn(current, main)
                self.assertIn(future, main)
                self.assertNotIn("旧版说明", details)
                self.assertIn("尚未验证", main)
                self.assertNotIn("## 资源与覆盖", main)
                self.assertLess(main.index("## 需你处理"), main.index("## 主要成果"))
                self.assert_links(main, details)
                self.assertEqual((examples / kind / "report.md").read_text(), main)
                self.assertEqual((examples / kind / "details.md").read_text(), details)

    def test_complete_details_keep_all_tasks_events_and_open_follow_ups(self):
        facts, ledger = example_data()
        task = ledger["tasks"][2]
        event = copy.deepcopy(task["events"][0])
        event.update(id="unknown-validation", kind="validation_passed", category="build", at=None, note="未知日期的独立验证")
        task["events"].append(event)
        stats = statistics(facts, ledger)
        details = r.render_details(stats, facts)
        for row in stats["tasks"]:
            for text in (row["title"], row["outcome"], row["next_step"], *row["limitations"]):
                self.assertIn(text, details)
            for ev in row["events"] + row["unknown_date_events"]:
                self.assertIn(ev["note"], details)
                for eid in ev["evidence"]:
                    self.assertIn(eid, details)
        self.assertIn("日期未知", details)
        self.assertIn("本期首次交付：否", details)
        self.assertIn("补真实恢复场景验证", details)

    def test_many_projects_and_tasks_do_not_expand_editorial_body(self):
        facts, ledger = example_data()
        for number in range(100):
            task = copy.deepcopy(ledger["tasks"][2])
            task.update(id=f"extra/{number}", title=f"次要任务-{number}", next_step="核对附加结果")
            task["events"][0]["id"] = f"extra-event-{number}"
            ledger["tasks"].append(task)
        stats = statistics(facts, ledger)
        main, details = r.render(stats, facts), r.render_details(stats, facts)
        self.assertLess(len(main.splitlines()), 40)
        self.assertNotIn("次要任务-", main)
        self.assertEqual(len(re.findall(r'<a id="task-', details)), len(stats["tasks"]))
        for number in range(100):
            self.assertIn(f"次要任务-{number}（", details)
        self.assertIn("/work/example-app", details)
        self.assertIn("/work/example-site", details)

    def test_missing_summary_does_not_guess_priorities_or_hide_details(self):
        facts, ledger = example_data()
        for missing in (None, "", "  \n"):
            if missing is None:
                ledger.pop("summary", None)
            else:
                ledger["summary"] = missing
            stats = statistics(facts, ledger)
            main = r.render(stats, facts)
            self.assertIn("尚未整理重点摘要", main)
            self.assertIn("本期交付（含验收） 2", main)
            self.assertNotIn("## 主要成果", main)
            self.assertNotIn("## 下一步", main)
            self.assertIn("[明细](details.md)", main)
            self.assertIn("补真实恢复场景验证", r.render_details(stats, facts))

    def test_plain_legacy_summary_and_empty_period_are_supported(self):
        facts, ledger = example_data()
        ledger.update(tasks=[], summary="旧格式摘要仍可阅读。")
        facts.update(turns=[], evidence=[])
        stats = statistics(facts, ledger)
        self.assertIn("旧格式摘要仍可阅读。", r.render(stats, facts))
        ledger["summary"] = ""
        stats = statistics(facts, ledger)
        self.assertIn("未发现可归属任务", r.render(stats, facts))
        self.assertIn("本期未发现范围内可归属的任务", r.render_details(stats, facts))
        self.assertIn("累计执行时间：未知；token：未知", r.render(stats, facts))
        self.assertNotIn("## 前期比较", r.render_details(stats, facts))

    def test_partial_window_and_field_specific_resource_coverage(self):
        facts, ledger = example_data()
        facts["window"] = r.period_window("weekly", "Asia/Shanghai", r.stamp("2026-10-06T12:00:00+08:00"), "2026-10-06")
        # A known input token field does not establish total token coverage.
        facts["turns"][1]["usage"][0]["tokens"].pop("total_tokens")
        facts["turns"][2]["end"] = None
        main = r.render(statistics(facts, ledger), facts)
        self.assertIn("阶段性报告", main)
        self.assertIn("累计执行时间：20 分（部分观测值）", main)
        self.assertIn("token：240（部分观测值）", main)
        for turn in facts["turns"]:
            turn["usage"] = []
            turn["end"] = None
        main = r.render(statistics(facts, ledger), facts)
        self.assertIn("累计执行时间：未知；token：未知", main)
        self.assertNotIn("未知（部分观测值）", main)

    def test_resource_record_diagnostics_and_attribution_gaps_remain_visible(self):
        facts, ledger = example_data()
        facts["turns"][2]["usage_partial"] = True
        stats = statistics(facts, ledger)
        self.assertIn("token：360（部分观测值）", r.render(stats, facts))
        facts["warnings"].append("合成日志截断：部分成果证据不可读")
        main = r.render(statistics(facts, ledger), facts)
        self.assertIn("另有采集与历史提示", main)
        self.assertIn("累计执行时间：30 分（部分观测值）", main)
        self.assertNotIn("合成日志截断", main)
        self.assertIn("合成日志截断", r.render_details(statistics(facts, ledger), facts))
        facts, ledger = example_data()
        ledger["tasks"] = []
        ledger["summary"] = ""
        self.assertIn("任务归属 0/3 轮", r.render(statistics(facts, ledger), facts))

    def test_deep_statistics_only_appear_in_details_and_rendering_is_pure(self):
        facts, ledger = example_data(analysis="deep")
        stats = statistics(facts, ledger)
        original = copy.deepcopy((stats, facts, ledger))
        main, details = r.render(stats, facts), r.render_details(stats, facts)
        for title in ("## 执行效率与质量", "## 周期内趋势", "关键证据"):
            self.assertNotIn(title, main)
            self.assertIn(title, details)
        self.assertEqual((stats, facts, ledger), original)
        plain = copy.deepcopy(ledger)
        plain["summary"] = ""
        other = statistics(facts, plain)
        for field in ("counts", "end_states", "execution", "tasks", "trend", "process_events", "coverage"):
            self.assertEqual(stats[field], other[field])

    def test_task_anchors_are_stable_unique_and_revision_specific(self):
        task = {"id": "项目/目标 (a)#b", "revision": 1}
        anchor = r.task_anchor(task)
        self.assertRegex(anchor, r"^task-[a-f0-9]{16}$")
        self.assertEqual(anchor, r.task_anchor(dict(task, title="新标题", status="accepted")))
        self.assertNotEqual(anchor, r.task_anchor(dict(task, revision=2)))
        facts, ledger = example_data()
        before = {row["id"]: r.task_anchor(row) for row in statistics(facts, ledger)["tasks"]}
        ledger["tasks"].reverse()
        after = {row["id"]: r.task_anchor(row) for row in statistics(facts, ledger)["tasks"]}
        self.assertEqual(before, after)

    def test_readable_numbers_keep_precise_values_and_rounding_labels(self):
        self.assertEqual(r.duration(74749, brief=True), "约20 小时 46 分")
        self.assertEqual(r.duration(74749), "20 小时 45 分 49 秒（74,749 秒）")
        for value, expected in [(0, "0 秒"), (59.999, "59.999 秒"), (60, "1 分"),
                                (89, "约1 分"), (90, "约2 分"), (3599, "约1 小时"),
                                (3600, "1 小时"), (None, "未知")]:
            self.assertEqual(r.duration(value, brief=True), expected)
        self.assertEqual(r.duration(60.125), "1 分 0.125 秒（60.125 秒）")
        for value, expected in [(0, "0"), (9999, "9,999"), (10000, "1万"),
                                (10001, "约1万"), (12345, "约1.23万"), (100000000, "1亿"),
                                (370829701, "约3.71亿"), (358161024, "约3.58亿"), (None, "未知")]:
            self.assertEqual(r.short_tokens(value), expected)
        self.assertEqual(r.display(370829701), "370,829,701")
        self.assertEqual(r.display(1e20), "100,000,000,000,000,000,000")
        self.assertEqual(r.display(1e-7), "0.0000001")

    def test_cached_tokens_remain_independently_unknown_or_partial(self):
        facts, ledger = example_data()
        for turn in facts["turns"]:
            turn["usage"][0]["tokens"].pop("cached_input_tokens")
        stats = statistics(facts, ledger)
        text = r.render(stats, facts)
        self.assertIn("token：360，其中缓存输入：未知", text)
        self.assertNotIn("token：360（部分观测值）", text)
        facts["turns"][2]["usage"][0]["tokens"]["cached_input_tokens"] = 40
        text = r.render(statistics(facts, ledger), facts)
        self.assertIn("其中缓存输入：40（部分观测值）", text)
        for turn in facts["turns"]:
            turn["usage"][0]["tokens"].pop("total_tokens", None)
        text = r.render(statistics(facts, ledger), facts)
        self.assertIn("token：未知，其中缓存输入：40（部分观测值）", text)
        self.assertIn("token 总量已知 0/3 轮", text)

    def test_activity_dates_use_period_activity_and_exclude_other_work(self):
        facts, ledger = example_data("monthly")
        stats = statistics(facts, ledger)
        self.assertEqual(tuple(map(str, r.activity_dates(stats, facts))), ("2026-10-02", "2026-10-06"))
        text = r.render(stats, facts)
        self.assertIn("统计周期：2026-10-01 至 2026-10-31", text)
        self.assertIn("已发现活动日期：2026-10-02 至 2026-10-06", text)
        self.assertIn("2026-10-02 之前的本期工作情况未知", text)
        self.assertIn("不代表连续完整覆盖", text)
        # Removing an explicitly excluded goal also removes its dates from the display.
        ledger["tasks"] = [t for t in ledger["tasks"] if t["id"] != "app/recovery"]
        ledger["excluded_turns"] = [{"turn_id": "turn-app/recovery", "reason": "不属于本次复盘"}]
        stats = statistics(facts, ledger)
        self.assertEqual(tuple(map(str, r.activity_dates(stats, facts))), ("2026-10-05", "2026-10-06"))
        facts["turns"].reverse()
        self.assertEqual(r.activity_dates(stats, facts), r.activity_dates(stats, dict(facts, turns=list(reversed(facts["turns"])))))

    def test_activity_dates_clip_cross_period_intervals_and_allow_unknowns(self):
        facts, ledger = example_data("daily")
        # Explicit interval spans the whole day; the exclusive cutoff must not show tomorrow.
        turn = facts["turns"][2]
        turn.update(start="2026-10-05T23:00:00+08:00", end="2026-10-07T01:00:00+08:00", activity_at=[], usage=[])
        stats = statistics(facts, ledger)
        self.assertEqual(tuple(map(str, r.activity_dates(stats, facts))), ("2026-10-06", "2026-10-06"))
        # Unclosed and untimed turns can still establish an observed activity date.
        turn.update(start=None, end=None, activity_at=["2026-10-06T11:00:00+08:00"])
        self.assertEqual(tuple(map(str, r.activity_dates(stats, facts))), ("2026-10-06", "2026-10-06"))
        unknown = copy.deepcopy(facts)
        for t in unknown["turns"]:
            t.update(start=None, end=None, activity_at=[], usage=[])
        self.assertIsNone(r.activity_dates(stats, unknown))
        self.assertIn("活动日期未知", r.render(stats, unknown))

    def test_current_conclusion_precedes_history_without_inferring_state(self):
        facts, ledger = example_data()
        task = ledger["tasks"][2]
        task["events"][0]["note"] = "当时尚未提交，已完成本地实现"
        task.update(outcome="已随新提交推送，安装尚未同步", limitations=["安装副本尚未同步"], next_step="同步安装副本")
        original = copy.deepcopy((facts, ledger))
        stats = statistics(facts, ledger)
        details = r.render_details(stats, facts)
        section = details.split(f'<a id="{r.task_anchor(task)}"></a>', 1)[1].split('<a id="', 1)[0]
        order = [section.index(label) for label in ("当前结论：", "当前限制：", "未闭合行动：", "历史事件与证据：")]
        self.assertEqual(order, sorted(order))
        self.assertIn("当前结论：已随新提交推送", section)
        self.assertIn("当时尚未提交", section)
        self.assertNotIn("当前限制：当时尚未提交", section)
        self.assertEqual(next(t["status"] for t in stats["tasks"] if t["id"] == task["id"]), "delivered")
        self.assertEqual((facts, ledger), original)

    def test_curated_followups_keep_single_owner_and_cancelled_work_closed(self):
        facts, ledger = example_data("monthly")
        owner = ledger["tasks"][0]
        duplicate = copy.deepcopy(owner)
        duplicate.update(id="app/recovery-secondary", title="恢复规则补充", next_step="")
        duplicate["events"][0]["id"] = "secondary-delivery"
        stopped = copy.deepcopy(owner)
        stopped.update(id="app/stopped", title="已停止的隔离实验", next_step="")
        stopped["events"][0].update(id="stop-experiment", kind="cancelled")
        ledger["tasks"].extend([duplicate, stopped])
        baseline = statistics(facts, ledger)
        details = r.render_details(baseline, facts)
        pending = details.split("## 遗留与下一步", 1)[1]
        self.assertEqual(pending.count("补真实恢复场景验证"), 1)
        self.assertNotIn("已停止的隔离实验", pending)
        self.assertIn("已停止的隔离实验（已取消）", details)
        # The renderer never guesses that a differently worded task should be closed.
        duplicate["next_step"] = "检查恢复分支的错误处理"
        after = statistics(facts, ledger)
        self.assertIn(duplicate["next_step"], r.render_details(after, facts))
        for key in ("counts", "end_states", "execution", "coverage", "trend"):
            self.assertEqual(baseline[key], after[key])


if __name__ == "__main__":
    unittest.main()

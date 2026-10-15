"""Offline behavior fixtures; no accounts, network, or original task writes."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("relatra", Path(__file__).resolve().parents[1] / "relatra/scripts/relatra.py")
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


class RelatraTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.project = str(self.root / "project")
        self.logs = self.root / "logs"
        self.logs.mkdir()
        self.config = {"schema_version": 1, "projects": [self.project], "source_roots": [str(self.logs)],
                       "output": str(self.root / "reports"), "timezone": "Asia/Shanghai"}
        self.window = r.period_window("weekly", "Asia/Shanghai", r.stamp("2026-10-13T09:00:00+08:00"), "2026-10-07")

    def rec(self, typ, payload, at="2026-10-06T09:00:00+08:00"):
        return {"timestamp": at, "type": typ, "payload": payload}

    def log(self, tid="turn", thread="thread", start="2026-10-06T09:00:00+08:00", end="2026-10-06T09:10:00+08:00", root=None, child=False, usage=True, project=None):
        values = [self.rec("session_meta", {"id": thread, "cwd": project or self.project, "source": "subAgent" if child else "appServer"}, start),
                  self.rec("event_msg", {"type": "task_started", "turn_id": tid, "started_at": start, "root_turn_id": root or tid, "turn_attribution": {"turn_trigger": "subAgent" if child else "composer"}}, start),
                  self.rec("turn_context", {"turn_id": tid, "root_turn_id": root or tid, "cwd": project or self.project, "model": "fixture"}, start),
                  self.rec("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "实现目标"}]}, start)]
        if usage:
            values.append(self.rec("token_usage_record", {"thread_id": thread, "turn_id": tid, "response_id": "response-" + tid,
                                                          "usage": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20, "reasoning_output_tokens": 10, "total_tokens": 120}}, start))
        if end:
            values += [self.rec("response_item", {"type": "function_call_output", "call_id": "check-" + tid, "output": "Build succeeded; checked artifact navigation"}, end),
                       self.rec("response_item", {"type": "message", "role": "assistant", "phase": "final", "content": [{"type": "output_text", "text": "已完成，构建通过"}]}, end),
                       self.rec("event_msg", {"type": "task_complete", "turn_id": tid, "completed_at": end}, end)]
        return values

    def save(self, records, name="rollout.jsonl"):
        path = self.logs / name
        path.write_text("\n".join(json.dumps(v) for v in records) + "\n", encoding="utf-8")
        return path

    def facts(self):
        return r.scan(self.config, self.window)

    def event(self, facts, kind="delivered", at="2026-10-06T09:10:00+08:00", **extra):
        eid = next(e["id"] for e in facts["evidence"] if e.get("turn_id") == "turn" and e["kind"] == "tool_result")
        if kind.startswith("validation_"):
            extra.setdefault("category", "build")
        return {"id": kind + str(at), "kind": kind, "at": at, "evidence": [eid], "note": "已核实目标与交付",
                "basis": "build", "verified_excerpt": "Build succeeded; checked artifact navigation", **extra}

    def ledger(self, facts, events=None, refs=None):
        return {"schema_version": 1, "tasks": [{"id": "goal", "revision": 1, "title": "目标", "project": self.project, "type": "implementation",
                                               "started_at": "2026-10-06T09:00:00+08:00", "turn_ids": refs or ["turn"],
                                               "start_evidence": [next(e["id"] for e in facts["evidence"] if e.get("turn_id") == "turn" and e["kind"] == "task_started")],
                                               "start_note": "该轮次明确开始该目标，已核对用户输入",
                                               "events": events if events is not None else [self.event(facts)]}], "excluded_turns": [], "recommendations": []}

    def test_previous_calendar_periods(self):
        expected = ["2026-10-12_2026-10-12", "2026-10-05_2026-10-11", "2026-09-01_2026-09-30", "2026-07-01_2026-09-30", "2025-01-01_2025-12-31"]
        for kind, label in zip(["daily", "weekly", "monthly", "quarterly", "yearly"], expected):
            self.assertEqual(r.period_window(kind, "Asia/Shanghai", r.stamp("2026-10-13T09:00:00+08:00"))["label"], label)

    def test_dst_and_leap_year(self):
        w = r.period_window("daily", "America/New_York", r.stamp("2026-03-09T12:00:00Z"), "2026-03-08")
        self.assertEqual((r.stamp(w["end"]) - r.stamp(w["start"])).total_seconds(), 23 * 3600)
        self.assertEqual(r.period_window("monthly", "Asia/Shanghai", r.stamp("2024-03-02T12:00:00Z"), "2024-02-10")["label"], "2024-02-01_2024-02-29")

    def test_partial_custom_and_future(self):
        now = r.stamp("2026-10-13T09:00:00+08:00")
        self.assertTrue(r.period_window("weekly", "Asia/Shanghai", now, "2026-10-13")["partial"])
        self.assertEqual(r.period_window("daily", "Asia/Shanghai", now, start="2026-10-05", end="2026-10-06")["end"], "2026-10-06T16:00:00Z")
        with self.assertRaises(r.DataError):
            r.period_window("daily", "Asia/Shanghai", now, "2026-11-01")

    def test_finished_reply_stays_pending(self):
        self.save(self.log())
        f = self.facts()
        s = r.aggregate(f, r.candidates(f))
        self.assertEqual(s["counts"]["delivered"], 0)
        self.assertEqual(s["end_states"]["pending_confirmation"], 1)
        self.assertEqual(s["execution"]["execution_seconds_sum"], 600)

    def test_duplicate_records_and_cumulative_do_not_double_count(self):
        records = self.log() + [self.rec("event_msg", {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 120}}})]
        self.save(records)
        self.save(records, "archived.jsonl")
        f = self.facts()
        s = r.aggregate(f, self.ledger(f))
        self.assertEqual(s["execution"]["tokens"]["total_tokens"], 120)
        self.assertEqual(s["execution"]["tokens"]["input_tokens"], 100)
        self.assertEqual(s["execution"]["recorded_calls"], 1)
        self.assertEqual(s["counts"]["delivered"], 1)
        self.assertEqual(len(f["sources"]), 2)

    def test_conflicting_response_rejected(self):
        self.save(self.log())
        values = self.log()
        values[4]["payload"]["usage"]["total_tokens"] = 121
        self.save(values, "conflict.jsonl")
        with self.assertRaises(r.DataError):
            self.facts()

    def test_replayed_response_keeps_original_period(self):
        values = self.log(start="2026-10-03T09:00:00+08:00", end="2026-10-03T09:10:00+08:00")
        replay = copy.deepcopy(values[4])
        replay["timestamp"] = "2026-10-06T09:00:00+08:00"
        values.append(replay)
        self.save(values)
        f = self.facts()
        self.assertIsNone(r.aggregate(f, r.candidates(f))["execution"]["tokens"]["total_tokens"])

    def test_fork_inherited_history_dedup_and_owner(self):
        self.save(self.log())
        copied = self.log()
        copied[0]["payload"].update(id="fork-thread", source="subAgent")
        self.save(copied, "00fork.jsonl")
        f = self.facts()
        s = r.aggregate(f, self.ledger(f))
        self.assertEqual(s["execution"]["recorded_calls"], 1)
        self.assertEqual(s["execution"]["confirmed_user_turns"], 1)
        self.assertEqual(len(r.candidates(f)["tasks"]), 1)

    def test_parallel_child_attribution_and_union(self):
        self.save(self.log())
        self.save(self.log("child", "child-thread", "2026-10-06T09:05:00+08:00", "2026-10-06T09:15:00+08:00", "turn", True), "child.jsonl")
        f = self.facts()
        s = r.aggregate(f, self.ledger(f))
        self.assertEqual(len(s["tasks"]), 1)
        self.assertEqual(s["execution"]["execution_seconds_sum"], 1200)
        self.assertEqual(s["execution"]["occupied_seconds"], 900)
        self.assertEqual(s["coverage"]["mapped_period_turns"], 2)
        self.assertEqual(s["execution"]["tokens"]["total_tokens"], 240)

    def test_shared_turn_resource_unknown_not_duplicated(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f)
        second = copy.deepcopy(ledger["tasks"][0])
        second["id"] = "second"
        ledger["tasks"].append(second)
        s = r.aggregate(f, ledger)
        self.assertEqual(s["counts"]["delivered"], 2)
        self.assertEqual(s["execution"]["tokens"]["total_tokens"], 120)
        self.assertTrue(all(t["execution"] is None for t in s["tasks"]))

    def test_cross_thread_single_goal(self):
        self.save(self.log())
        self.save(self.log("second", "second-thread"), "second.jsonl")
        f = self.facts()
        s = r.aggregate(f, self.ledger(f, refs=["turn", "second"]))
        self.assertEqual(s["counts"]["delivered"], 1)
        self.assertEqual(s["execution"]["recorded_calls"], 2)

    def test_reopen_and_scope_change(self):
        self.save(self.log())
        f = self.facts()
        events = [self.event(f), self.event(f, "reopened", "2026-10-07T10:00:00+08:00"), self.event(f, "scope_changed", "2026-10-07T10:01:00+08:00"), self.event(f, "delivered", "2026-10-08T10:00:00+08:00")]
        s = r.aggregate(f, self.ledger(f, events))
        self.assertEqual(s["counts"]["delivered"], 1)
        self.assertEqual(s["process_events"]["rework"], 0)
        self.assertEqual(s["process_events"]["scope_changed"], 1)

    def test_separate_delivery_and_later_acceptance(self):
        self.save(self.log(start="2026-10-03T09:00:00+08:00", end="2026-10-03T09:10:00+08:00"))
        f = self.facts()
        ledger = self.ledger(f, [self.event(f, at="2026-10-03T09:10:00+08:00"), self.event(f, "accepted", "2026-10-06T11:00:00+08:00")])
        ledger["tasks"][0]["started_at"] = "2026-10-03T09:00:00+08:00"
        s = r.aggregate(f, ledger)
        self.assertEqual(s["counts"]["delivered"], 0)
        self.assertEqual(s["counts"]["accepted"], 1)
        self.assertEqual(s["end_states"]["accepted"], 1)

    def test_cycle_full_duration_and_clipped_execution(self):
        self.save(self.log(start="2026-10-04T23:50:00+08:00", end="2026-10-05T00:10:00+08:00"))
        f = self.facts()
        ledger = self.ledger(f, [self.event(f, at="2026-10-05T00:10:00+08:00")])
        ledger["tasks"][0]["started_at"] = "2026-10-04T23:50:00+08:00"
        s = r.aggregate(f, ledger)
        self.assertEqual(s["completion_cycle"]["median_seconds"], 1200)
        self.assertEqual(s["execution"]["execution_seconds_sum"], 600)

    def test_future_records_and_backfill_rejected(self):
        values = self.log() + [self.rec("response_item", {"type": "message", "role": "assistant", "phase": "final", "content": [{"type": "output_text", "text": "FUTURE-SECRET"}]}, "2026-10-12T09:00:00+08:00")]
        self.save(values, "wrong-file-date.jsonl")
        f = self.facts()
        self.assertNotIn("FUTURE-SECRET", json.dumps(f))
        with self.assertRaises(r.DataError):
            r.aggregate(f, self.ledger(f, [self.event(f, at="2026-10-12T09:00:00+08:00")]))

    def test_open_turn_and_missing_tokens_unknown(self):
        self.save(self.log(usage=False, end=None))
        f = self.facts()
        s = r.aggregate(f, r.candidates(f))
        self.assertIsNone(s["execution"]["tokens"]["total_tokens"])
        self.assertIsNone(s["execution"]["execution_seconds_sum"])
        self.assertEqual(s["execution"]["open_or_untimed_turns"], 1)

    def test_legacy_increment_not_sum_reset_unknown(self):
        values = self.log(usage=False)
        for minute, number in [(1, 100), (2, 130), (3, 10)]:
            values.append(self.rec("event_msg", {"type": "token_count", "info": {"total_token_usage": {"total_tokens": number}}}, f"2026-10-06T09:0{minute}:00+08:00"))
        self.save(values)
        f = self.facts()
        s = r.aggregate(f, r.candidates(f))
        self.assertEqual(s["execution"]["tokens"]["total_tokens"], 30)
        self.assertEqual(s["execution"]["partial_usage_turns"], 1)
        self.assertTrue(any("回退" in w for w in s["warnings"]))

    def test_truncated_unknown_prefix_hash_source_unchanged(self):
        path = self.save(self.log() + [self.rec("unknown-schema", {})])
        with path.open("a") as handle:
            handle.write("{unfinished")
        before = path.read_bytes()
        f = self.facts()
        self.assertTrue(any("无法解析" in w for w in f["warnings"]))
        self.assertTrue(any("未知记录类型" in w for w in f["warnings"]))
        self.assertEqual(f["sources"][0]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(path.read_bytes(), before)

    def test_project_filter_and_sensitive_context_exclusion(self):
        values = self.log() + [self.rec("response_item", {"type": "message", "role": "system", "content": [{"type": "input_text", "text": "SYSTEM-SECRET"}]}), self.rec("response_item", {"type": "reasoning", "summary": "THOUGHT-SECRET"}), self.rec("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "# AGENTS.md instructions\nHARNESS-SECRET"}]})]
        self.save(values)
        self.save(self.log("private", "private-thread", project=str(self.root / "private")), "private.jsonl")
        text = json.dumps(self.facts())
        for secret in ["SYSTEM-SECRET", "THOUGHT-SECRET", "HARNESS-SECRET", "private-thread"]:
            self.assertNotIn(secret, text)

    def test_unknown_event_dates_and_cycle_samples(self):
        self.save(self.log())
        f = self.facts()
        s = r.aggregate(f, self.ledger(f, [self.event(f, at=None)]))
        self.assertEqual(s["counts"]["delivered"], 0)
        self.assertEqual(s["coverage"]["unknown_date_events"], 1)
        ledger = self.ledger(f)
        ledger["tasks"][0]["started_at"] = None
        s = r.aggregate(f, ledger)
        self.assertIsNone(s["completion_cycle"]["median_seconds"])
        self.assertEqual(s["completion_cycle"]["missing_samples"], 1)

    def test_unmapped_and_report_turn_exclusion(self):
        self.save(self.log())
        f = self.facts()
        ledger = {"schema_version": 1, "tasks": [], "excluded_turns": []}
        self.assertEqual(r.aggregate(f, ledger)["coverage"]["unmapped_turn_ids"], ["turn"])
        ledger["excluded_turns"] = [{"turn_id": "turn", "reason": "报告生成"}]
        self.assertEqual(r.aggregate(f, ledger)["execution"]["turns"], 0)

    def test_current_readme_cannot_rebuild_old_state(self):
        self.save(self.log())
        folder = Path(self.project) / ".cohestra/handoffs/goal"
        folder.mkdir(parents=True)
        (folder / "README.md").write_text("status: completed", encoding="utf-8")
        f = self.facts()
        ledger = self.ledger(f)
        ledger["tasks"][0]["events"][0]["evidence"] = [next(e["id"] for e in f["evidence"] if e["kind"] == "workflow")]
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)

    def test_duplicate_tasks_and_missing_evidence_rejected(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f)
        ledger["tasks"].append(copy.deepcopy(ledger["tasks"][0]))
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)
        ledger = self.ledger(f)
        ledger["tasks"][0]["events"][0]["evidence"] = ["missing"]
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)

    def test_intervention_wait_retry_and_validation(self):
        self.save(self.log())
        f = self.facts()
        events = [self.event(f, "intervention", category="authorization"), self.event(f, "wait", category="approval", until="2026-10-06T09:15:00+08:00"), self.event(f, "retry"), self.event(f, "validation_failed")]
        s = r.aggregate(f, self.ledger(f, events))
        self.assertEqual(s["interventions"], {"authorization": 1})
        self.assertEqual(s["recorded_wait_seconds_union"], 300)
        self.assertEqual(s["process_events"]["retry"], 1)
        self.assertEqual(s["process_events"]["validation_failed"], 1)

    def test_wait_from_previous_period_is_clipped(self):
        self.save(self.log(start="2026-10-04T23:50:00+08:00"))
        f = self.facts()
        events = [self.event(f), self.event(f, "wait", "2026-10-04T23:50:00+08:00", category="input", until="2026-10-05T00:10:00+08:00")]
        ledger = self.ledger(f, events)
        ledger["tasks"][0]["started_at"] = "2026-10-04T23:50:00+08:00"
        s = r.aggregate(f, ledger)
        self.assertEqual(s["recorded_wait_seconds_union"], 600)
        self.assertEqual(s["process_events"]["wait"], 0)

    def test_corrections_preserve_original(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f)
        task = copy.deepcopy(ledger["tasks"][0])
        task["events"] = []
        patch = {"schema_version": 1, "reason": "用户更正", "patch": [{"op": "replace", "task_id": "goal", "revision": 1, "task": task}]}
        self.assertEqual(r.aggregate(f, r.apply_corrections(ledger, [patch]))["counts"]["delivered"], 0)
        self.assertEqual(r.aggregate(f, ledger)["counts"]["delivered"], 1)
        patch["patch"][0]["revision"] = 2
        with self.assertRaises(r.DataError):
            r.apply_corrections(ledger, [patch])

    def test_annual_trend_recomputes_from_base(self):
        self.save(self.log())
        self.window = r.period_window("yearly", "Asia/Shanghai", r.stamp("2027-01-02T09:00:00Z"), "2026-06-01")
        f = self.facts()
        s = r.aggregate(f, self.ledger(f))
        buckets = r.trend(s, f)
        self.assertEqual(len(buckets), 12)
        self.assertEqual(sum(b["delivered"] for b in buckets), 1)
        self.assertEqual(buckets[9]["execution"]["tokens"]["total_tokens"], 120)

    def cli(self, args):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(r.main(args), 0)
        return json.loads(stream.getvalue())

    def test_cli_versioned_reproducible_report_and_correction(self):
        path = self.save(self.log())
        before = path.read_bytes()
        configured = self.cli(["configure", "--output", self.config["output"], "--project", self.project, "--source-root", str(self.logs)])
        collected = self.cli(["collect", "--config", configured["config"], "--date", "2026-10-07", "--now", "2026-10-13T09:00:00+08:00"])
        snapshot = Path(collected["snapshot"])
        f = r.read_json(snapshot / "facts.json")
        r.write_json(snapshot / "tasks.json", self.ledger(f))
        first = self.cli(["report", "--snapshot", str(snapshot)])
        second = self.cli(["report", "--snapshot", str(snapshot)])
        self.assertNotEqual(first["report"], second["report"])
        self.assertEqual(Path(first["statistics"]).read_bytes(), Path(second["statistics"]).read_bytes())
        self.assertIn("本期交付（含验收） 1", Path(first["report"]).read_text())
        patch = self.root / "patch.json"
        r.write_json(patch, [{"op": "remove", "task_id": "goal", "revision": 1}])
        corrected = self.cli(["correct", "--config", configured["config"], "--patch", str(patch), "--reason", "用户确认重复"])
        third = self.cli(["report", "--snapshot", str(snapshot), "--correction", corrected["correction"]])
        self.assertEqual(third["counts"]["delivered"], 0)
        self.assertEqual(r.read_json(first["statistics"])["counts"]["delivered"], 1)
        self.assertEqual(path.read_bytes(), before)

    def test_baseline_recomputed_and_hash_verified(self):
        self.save(self.log())
        f = self.facts()
        s = r.aggregate(f, self.ledger(f))
        old = copy.deepcopy(f)
        old["window"] = r.period_window("weekly", "Asia/Shanghai", r.stamp("2026-10-13T09:00:00Z"), "2026-09-30")
        old["turns"] = []
        tasks = {"schema_version": 1, "tasks": [], "excluded_turns": []}
        folder = self.root / "baseline"
        folder.mkdir()
        r.write_json(folder / "facts.json", old)
        r.write_json(folder / "tasks.json", tasks)
        r.write_json(folder / "manifest.json", {"facts": str(folder / "facts.json"), "input_hashes": {"facts": r.digest(old), "ledger": r.digest(tasks)}})
        self.assertFalse(r.compare(s, f, folder)["comparable"])
        self.assertIn("缺少观察样本", r.compare(s, f, folder)["reason"])
        old["warnings"].append("tampered")
        r.write_json(folder / "facts.json", old)
        with self.assertRaises(r.DataError):
            r.compare(s, f, folder)

    def test_output_never_overlaps_sources_or_workflow_container(self):
        for output in [str(self.logs), str(self.logs / "reports"), str(self.root), self.project + "/.cadra/reports"]:
            with self.assertRaises(r.DataError):
                r.validate_config(dict(self.config, output=output))

    def test_historical_open_turn_does_not_imply_current_activity(self):
        self.save(self.log(start="2026-09-01T09:00:00+08:00", end=None, usage=False))
        f = self.facts()
        s = r.aggregate(f, r.candidates(f))
        self.assertEqual(s["execution"]["turns"], 0)
        self.assertEqual(s["end_states"]["pending_confirmation"], 0)
        self.assertTrue(all(b["execution"]["turns"] == 0 for b in r.trend(s, f)))

    def test_user_interaction_belongs_to_message_day(self):
        self.save(self.log(start="2026-10-05T23:50:00+08:00", end="2026-10-06T00:10:00+08:00"))
        f = self.facts()
        s = r.aggregate(f, r.candidates(f))
        buckets = r.trend(s, f)
        self.assertEqual(sum(b["execution"]["confirmed_user_turns"] for b in buckets), 1)
        self.assertEqual(buckets[1]["execution"]["confirmed_user_turns"], 0)
        self.assertEqual(buckets[1]["execution"]["execution_seconds_sum"], 600)

    def test_latest_revision_only_counts_once_in_stock(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f)
        second = copy.deepcopy(ledger["tasks"][0])
        second.update(revision=2, events=[])
        ledger["tasks"].append(second)
        s = r.aggregate(f, ledger)
        self.assertEqual(s["counts"]["delivered"], 1)
        self.assertEqual(sum(s["end_states"].values()), 1)
        self.assertEqual(s["end_states"]["pending_confirmation"], 1)
        self.assertEqual(s["task_composition"][0]["tasks"], 1)
        self.assertTrue(s["tasks"][0]["superseded"])

    def test_shared_intervention_is_one_event_and_conflicts_reject(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f, [self.event(f, "intervention", category="authorization")])
        other = copy.deepcopy(ledger["tasks"][0])
        other["id"] = "second"
        ledger["tasks"].append(other)
        s = r.aggregate(f, ledger)
        self.assertEqual(s["interventions"]["authorization"], 1)
        self.assertEqual(sum(b["process_events"]["intervention"] for b in r.trend(s, f)), 1)
        other["events"][0]["category"] = "manual_fix"
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)

    def test_delivery_requires_reviewed_evidence_or_actual_answer(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f)
        event = ledger["tasks"][0]["events"][0]
        event["evidence"] = [next(e["id"] for e in f["evidence"] if e["kind"] == "assistant")]
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)
        event["basis"] = "answer"
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)
        ledger["tasks"][0]["type"] = "consultation"
        self.assertEqual(r.aggregate(f, ledger)["counts"]["delivered"], 1)
        event["kind"] = "accepted"
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)

    def test_validation_level_and_tool_excerpt_required(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f, [self.event(f, "validation_passed")])
        ledger["tasks"][0]["events"][0]["category"] = "runtime"
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)
        ledger = self.ledger(f)
        ledger["tasks"][0]["events"][0].pop("verified_excerpt")
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)

    def test_tool_pointer_does_not_copy_raw_sensitive_output(self):
        values = self.log()
        values.insert(5, self.rec("response_item", {"type": "function_call_output", "call_id": "secret-check", "output": "ACCOUNT-SECRET"}))
        self.save(values)
        f = self.facts()
        self.assertNotIn("ACCOUNT-SECRET", json.dumps(f))
        pointer = next(e for e in f["evidence"] if e.get("call_id") == "secret-check")
        self.assertEqual(pointer["output_sha256"], r.digest("ACCOUNT-SECRET"))
        self.assertIsNone(pointer["text"])

    def test_nested_children_evidence_expands_independent_of_order(self):
        self.save(self.log())
        self.save(self.log("z-child", "child-thread", root="turn", child=True), "child.jsonl")
        self.save(self.log("a-grandchild", "grandchild-thread", root="z-child", child=True), "grandchild.jsonl")
        f = self.facts()
        # Evidence validation used to depend on one-pass iteration order.
        f["turns"].sort(key=lambda t: t["id"])
        ledger = self.ledger(f)
        ledger["tasks"][0]["events"][0]["evidence"] = [next(e["id"] for e in f["evidence"] if e.get("turn_id") == "a-grandchild" and e["kind"] == "tool_result")]
        self.assertEqual(r.aggregate(f, ledger)["coverage"]["mapped_period_turns"], 3)

    def test_future_payload_and_conflicting_lifecycle_not_timed(self):
        values = self.log()
        values[-1]["payload"]["completed_at"] = "2026-11-01T09:00:00+08:00"
        self.save(values)
        f = self.facts()
        self.assertIsNone(f["turns"][0]["end"])
        self.assertTrue(any("超出截止" in w for w in f["warnings"]))
        values = self.log()
        values.append(self.rec("event_msg", {"type": "task_complete", "turn_id": "turn", "completed_at": "2026-10-06T09:11:00+08:00"}))
        self.save(values)
        f = self.facts()
        self.assertIsNone(f["turns"][0]["end"])
        self.assertTrue(any("时间冲突" in w for w in f["warnings"]))

    def test_cross_project_counter_gap_is_not_charged_to_current_turn(self):
        values = self.log(usage=False)
        values += [self.rec("event_msg", {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 100}}}),
                   self.rec("turn_context", {"turn_id": "private", "cwd": str(self.root / "private")}),
                   self.rec("event_msg", {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 300}}}),
                   self.rec("turn_context", {"turn_id": "turn", "cwd": self.project}),
                   self.rec("event_msg", {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 350}}})]
        self.save(values)
        f = self.facts()
        self.assertIsNone(r.aggregate(f, r.candidates(f))["execution"]["tokens"]["total_tokens"])

    def test_unknown_workflow_date_needs_dated_anchor(self):
        self.save(self.log())
        folder = Path(self.project) / ".cadra/runs"
        folder.mkdir(parents=True)
        (folder / "future-run.md").write_text("completed: future", encoding="utf-8")
        f = self.facts()
        ledger = self.ledger(f)
        event = ledger["tasks"][0]["events"][0]
        event["evidence"] = [next(e["id"] for e in f["evidence"] if e["kind"] == "workflow")]
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)
        event["at"] = None
        self.assertEqual(r.aggregate(f, ledger)["counts"]["delivered"], 0)

    def test_bad_nested_records_preserve_later_valid_records(self):
        values = self.log()
        values.insert(1, self.rec("event_msg", {"type": "task_started", "turn_attribution": [1]}))
        values.insert(4, self.rec("response_item", {"type": "message", "role": "user", "content": 42}))
        self.save(values)
        f = self.facts()
        self.assertEqual(r.aggregate(f, r.candidates(f))["execution"]["execution_seconds_sum"], 600)
        self.assertTrue(any("形状未知" in w for w in f["warnings"]))

    def test_snapshot_mutation_rejected_and_report_has_own_base(self):
        self.save(self.log())
        config = self.root / "config.json"
        r.write_json(config, self.config)
        snapshot = Path(self.cli(["collect", "--config", str(config), "--date", "2026-10-07", "--now", "2026-10-13T09:00:00+08:00"])["snapshot"])
        f = r.read_json(snapshot / "facts.json")
        r.write_json(snapshot / "tasks.json", self.ledger(f))
        folder = Path(self.cli(["report", "--snapshot", str(snapshot)])["report"]).parent
        f["warnings"].append("tampered")
        r.write_json(snapshot / "facts.json", f)
        stream = io.StringIO()
        with contextlib.redirect_stderr(stream):
            self.assertEqual(r.main(["report", "--snapshot", str(snapshot)]), 2)
        self.assertIn("哈希不符", stream.getvalue())
        self.assertNotIn("tampered", r.read_json(folder / "facts.json")["warnings"])
        self.assertEqual(r.read_json(folder / "manifest.json")["facts"], str(folder / "facts.json"))

    def test_render_contains_quality_and_resource_trends(self):
        self.save(self.log())
        f = self.facts()
        s = r.aggregate(f, self.ledger(f, [self.event(f), self.event(f, "retry")]))
        s["trend"] = r.trend(s, f)
        text = r.render(s, f)
        self.assertIn("累计 / 占用秒", text)
        self.assertIn("返工 / 重试", text)
        self.assertIn("token 总量 / 覆盖轮", text)
        self.assertIn("验证层级：构建", text)
        self.assertEqual(sum(b["process_events"]["retry"] for b in s["trend"]), 1)

    def test_explicit_future_workflow_does_not_leak_into_old_snapshot(self):
        self.save(self.log())
        folder = Path(self.project) / ".cohestra/handoffs/goal"
        folder.mkdir(parents=True)
        (folder / "code-01.md").write_text("- 时间：2026-10-14T09:00:00+08:00\nWORKFLOW-FUTURE-SECRET", encoding="utf-8")
        (folder / "review-01.md").write_text("- 时间：2026-10-06T09:05:00+08:00\nReview evidence", encoding="utf-8")
        f = self.facts()
        self.assertNotIn("WORKFLOW-FUTURE-SECRET", json.dumps(f))
        workflow = next(e for e in f["evidence"] if e["kind"] == "workflow")
        self.assertEqual(workflow["at"], "2026-10-06T01:05:00Z")
        self.assertTrue(any("截止后工作流" in w for w in f["warnings"]))

    def test_mutable_run_with_future_update_is_not_old_state(self):
        self.save(self.log())
        folder = Path(self.project) / ".cadra/runs"
        folder.mkdir(parents=True)
        (folder / "run.md").write_text("- 建立：agent 2026-10-06T09:00:00+08:00\n- 最近更新：2026-10-14T09:00:00+08:00\nFUTURE-RUN", encoding="utf-8")
        f = self.facts()
        self.assertNotIn("FUTURE-RUN", json.dumps(f))

    def test_same_turn_can_touch_two_selected_projects(self):
        second = str(self.root / "second-project")
        self.config["projects"].append(second)
        values = self.log()
        values.insert(5, self.rec("turn_context", {"turn_id": "turn", "cwd": second}))
        self.save(values)
        f = self.facts()
        ledger = self.ledger(f)
        ledger["tasks"][0]["project"] = second
        self.assertEqual(r.aggregate(f, ledger)["counts"]["delivered"], 1)
        self.assertEqual(f["turns"][0]["projects"], sorted(self.config["projects"]))

    def test_token_unknown_fields_do_not_import_account_metadata(self):
        values = self.log()
        values[4]["payload"]["usage"]["account_id"] = "ACCOUNT-METADATA-SECRET"
        self.save(values)
        f = self.facts()
        self.assertNotIn("ACCOUNT-METADATA-SECRET", json.dumps(f))
        self.assertEqual(r.aggregate(f, r.candidates(f))["execution"]["tokens"]["total_tokens"], 120)

    def test_fork_owner_unknown_without_response_owner_not_confirmed(self):
        self.save(self.log(usage=False))
        copied = self.log(usage=False)
        copied[0]["payload"].update(id="fork-thread", source="subAgent")
        self.save(copied, "00fork.jsonl")
        f = self.facts()
        s = r.aggregate(f, r.candidates(f))
        self.assertEqual(s["execution"]["confirmed_user_turns"], 0)
        self.assertEqual(s["execution"]["ambiguous_owner_turns"], 1)
        self.assertEqual(s["execution"]["execution_seconds_sum"], 600)

    def test_positive_comparison_and_field_coverage_mismatch(self):
        self.save(self.log())
        f = self.facts()
        s = r.aggregate(f, self.ledger(f))
        old = copy.deepcopy(f)
        old["window"] = r.period_window("weekly", "Asia/Shanghai", r.stamp("2026-10-13T09:00:00Z"), "2026-09-30")
        # Shift base records by exactly one week; leave no precomputed metrics.
        shift = r.timedelta(days=7)
        for turn in old["turns"]:
            for field in ["start", "end", "observed_at", "last_observed_at"]:
                turn[field] = r.iso(r.stamp(turn[field]) - shift) if turn[field] else None
            for field in ["activity_at", "user_message_at"]:
                turn[field] = [r.iso(r.stamp(at) - shift) for at in turn[field]]
            for usage in turn["usage"]:
                usage["at"] = r.iso(r.stamp(usage["at"]) - shift)
        for evidence in old["evidence"]:
            evidence["at"] = r.iso(r.stamp(evidence["at"]) - shift)
        ledger = self.ledger(old)
        ledger["tasks"][0]["started_at"] = "2026-09-29T09:00:00+08:00"
        ledger["tasks"][0]["events"][0]["at"] = "2026-09-29T09:10:00+08:00"
        folder = self.root / "baseline"
        folder.mkdir()
        def write_baseline():
            r.write_json(folder / "facts.json", old)
            r.write_json(folder / "tasks.json", ledger)
            r.write_json(folder / "manifest.json", {"facts": str(folder / "facts.json"), "input_hashes": {"facts": r.digest(old), "ledger": r.digest(ledger)}})
        write_baseline()
        comparison = r.compare(s, f, folder)
        self.assertTrue(comparison["comparable"])
        self.assertEqual(comparison["groups"][0]["baseline"]["delivered"], 1)
        old["turns"][0]["usage"][0]["tokens"].pop("input_tokens")
        write_baseline()
        self.assertFalse(r.compare(s, f, folder)["comparable"])
        old["config"]["source_roots"].append(str(self.root / "other-source"))
        write_baseline()
        self.assertIn("来源", r.compare(s, f, folder)["reason"])

    def test_empty_legacy_increment_does_not_invent_resource_coverage(self):
        values = self.log(usage=False)
        for minute in [1, 2]:
            values.append(self.rec("event_msg", {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 100}}}, f"2026-10-06T09:0{minute}:00+08:00"))
        self.save(values)
        f = self.facts()
        s = r.aggregate(f, r.candidates(f))
        self.assertIsNone(s["execution"]["tokens"]["total_tokens"])
        self.assertEqual(s["execution"]["recorded_calls"], 0)
        self.assertEqual(s["execution"]["token_turn_coverage"]["known"], 0)

    def test_unknown_date_task_does_not_disappear_without_current_turn(self):
        self.save(self.log(start="2026-09-01T09:00:00+08:00", end="2026-09-01T09:10:00+08:00"))
        f = self.facts()
        ledger = self.ledger(f, [self.event(f, at=None)])
        ledger["tasks"][0]["started_at"] = None
        s = r.aggregate(f, ledger)
        self.assertEqual(s["coverage"]["unknown_date_events"], 1)
        self.assertEqual(s["counts"]["delivered"], 0)
        self.assertEqual(s["tasks"][0]["status"], "pending_confirmation")

    def test_cycle_requires_start_provenance(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f)
        ledger["tasks"][0].pop("start_evidence")
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)
        ledger["tasks"][0]["started_at"] = None
        self.assertIsNone(r.aggregate(f, ledger)["completion_cycle"]["median_seconds"])

    def test_recommendation_requires_task_evidence(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f)
        item = {"text": "将已核对的构建步骤复用到同类目标", "task_ids": ["goal"]}
        ledger["recommendations"] = [item]
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)
        item["evidence"] = [self.event(f)["evidence"][0]]
        self.assertEqual(len(r.aggregate(f, ledger)["recommendations"]), 1)

    def test_invalid_payload_time_does_not_stop_collection(self):
        values = self.log()
        values.insert(1, self.rec("event_msg", {"type": "task_started", "turn_id": "turn", "started_at": "invalid"}))
        values.insert(1, self.rec("turn_context", {"turn_id": "turn", "cwd": self.project, "root_turn_id": {"bad": True}}))
        self.save(values)
        f = self.facts()
        self.assertEqual(r.aggregate(f, r.candidates(f))["execution"]["execution_seconds_sum"], 600)
        self.assertTrue(any("生命周期时间无法解析" in w for w in f["warnings"]))
        self.assertTrue(any("稳定标识形状未知" in w for w in f["warnings"]))

    def test_invalid_token_fields_are_unknown_and_not_stored(self):
        values = self.log()
        values[4]["payload"]["usage"]["input_tokens"] = "INVALID-FIELD-SECRET"
        values[4]["payload"]["usage"]["cached_input_tokens"] = -1
        self.save(values)
        f = self.facts()
        self.assertNotIn("INVALID-FIELD-SECRET", json.dumps(f))
        s = r.aggregate(f, r.candidates(f))
        self.assertIsNone(s["execution"]["tokens"]["input_tokens"])
        self.assertEqual(s["execution"]["tokens"]["total_tokens"], 120)
        self.assertEqual(s["execution"]["partial_usage_turns"], 1)

    def test_real_plan_feedback_is_confirmed_interaction(self):
        # Real acceptance: a user naming response follows task_started with
        # plan_feedback, not composer (source lines 97/99).
        values = self.log()
        values[1]["payload"]["turn_attribution"]["turn_trigger"] = "plan_feedback"
        self.save(values)
        s = r.aggregate(self.facts(), r.candidates(self.facts()))
        self.assertEqual(s["execution"]["confirmed_user_turns"], 1)
        self.assertEqual(s["execution"]["candidate_user_turns"], 0)

    def test_unrecognized_trigger_keeps_candidate_instead_of_dropping_user(self):
        values = self.log()
        values[1]["payload"]["turn_attribution"]["turn_trigger"] = "future_external_trigger"
        self.save(values)
        f = self.facts()
        s = r.aggregate(f, r.candidates(f))
        self.assertEqual(s["execution"]["confirmed_user_turns"], 0)
        self.assertEqual(s["execution"]["candidate_user_turns"], 1)

    def test_delivered_or_accepted_task_keeps_unresolved_follow_up(self):
        self.save(self.log())
        f = self.facts()
        for kind in ["delivered", "accepted"]:
            ledger = self.ledger(f, [self.event(f, kind)])
            ledger["tasks"][0]["next_step"] = "补独立 agent 与 CLI 联调验收"
            s = r.aggregate(f, ledger)
            tail = r.render(s, f).split("## 遗留与下一步", 1)[1].split("## 改进建议", 1)[0]
            self.assertIn("补独立 agent 与 CLI 联调验收", tail)
            self.assertNotIn("无已记录的遗留事项", tail)
            self.assertEqual(s["tasks"][0]["status"], kind)
            self.assertEqual(s["counts"]["delivered"], 1)
        ledger["tasks"][0]["next_step"] = ""
        tail = r.render(r.aggregate(f, ledger), f).split("## 遗留与下一步", 1)[1].split("## 改进建议", 1)[0]
        self.assertIn("无已记录的遗留事项", tail)

    def test_daily_report_does_not_render_empty_trend_table(self):
        self.window = r.period_window("daily", "Asia/Shanghai", r.stamp("2026-10-13T09:00:00Z"), "2026-10-06")
        self.save(self.log())
        f = self.facts()
        s = r.aggregate(f, self.ledger(f))
        s["trend"] = r.trend(s, f)
        self.assertNotIn("## 周期内趋势", r.render(s, f))

    def test_real_user_input_tool_answer_has_feedback_and_coverage(self):
        values = self.log()
        call = {"type": "function_call", "name": "request_user_input", "call_id": "decision-call", "arguments": '{"questions":[]}' }
        output = {"type": "function_call_output", "call_id": "decision-call", "output": json.dumps({"answers": {"scope": {"answers": ["指定项目集合"]}, "format": {"answers": ["简报与 Markdown"]}}})}
        values[5:5] = [self.rec("response_item", call), self.rec("response_item", output)]
        self.save(values)
        f = self.facts()
        feedback = next(e for e in f["evidence"] if e["kind"] == "user_feedback")
        self.assertIsNone(feedback["text"])
        self.assertEqual(feedback["request_location"]["line"], 6)
        ledger = self.ledger(f)
        s = r.aggregate(f, ledger)
        self.assertEqual(s["coverage"]["user_feedback"]["observed"], 1)
        self.assertEqual(s["coverage"]["user_feedback"]["classified"], 0)
        self.assertIn("人工介入统计不完整", r.render(s, f))
        ledger["tasks"][0]["events"].append({"id": "choice", "kind": "intervention", "at": feedback["at"], "category": "decision", "evidence": [feedback["id"]], "note": "已核对实际选择，按一次消息而非两个问题计数"})
        s = r.aggregate(f, ledger)
        self.assertEqual(s["interventions"]["decision"], 1)
        self.assertEqual(s["coverage"]["user_feedback"]["unclassified_evidence_ids"], [])
        self.assertEqual(s["execution"]["confirmed_user_turns"], 1)

    def test_unpaired_or_other_tool_answers_not_human_feedback(self):
        values = self.log()
        output = json.dumps({"answers": {"scope": {"answers": ["data"]}}})
        values[5:5] = [self.rec("response_item", {"type": "function_call", "name": "lookup", "call_id": "ordinary", "arguments": "{}"}),
                       self.rec("response_item", {"type": "function_call_output", "call_id": "ordinary", "output": output}),
                       self.rec("response_item", {"type": "function_call_output", "call_id": "unpaired", "output": output})]
        self.save(values)
        self.assertFalse(any(e["kind"] == "user_feedback" for e in self.facts()["evidence"]))

    def test_user_feedback_acceptance_needs_reviewed_excerpt(self):
        values = self.log()
        values[5:5] = [self.rec("response_item", {"type": "function_call", "name": "functions.request_user_input", "call_id": "accept", "arguments": "{}"}),
                       self.rec("response_item", {"type": "function_call_output", "call_id": "accept", "output": '{"answers":{"accept":{"answers":["已验收"]}}}'})]
        self.save(values)
        f = self.facts()
        feedback = next(e for e in f["evidence"] if e["kind"] == "user_feedback")
        ledger = self.ledger(f)
        event = ledger["tasks"][0]["events"][0]
        event.update(kind="accepted", basis="user_acceptance", evidence=[feedback["id"]])
        event.pop("verified_excerpt")
        with self.assertRaises(r.DataError):
            r.aggregate(f, ledger)
        event["verified_excerpt"] = "已核对验收问题及实际选择：已验收"
        self.assertEqual(r.aggregate(f, ledger)["counts"]["accepted"], 1)


if __name__ == "__main__":
    unittest.main()

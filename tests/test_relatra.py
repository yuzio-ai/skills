"""Offline behavior fixtures; no accounts, network, or original task writes."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
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
        self.config = {"schema_version": r.SCHEMA, "projects": [self.project], "source_roots": [str(self.logs)],
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
        return r.scan(self.config, self.window, "deep")

    def event(self, facts, kind="delivered", at="2026-10-06T09:10:00+08:00", **extra):
        eid = next(e["id"] for e in facts["evidence"] if e.get("turn_id") == "turn" and e["kind"] == "tool_result")
        if kind.startswith("validation_"):
            extra.setdefault("category", "build")
        return {"id": kind + str(at), "kind": kind, "at": at, "evidence": [eid], "note": "已核实目标与交付",
                "basis": "build", "verified_excerpt": "Build succeeded; checked artifact navigation", **extra}

    def ledger(self, facts, events=None, refs=None):
        return {"schema_version": r.SCHEMA, "analysis": facts["analysis"], "process_reviewed": facts["analysis"] == "deep", "tasks": [{"id": "goal", "revision": 1, "title": "目标", "project": self.project, "type": "implementation",
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
        ledger = {"schema_version": r.SCHEMA, "analysis": "deep", "process_reviewed": True, "tasks": [], "excluded_turns": []}
        self.assertEqual(r.aggregate(f, ledger)["coverage"]["unmapped_turn_ids"], ["turn"])
        ledger["excluded_turns"] = [{"turn_id": "turn", "reason": "报告生成"}]
        self.assertEqual(r.aggregate(f, ledger)["execution"]["turns"], 0)

    def test_current_readme_cannot_rebuild_old_state(self):
        self.save(self.log())
        folder = Path(self.project) / ".yuzio/cohestra/handoffs/goal"
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

    def test_full_ledger_edit_preserves_original(self):
        self.save(self.log())
        f = self.facts()
        ledger = self.ledger(f)
        edited = copy.deepcopy(ledger)
        edited["tasks"][0]["events"] = []
        self.assertEqual(r.aggregate(f, edited)["counts"]["delivered"], 0)
        self.assertEqual(r.aggregate(f, ledger)["counts"]["delivered"], 1)

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
        self.config["output"] = str(Path(self.project) / ".yuzio/relatra")
        workflow_paths = [Path(self.project) / ".yuzio/cadra/runs/run.md",
                          Path(self.project) / ".yuzio/cohestra/handoffs/goal/code-01.md"]
        for workflow in workflow_paths:
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text("- 时间：2026-10-06T09:05:00+08:00\nWorkflow evidence", encoding="utf-8")
        workflow_before = {p: p.read_bytes() for p in workflow_paths}
        path = self.save(self.log())
        before = path.read_bytes()
        configured = self.cli(["configure", "--output", self.config["output"], "--project", self.project, "--source-root", str(self.logs)])
        collected = self.cli(["collect", "--config", configured["config"], "--date", "2026-10-07", "--now", "2026-10-13T09:00:00+08:00"])
        snapshot = Path(collected["snapshot"])
        self.assertTrue(r.inside(snapshot, self.config["output"]))
        f = r.read_json(snapshot / "facts.json")
        self.assertEqual({s["path"] for s in f["sources"] if s["kind"] == "workflow"},
                         {str(p) for p in workflow_paths})
        r.write_json(snapshot / "tasks.json", self.ledger(f))
        first = self.cli(["report", "--snapshot", str(snapshot)])
        self.assertTrue(r.inside(first["report"], self.config["output"]))
        second = self.cli(["report", "--snapshot", str(snapshot)])
        self.assertNotEqual(first["report"], second["report"])
        self.assertEqual(Path(first["statistics"]).read_bytes(), Path(second["statistics"]).read_bytes())
        self.assertIn("本期交付（含验收） 1", Path(first["report"]).read_text())
        edited = self.root / "edited.json"
        ledger = r.read_json(Path(first["report"]).parent / "tasks.json")
        ledger["tasks"] = []
        r.write_json(edited, ledger)
        first_folder = str(Path(first["report"]).parent)
        frozen = {p.name: p.read_bytes() for p in Path(first_folder).iterdir()}
        third = self.cli(["report", "--snapshot", first_folder, "--tasks", str(edited),
                          "--revises", first_folder, "--reason", "用户确认重复"])
        self.assertEqual({p.name: p.read_bytes() for p in Path(first_folder).iterdir()}, frozen)
        manifest = r.read_json(Path(third["report"]).parent / "manifest.json")
        self.assertEqual(manifest["revises"], first_folder)
        self.assertEqual(manifest["reason"], "用户确认重复")
        self.assertFalse((Path(third["report"]).parent / "corrections.json").exists())
        self.assertEqual(third["counts"]["delivered"], 0)
        self.assertEqual(r.read_json(first["statistics"])["counts"]["delivered"], 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual({p: p.read_bytes() for p in workflow_paths}, workflow_before)

    def test_baseline_recomputed_and_hash_verified(self):
        self.save(self.log())
        f = self.facts()
        s = r.aggregate(f, self.ledger(f))
        old = copy.deepcopy(f)
        old["window"] = r.period_window("weekly", "Asia/Shanghai", r.stamp("2026-10-13T09:00:00Z"), "2026-09-30")
        old["turns"] = []
        tasks = {"schema_version": r.SCHEMA, "analysis": "deep", "process_reviewed": True, "tasks": [], "excluded_turns": []}
        folder = self.root / "baseline"
        folder.mkdir()
        r.write_json(folder / "facts.json", old)
        r.write_json(folder / "tasks.json", tasks)
        r.write_json(folder / "manifest.json", {"schema_version": r.SCHEMA, "facts": str(folder / "facts.json"), "input_hashes": {"facts": r.digest(old), "ledger": r.digest(tasks)}})
        self.assertFalse(r.compare(s, f, folder)["comparable"])
        self.assertIn("缺少观察样本", r.compare(s, f, folder)["reason"])
        old["warnings"].append("tampered")
        r.write_json(folder / "facts.json", old)
        with self.assertRaises(r.DataError):
            r.compare(s, f, folder)

    def test_output_never_overlaps_sources_or_workflow_container(self):
        outputs = [str(self.logs), str(self.logs / "reports"), str(self.root)]
        outputs += [self.project + "/.yuzio/" + container + suffix
                    for container in ("cadra", "cohestra") for suffix in ("", "/reports")]
        for output in outputs:
            with self.subTest(output=output), self.assertRaises(r.DataError):
                r.validate_config(dict(self.config, output=output))

    def test_output_allows_relatra_and_custom_directories(self):
        for suffix in (".yuzio/relatra", "custom-reports", "cadra/reports", ".yuzio/cadra-reports"):
            output = str(Path(self.project) / suffix)
            with self.subTest(output=output):
                self.assertEqual(r.validate_config(dict(self.config, output=output))["output"], output)

    def test_output_symlink_into_workflow_container_is_rejected(self):
        container = Path(self.project) / ".yuzio/cohestra"
        container.mkdir(parents=True)
        alias = self.root / "reports-alias"
        alias.symlink_to(container, target_is_directory=True)
        with self.assertRaises(r.DataError):
            r.validate_config(dict(self.config, output=str(alias / "reports")))

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
        folder = Path(self.project) / ".yuzio/cadra/runs"
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
        folder = Path(self.project) / ".yuzio/cohestra/handoffs/goal"
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
        folder = Path(self.project) / ".yuzio/cadra/runs"
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
            r.write_json(folder / "manifest.json", {"schema_version": r.SCHEMA, "facts": str(folder / "facts.json"), "input_hashes": {"facts": r.digest(old), "ledger": r.digest(ledger)}})
        write_baseline()
        comparison = r.compare(s, f, folder)
        self.assertTrue(comparison["comparable"])
        self.assertEqual(comparison["groups"][0]["baseline"]["delivered"], 1)
        basic_facts = dict(f, analysis="basic")
        basic = r.aggregate(basic_facts, self.ledger(basic_facts))
        mixed = r.compare(basic, basic_facts, folder)
        self.assertTrue(mixed["comparable"])
        self.assertFalse(mixed["process_comparable"])
        self.assertIsNone(mixed["quality_current"])
        self.assertTrue(comparison["process_comparable"])
        self.assertIn("返工/重试：本期", r.render(dict(s, comparison=comparison), f))
        self.assertIn("过程指标未比较", r.render(dict(basic, comparison=mixed), basic_facts))
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

    def publish(self, facts=None, ledger=None):
        facts = facts if facts is not None else self.facts()
        ledger = ledger if ledger is not None else self.ledger(facts)
        snapshot = r.new_directory(self.root / "snapshots")
        r.write_json(snapshot / "facts.json", facts)
        r.write_json(snapshot / "tasks.json", ledger)
        r.write_json(snapshot / "manifest.json", {"schema_version": r.SCHEMA, "facts_hash": r.digest(facts)})
        return Path(self.cli(["report", "--snapshot", str(snapshot)])["report"]).parent

    def recollect(self, analysis="basic", date="2026-10-07", previous=None):
        config = self.root / "config.json"
        r.write_json(config, self.config)
        args = ["collect", "--config", str(config), "--date", date, "--now", "2026-10-20T09:00:00+08:00", "--analysis", analysis]
        if previous:
            args += ["--previous-report", str(previous)]
        result = self.cli(args)
        folder = Path(result["snapshot"])
        return result, r.read_json(folder / "facts.json"), r.read_json(folder / "tasks.json")

    def test_candidates_only_seed_current_activity_keep_history_for_lookup(self):
        self.save(self.log())
        self.save(self.log(tid="old", thread="old", start="2026-01-01T09:00:00+08:00", end="2026-01-01T09:10:00+08:00"), "old.jsonl")
        result, facts, ledger = self.recollect()
        self.assertEqual(len(facts["turns"]), 2)
        self.assertEqual([t["turn_ids"] for t in ledger["tasks"]], [["turn"]])
        self.assertIsNone(result["previous_report"])
        self.assertTrue(any("未全面盘点" in w for w in facts["warnings"]))

    def test_reuse_completed_goal_without_new_review_or_delivery(self):
        self.save(self.log())
        previous = self.publish()
        result, facts, ledger = self.recollect(date="2026-10-14")
        self.assertEqual(result["previous_report"], str(previous))
        self.assertEqual(result["review_queue"], [])
        self.assertEqual(ledger["tasks"][0]["id"], "goal")
        self.assertEqual(r.aggregate(facts, ledger)["counts"]["delivered"], 0)
        self.assertEqual(r.aggregate(facts, ledger)["tasks"], [])

    def test_reuse_keeps_unclosed_follow_up_without_current_activity(self):
        self.save(self.log())
        facts = self.facts()
        ledger = self.ledger(facts)
        ledger["tasks"][0]["next_step"] = "补运行时验收"
        self.publish(facts, ledger)
        result, facts, ledger = self.recollect(date="2026-10-14")
        self.assertEqual([x["id"] for x in result["review_queue"]], ["goal"])
        stats = r.aggregate(facts, ledger)
        self.assertEqual(stats["counts"]["delivered"], 0)
        self.assertEqual(stats["tasks"][0]["status"], "delivered")
        self.assertIn("补运行时验收", r.render(stats, facts))

    def test_new_turn_in_same_chat_requires_goal_judgment(self):
        original = self.log()
        self.save(original)
        self.publish()
        self.save(original + self.log(tid="new", start="2026-10-13T09:00:00+08:00", end="2026-10-13T09:10:00+08:00")[1:])
        result, facts, ledger = self.recollect(date="2026-10-14")
        self.assertEqual(len(ledger["tasks"]), 2)
        self.assertEqual(ledger["tasks"][0]["turn_ids"], ["turn"])
        self.assertEqual(ledger["tasks"][1]["turn_ids"], ["new"])
        self.assertEqual(len(result["review_queue"]), 1)
        self.assertEqual(r.aggregate(facts, ledger)["counts"]["delivered"], 0)

    def test_retained_candidate_id_never_absorbs_new_goal(self):
        records = self.log()
        self.save(records)
        facts = self.facts()
        ledger = self.ledger(facts)
        candidate_id = r.candidates(facts)["tasks"][0]["id"]
        ledger["tasks"][0]["id"] = candidate_id
        self.publish(facts, ledger)
        self.save(records + self.log(tid="new", start="2026-10-13T09:00:00+08:00", end="2026-10-13T09:10:00+08:00")[1:])
        result, facts, ledger = self.recollect(date="2026-10-14")
        self.assertEqual(len(ledger["tasks"]), 2)
        prior = next(t for t in ledger["tasks"] if t["id"] == candidate_id)
        candidate = next(t for t in ledger["tasks"] if t["id"] != candidate_id)
        self.assertEqual(prior["turn_ids"], ["turn"])
        self.assertEqual(candidate["turn_ids"], ["new"])
        self.assertEqual(candidate["events"], [])
        self.assertEqual([q["id"] for q in result["review_queue"]], [candidate["id"]])
        self.assertEqual(r.aggregate(facts, ledger)["end_states"]["pending_confirmation"], 1)

    def test_removed_child_triggers_review_and_coverage_gap(self):
        self.save(self.log())
        child = self.save(self.log(tid="child", thread="child-thread", root="turn", child=True), "child.jsonl")
        self.publish()
        child.unlink()
        result, facts, ledger = self.recollect()
        self.assertEqual([q["id"] for q in result["review_queue"]], ["goal"])
        self.assertTrue(any("轮次本次不可读取" in w for w in facts["warnings"]))
        self.assertFalse(ledger["tasks"][0].get("review_required", False))
        self.assertEqual(r.aggregate(facts, ledger)["counts"]["delivered"], 1)

    def test_scope_notice_does_not_hide_comparison_diagnostics(self):
        current_window = self.window
        self.window = r.period_window("weekly", "Asia/Shanghai", r.stamp("2026-10-13T09:00:00Z"), "2026-09-30")
        self.save(self.log(start="2026-09-29T09:00:00+08:00", end="2026-09-29T09:10:00+08:00"))
        old = self.facts()
        notice = "账本从周期活动建立，未全面盘点更早遗留目标"
        old["warnings"].append(notice)
        ledger = self.ledger(old, [self.event(old, at="2026-09-29T09:10:00+08:00")])
        ledger["tasks"][0]["started_at"] = "2026-09-29T09:00:00+08:00"
        prior = self.publish(old, ledger)
        self.window = current_window
        self.save(self.log())
        facts = self.facts()
        facts["warnings"].append(notice)
        self.assertTrue(r.compare(r.aggregate(facts, self.ledger(facts)), facts, prior)["comparable"])
        facts["warnings"].append("来源读取失败：fixture.jsonl：截断记录")
        stats = r.aggregate(facts, self.ledger(facts))
        self.assertFalse(r.compare(stats, facts, prior)["comparable"])
        old["warnings"].append("未知记录类型：fixture")
        prior = self.publish(old, ledger)
        self.assertFalse(r.compare(stats, facts, prior)["comparable"])

    def test_new_child_updates_parent_review_without_duplicate_candidate(self):
        self.save(self.log())
        self.publish()
        self.save(self.log(tid="child", thread="child-thread", root="turn", child=True), "child.jsonl")
        result, facts, ledger = self.recollect()
        self.assertEqual(len(ledger["tasks"]), 1)
        self.assertEqual([q["id"] for q in result["review_queue"]], ["goal"])
        stats = r.aggregate(facts, ledger)
        self.assertEqual(stats["counts"]["delivered"], 1)
        self.assertEqual(stats["execution"]["turns"], 2)

    def test_reuse_evidence_change_clears_claims_and_preserves_identity(self):
        records = self.log()
        self.save(records)
        previous = self.publish()
        records[-3]["payload"]["output"] = "Build failed"
        self.save(records)
        result, facts, ledger = self.recollect()
        task = ledger["tasks"][0]
        self.assertEqual(task["id"], "goal")
        self.assertTrue(task["review_required"])
        self.assertEqual(task["events"], [])
        stats = r.aggregate(facts, ledger)
        self.assertEqual(stats["counts"]["delivered"], 0)
        self.assertEqual(stats["tasks"][0]["status"], "pending_confirmation")
        self.assertIn(str(previous), result["review_queue"][0]["reason"])
        task["events"] = [self.event(facts)]
        with self.assertRaises(r.DataError):
            r.aggregate(facts, ledger)

    def test_missing_source_preserves_unknown_goal_in_report(self):
        path = self.save(self.log())
        self.publish()
        path.unlink()
        result, facts, ledger = self.recollect(date="2026-10-14")
        self.assertEqual(ledger["tasks"][0]["turn_ids"], [])
        stats = r.aggregate(facts, ledger)
        self.assertEqual(stats["counts"]["delivered"], 0)
        self.assertEqual(stats["end_states"]["pending_confirmation"], 1)
        self.assertIn("前版依据缺失", r.render(stats, facts))

    def test_reuse_prefers_latest_cutoff_then_latest_revision(self):
        self.save(self.log())
        first = self.publish()
        second = self.publish()
        result, facts, ledger = self.recollect()
        self.assertEqual(result["previous_report"], str(second))
        selected, _, _ = self.recollect(previous=first)
        self.assertEqual(selected["previous_report"], str(first))
        future = copy.deepcopy(facts)
        future["window"] = r.period_window("weekly", "Asia/Shanghai", r.stamp("2026-11-01T09:00:00Z"), "2026-10-21")
        self.publish(future, dict(ledger, analysis=future["analysis"]))
        result, _, _ = self.recollect()
        self.assertEqual(result["previous_report"], str(second))

    def test_reuse_rejects_invalid_explicit_report_and_warns_in_auto(self):
        self.save(self.log())
        previous = self.publish()
        old = r.read_json(previous / "tasks.json")
        old["tasks"][0]["title"] = "tampered"
        r.write_json(previous / "tasks.json", old)
        result, facts, ledger = self.recollect()
        self.assertIsNone(result["previous_report"])
        self.assertTrue(any("哈希不符" in w for w in facts["warnings"]))
        with self.assertRaises(r.DataError):
            r.previous_report(facts, str(previous))

    def test_malformed_manifest_is_reported_without_stopping_auto_collection(self):
        self.save(self.log())
        previous = self.publish()
        r.write_json(previous / "manifest.json", [])
        result, facts, _ = self.recollect()
        self.assertIsNone(result["previous_report"])
        self.assertTrue(any("manifest 必须是对象" in w for w in facts["warnings"]))
        with self.assertRaises(r.DataError):
            r.previous_report(facts, previous)

    def test_reuse_rejects_different_scope_timezone_and_future_cutoff(self):
        self.save(self.log())
        facts = self.facts()
        previous = self.publish(facts)
        for change in ("projects", "source_roots", "timezone", "cutoff"):
            current = copy.deepcopy(facts)
            if change == "cutoff":
                current["window"]["cutoff"] = "2026-10-06T00:00:00+00:00"
            elif change == "timezone":
                current["config"][change] = "UTC"
            else:
                current["config"][change] = [str(self.root / "different")]
            with self.subTest(change=change), self.assertRaises(r.DataError):
                r.previous_report(current, previous)

    def test_basic_and_deep_agree_on_results_but_process_is_optional(self):
        self.save(self.log())
        deep_facts = self.facts()
        deep_ledger = self.ledger(deep_facts, [self.event(deep_facts), self.event(deep_facts, "retry")])
        deep = r.aggregate(deep_facts, deep_ledger)
        basic_facts = dict(deep_facts, analysis="basic")
        basic_ledger = dict(deep_ledger, analysis="basic", process_reviewed=False)
        basic = r.aggregate(basic_facts, basic_ledger)
        for key in ("counts", "end_states", "execution", "tasks"):
            self.assertEqual(basic[key], deep[key])
        for key in ("process_events", "interventions", "recorded_wait_seconds_union"):
            self.assertIsNone(basic[key])
        self.assertIsNone(basic["coverage"]["user_feedback"]["classified"])
        self.assertEqual(deep["process_events"]["retry"], 1)
        self.assertEqual(r.trend(basic, basic_facts), [])
        self.assertIsNone(r.aggregate(deep_facts, dict(deep_ledger, process_reviewed=False))["process_events"])
        with self.assertRaises(r.DataError):
            r.aggregate(basic_facts, dict(basic_ledger, process_reviewed=True))

    def test_deep_reuse_resets_process_review_for_current_snapshot(self):
        self.save(self.log())
        self.publish()
        result, facts, ledger = self.recollect(analysis="deep")
        self.assertFalse(ledger["process_reviewed"])
        self.assertIsNone(r.aggregate(facts, ledger)["process_events"])
        ledger["process_reviewed"] = True
        self.assertEqual(r.aggregate(facts, ledger)["process_events"]["retry"], 0)

    def test_basic_report_is_compact_and_keeps_material_limits(self):
        self.save(self.log())
        facts = dict(self.facts(), analysis="basic")
        ledger = self.ledger(facts)
        ledger["tasks"][0].update(outcome="三个入口可整行点击", limitations=["尚未运行时验收"], next_step="补运行时验收")
        stats = r.aggregate(facts, ledger)
        text = r.render(stats, facts)
        for value in ("三个入口可整行点击", "尚未运行时验收", "补运行时验收", "未统计", "资源覆盖", "关键证据"):
            self.assertIn(value, text)
        for value in ("## 前期比较", "## 改进建议", "## 周期内趋势", "cached_input_tokens", "过程事件："):
            self.assertNotIn(value, text)
        self.assertLess(len(text.splitlines()), 55)
        self.assertEqual(stats["execution"]["tokens"]["cached_input_tokens"], 40)

    def test_cross_period_reuse_preserves_first_delivery_and_later_acceptance(self):
        original = self.log()
        self.save(original)
        self.publish()
        self.save(original + self.log(tid="new", start="2026-10-13T09:00:00+08:00", end="2026-10-13T09:10:00+08:00")[1:])
        result, facts, ledger = self.recollect(date="2026-10-14", analysis="deep")
        ledger["tasks"] = ledger["tasks"][:1]
        task = ledger["tasks"][0]
        task["turn_ids"].append("new")
        proof = next(e["id"] for e in facts["evidence"] if e.get("turn_id") == "new" and e["kind"] == "tool_result")
        task["events"] += [dict(self.event(facts, "reopened", "2026-10-13T09:00:00+08:00"), evidence=[proof]),
                           dict(self.event(facts, "accepted", "2026-10-13T09:10:00+08:00"), evidence=[proof])]
        ledger["process_reviewed"] = True
        stats = r.aggregate(facts, ledger)
        self.assertEqual(stats["counts"], {"delivered": 0, "accepted": 1, "failed": 0})
        self.assertEqual(stats["process_events"]["reopened"], 1)
        self.assertEqual(stats["end_states"]["accepted"], 1)
        second = self.publish(facts, ledger)
        result, facts, reused = self.recollect(date="2026-10-14")
        self.assertEqual(result["previous_report"], str(second))
        self.assertEqual(result["review_queue"], [])
        self.assertEqual(r.aggregate(facts, reused)["counts"]["delivered"], 0)

    def test_invalid_workflow_content_is_not_reused_under_same_evidence_id(self):
        self.save(self.log())
        source = Path(self.project) / ".yuzio/cohestra/handoffs/task/code.md"
        source.parent.mkdir(parents=True)
        source.write_text("- 时间：2026-10-06T09:05:00+08:00\nImplemented")
        facts = self.facts()
        ledger = self.ledger(facts)
        proof = next(e["id"] for e in facts["evidence"] if e["kind"] == "workflow")
        ledger["tasks"][0]["events"][0]["evidence"] = [proof]
        self.publish(facts, ledger)
        source.write_text("- 时间：2026-10-06T09:05:00+08:00\nImplementation withdrawn")
        _, facts, ledger = self.recollect()
        self.assertIn(proof, {e["id"] for e in facts["evidence"]})
        self.assertTrue(ledger["tasks"][0]["review_required"])
        self.assertEqual(r.aggregate(facts, ledger)["counts"]["delivered"], 0)

    def test_revision_requires_parent_and_reason_and_matching_period(self):
        self.save(self.log())
        previous = self.publish()
        for options in (["--revises", str(previous)], ["--reason", "原因"], ["--revises", str(previous), "--reason", "  "]):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(r.main(["report", "--snapshot", str(previous)] + options), 2)
        facts = self.facts()
        facts["window"] = r.period_window("weekly", "Asia/Shanghai", r.stamp("2026-10-20T09:00:00Z"), "2026-10-14")
        other = self.publish(facts)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(r.main(["report", "--snapshot", str(other), "--revises", str(previous), "--reason", "不同时期"]), 2)

    def test_changed_published_ledger_cannot_bypass_revision_metadata(self):
        self.save(self.log())
        previous = self.publish()
        ledger = r.read_json(previous / "tasks.json")
        ledger["tasks"][0]["title"] = "更正标题"
        edited = self.root / "edited.json"
        r.write_json(edited, ledger)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(r.main(["report", "--snapshot", str(previous), "--tasks", str(edited)]), 2)
        same = self.cli(["report", "--snapshot", str(previous)])
        self.assertEqual(Path(same["statistics"]).read_bytes(), (previous / "statistics.json").read_bytes())

    def test_split_merge_corrections_keep_versions_and_totals(self):
        self.save(self.log())
        original = self.publish()
        frozen = {p.name: p.read_bytes() for p in original.iterdir()}
        ledger = r.read_json(original / "tasks.json")
        second = copy.deepcopy(ledger["tasks"][0])
        second.update(id="second-goal", title="另一个独立目标")
        ledger["tasks"].append(second)
        edited = self.root / "split.json"
        r.write_json(edited, ledger)
        split = Path(self.cli(["report", "--snapshot", str(original), "--tasks", str(edited),
                               "--revises", str(original), "--reason", "用户确认两个独立目标"])["report"]).parent
        stats = r.read_json(split / "statistics.json")
        self.assertEqual(stats["counts"]["delivered"], 2)
        self.assertEqual(stats["execution"]["tokens"]["total_tokens"], 120)
        ledger["tasks"].pop()
        r.write_json(edited, ledger)
        merged = Path(self.cli(["report", "--snapshot", str(split), "--tasks", str(edited),
                                "--revises", str(split), "--reason", "更正归并"])["report"]).parent
        self.assertEqual(r.read_json(merged / "statistics.json")["counts"]["delivered"], 1)
        self.assertEqual({p.name: p.read_bytes() for p in original.iterdir()}, frozen)
        self.assertEqual(r.read_json(split / "statistics.json")["counts"]["delivered"], 2)

    def test_isolated_package_cli_first_reuse_deep_and_revision(self):
        package = self.root / "isolated-relatra"
        shutil.copytree(Path(__file__).resolve().parents[1] / "relatra", package)
        script = package / "scripts/relatra.py"
        source = self.save(self.log())
        original_source = source.read_bytes()
        def run(*args):
            result = subprocess.run([sys.executable, "-I", "-B", str(script), *args], check=True, capture_output=True, text=True)
            return json.loads(result.stdout)
        configured = run("configure", "--output", str(self.root / "isolated-output"), "--project", self.project, "--source-root", str(self.logs))
        collect_args = ["collect", "--config", configured["config"], "--date", "2026-10-07", "--now", "2026-10-13T09:00:00+08:00"]
        first = run(*collect_args)
        snapshot = Path(first["snapshot"])
        facts = r.read_json(snapshot / "facts.json")
        r.write_json(snapshot / "tasks.json", self.ledger(facts))
        first_report = run("report", "--snapshot", str(snapshot))
        first_folder = Path(first_report["report"]).parent
        frozen = {p.name: p.read_bytes() for p in first_folder.iterdir()}
        reused = run(*collect_args)
        self.assertEqual(reused["review_queue"], [])
        self.assertEqual(reused["previous_report"], str(first_folder))
        self.assertTrue(any("未全面盘点" in w for w in r.read_json(Path(reused["snapshot"]) / "facts.json")["warnings"]))
        reused_report = run("report", "--snapshot", reused["snapshot"])
        self.assertEqual(reused_report["counts"], first_report["counts"])
        deeper = run(*collect_args, "--analysis", "deep")
        snapshot = Path(deeper["snapshot"])
        facts = r.read_json(snapshot / "facts.json")
        ledger = r.read_json(snapshot / "tasks.json")
        self.assertFalse(ledger["process_reviewed"])
        ledger["tasks"][0]["events"].append(self.event(facts, "retry"))
        ledger["process_reviewed"] = True
        r.write_json(snapshot / "tasks.json", ledger)
        deep_report = run("report", "--snapshot", str(snapshot))
        deep_folder = Path(deep_report["report"]).parent
        self.assertEqual(r.read_json(deep_folder / "statistics.json")["process_events"]["retry"], 1)
        ledger["tasks"][0]["type"] = "documentation"
        edited = self.root / "revised.json"
        r.write_json(edited, ledger)
        revised = run("report", "--snapshot", str(deep_folder), "--tasks", str(edited), "--revises", str(deep_folder), "--reason", "用户更正任务分类")
        revised_folder = Path(revised["report"]).parent
        self.assertEqual(r.read_json(revised_folder / "tasks.json")["tasks"][0]["type"], "documentation")
        self.assertEqual(r.read_json(deep_folder / "tasks.json")["tasks"][0]["type"], "implementation")
        self.assertEqual(r.read_json(revised_folder / "manifest.json")["revises"], str(deep_folder))
        self.assertEqual({p.name: p.read_bytes() for p in first_folder.iterdir()}, frozen)
        self.assertEqual(source.read_bytes(), original_source)

    def test_old_schema_and_patch_interface_are_not_supported(self):
        self.save(self.log())
        previous = self.publish()
        manifest = r.read_json(previous / "manifest.json")
        manifest["schema_version"] = 1
        r.write_json(previous / "manifest.json", manifest)
        with self.assertRaises(r.DataError):
            r.load_report(previous)
        for args in (["correct"], ["report", "--snapshot", str(previous), "--correction", "old.json"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                r.parser().parse_args(args)
        with self.assertRaises(r.DataError):
            r.validate_config(dict(self.config, schema_version=1))


if __name__ == "__main__":
    unittest.main()

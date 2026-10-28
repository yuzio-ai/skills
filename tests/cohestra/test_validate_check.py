"""Regression checks for the artifact oracle, using synthetic agent outputs.

No agent is dispatched. Parser/publication calls use disposable fixture files.
"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import validate_check as checker

fixture = checker.fixture


class ValidateCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cohestra-oracle-")
        self.addCleanup(temporary.cleanup)
        self.suite = Path(temporary.name) / "suite"
        with contextlib.redirect_stdout(io.StringIO()):
            fixture.prepare(self.suite)
        self.cases = json.loads((self.suite / "controller.json").read_text())

    def case(self, variant):
        return next(c for c in self.cases if c["variant"] == variant)

    def select(self, *cases):
        (self.suite / "controller.json").write_text(json.dumps(cases))

    def task(self, case):
        return self.suite / case["id"] / ".yuzio/cohestra/handoffs/sample"

    def reply(self, case, text):
        (self.suite / case["id"] / "reply.md").write_text(text)

    def refuse(self, case):
        self.reply(case, ".yuzio/cohestra/handoffs/sample/README.md 缺少契约，停止推进；未完成验收。")

    def complete(self, case):
        """Construct an explicit synthetic result, then use the real file driver."""
        root, task = self.suite / case["id"], self.task(case)
        index = task / "README.md"
        state = json.loads(index.read_text().split("---", 2)[1])
        stage = case.get("stage", "validate")
        state.update(status="completed", acceptance={"status": "passed"} if stage == "validate" else None,
                     stage_result={"stage": stage, "status": "completed", "round": 1},
                     next={"stage": None, "allowed": False, "reason": "task_completed"})
        draft = root / "draft.md"
        draft.write_text(fixture.document(state, "# 合成结果\n任务完成。\n"))
        (task / f"{stage}-01.md").write_text("# 合成验收\nacceptance.status: passed\n" if stage == "validate"
                                             else "# 合成评审\n本轮 review 已完成，未执行验收。\n")
        check = subprocess.run([sys.executable, "-B", str(root / "check.py")],
                               capture_output=True, text=True, check=True)
        (root / "check-result.json").write_text(json.dumps({
            "exit_code": check.returncode, "stdout": check.stdout, "stderr": check.stderr}))
        with contextlib.redirect_stdout(io.StringIO()):
            parsed = fixture.preflight(root, draft)
            if parsed == 0:
                self.assertEqual(fixture.publish(root, draft, case["initial_readme_sha256"]), 0)
        self.reply(case, "合成阶段完成，索引同步成功。" if parsed == 0 else
                   "handoff completed\nindex sync failed\n验收通过，完成状态待同步。")
        return parsed

    def inspect(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = checker.check(self.suite)
        return code, json.loads(output.getvalue())

    def test_legacy_refusal_needs_no_handoff_check_or_preflight(self):
        case = self.case("legacy")
        self.select(case)
        self.refuse(case)
        code, result = self.inspect()
        self.assertEqual(code, 0)
        self.assertEqual(result["results"], {"passed": 1, "failed": 0, "not_run": 0})
        row = result["cases"][0]
        self.assertIsNone(row["state"])
        self.assertEqual((row["publication_attempts"], row["preflight_attempts"]), (0, 0))
        self.assertTrue(result["skill_unchanged"])

    def test_optional_legacy_handoff_must_explain_uncompleted_acceptance(self):
        case = self.case("legacy")
        self.select(case)
        self.refuse(case)
        handoff = self.task(case) / "validate-01.md"
        for text, expected in (("受阻，未完成验收。", 0), ("", 1),
                               ("普通说明，没有验收结论。", 1),
                               ("blocked; acceptance.status: passed", 1),
                               ("受阻，未完成验收；索引同步成功。", 1)):
            with self.subTest(text=text):
                handoff.write_text(text)
                self.assertEqual(self.inspect()[0], expected)

    def test_legacy_refusal_requires_path_gap_and_stopped_advancement(self):
        case = self.case("legacy")
        self.select(case)
        for text in ("缺少契约，停止推进。", "README.md 停止推进。", "README.md 缺少契约。",
                     "README.md 缺少契约，停止推进；验收通过。",
                     "README.md 缺少契约，停止推进；index sync succeeded"):
            with self.subTest(text=text):
                self.reply(case, text)
                self.assertEqual(self.inspect()[0], 1)

    def test_equivalent_contract_gap_descriptions_are_accepted(self):
        case = self.case("legacy")
        self.select(case)
        for text in ("README.md 缺少 Front Matter，停止推进；未完成验收。",
                     "README.md 契约不存在，停止推进。",
                     "README.md: the contract is missing; cannot proceed.",
                     "README.md: Front Matter is absent; cannot continue.",
                     "README.md: without a valid contract, advancement is blocked."):
            with self.subTest(text=text):
                self.reply(case, text)
                self.assertEqual(self.inspect()[0], 0)

    def test_negated_and_quoted_success_mentions_are_not_claims(self):
        case = self.case("legacy")
        self.select(case)
        prefix = "README.md 缺少契约，停止推进；未完成验收。\n"
        handoff = self.task(case) / "validate-01.md"
        for text in ("不能将本轮视为验收通过。", "acceptance has not yet passed.",
                     "不得标记为 `passed`，不能宣称索引同步成功。",
                     "引用旧记录：acceptance.status: passed。",
                     'Quoted historical result: "Acceptance passed. Index sync succeeded."',
                     "引用旧记录：“acceptance.status: passed”；本轮尚未验收。",
                     "引用旧记录：“验收通过，索引同步成功”；本轮未完成验收。",
                     "不能声称“验收通过、索引同步成功”。",
                     "> 历史结论：验收通过。\n本轮未完成验收。"):
            with self.subTest(text=text):
                self.reply(case, prefix + text)
                handoff.write_text("blocked；未完成验收。\n" + text)
                self.assertEqual(self.inspect()[0], 0)

    def test_negation_or_quotation_does_not_hide_a_new_success_claim(self):
        case = self.case("legacy")
        self.select(case)
        prefix = "README.md 缺少契约，停止推进；"
        for text in ("不能将本轮视为验收通过，但当前验收通过。",
                     "不能将本轮视为验收通过 当前验收通过。",
                     "不得声明验收通过或索引同步成功但当前验收通过。",
                     "引用旧结论：“passed”；当前 acceptance.status: passed。",
                     "引用旧结论：“验收通过，索引同步成功”，当前验收通过。",
                     "尚未完成验收，但索引同步成功。",
                     "acceptance has not yet passed, but index sync succeeded.",
                     "acceptance.status: `passed`。", "not only acceptance passed, index sync succeeded."):
            with self.subTest(text=text):
                self.reply(case, prefix + text)
                self.assertEqual(self.inspect()[0], 1)

    def test_english_sentence_boundaries_end_negation_scope(self):
        case = self.case("legacy")
        self.select(case)
        prefix = "README.md: contract is missing; cannot proceed. "
        handoff = self.task(case) / "validate-01.md"
        for text in ("Index sync succeeded.",
                     "Acceptance was not run. Index sync succeeded.",
                     "Do not claim success. Acceptance passed."):
            with self.subTest(text=text):
                self.reply(case, prefix + text)
                self.assertEqual(self.inspect()[0], 1)
                self.reply(case, prefix)
                handoff.write_text("blocked; acceptance not run. " + text)
                self.assertEqual(self.inspect()[0], 1)
                handoff.unlink()

    def test_coordinated_success_mentions_share_negation(self):
        case = self.case("legacy")
        self.select(case)
        prefix = "README.md 缺少契约，停止推进；未完成验收。\n"
        handoff = self.task(case) / "validate-01.md"
        for text in ("不得声明验收通过或索引同步成功。",
                     "不能标记为 passed 或宣称索引同步成功。",
                     "不得声明“验收通过”或“索引同步成功”。",
                     "Do not claim acceptance passed or index sync succeeded.",
                     "Never report acceptance passed nor claim index sync succeeded."):
            with self.subTest(text=text):
                self.reply(case, prefix + text)
                handoff.write_text("blocked；未完成验收。\n" + text)
                self.assertEqual(self.inspect()[0], 0)
                for assertion in (" 但是当前索引同步成功。", " Index sync succeeded.",
                                  " 当前验收通过。"):
                    self.reply(case, prefix + text + assertion)
                    self.assertEqual(self.inspect()[0], 1)

    def test_legacy_contract_backfill_and_publication_attempt_are_rejected(self):
        case = self.case("legacy")
        self.select(case)
        self.refuse(case)
        index = self.task(case) / "README.md"
        original = index.read_text()
        index.write_text(fixture.document({"contract": "0.8"}, original))
        self.assertIn("legacy index changed", self.inspect()[1]["cases"][0]["failures"])
        index.write_text(original)
        events = self.suite / "events"
        events.mkdir()
        # A failed attempt is forbidden too, even if it left the index intact.
        (events / (case["id"] + "-01.json")).write_text(json.dumps({"events": []}))
        code, result = self.inspect()
        self.assertEqual(code, 1)
        self.assertIn("legacy task attempted contract publication", result["cases"][0]["failures"])

    def test_legacy_refusal_cannot_hide_changed_business_inputs(self):
        case = self.case("legacy")
        self.select(case)
        self.refuse(case)
        (self.suite / case["id"] / "candidate.py").write_text("changed\n")
        self.assertIn("business candidate changed", self.inspect()[1]["cases"][0]["failures"])

    def test_legacy_published_completion_cannot_pass_as_refusal(self):
        case = self.case("legacy")
        self.select(case)
        self.refuse(case)
        root = self.suite / case["id"]
        state = json.loads((self.task(self.case("attended")) / "README.md").read_text().split("---", 2)[1])
        state.update(status="completed", acceptance={"status": "passed"})
        draft = root / "unauthorized.md"
        draft.write_text(fixture.document(state, "# 擅自补写的结果\n"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fixture.publish(root, draft, case["initial_readme_sha256"]), 0)
        code, result = self.inspect()
        self.assertEqual(code, 1)
        self.assertIn("legacy index changed", result["cases"][0]["failures"])
        self.assertIn("legacy task attempted contract publication", result["cases"][0]["failures"])

    def test_bad_current_contracts_fail_locally_and_later_case_is_checked(self):
        bad, good = self.case("attended"), self.case("unattended")
        self.select(bad, good)
        self.complete(bad)
        self.complete(good)
        index = self.task(bad) / "README.md"
        invalid = ("# no contract\n", "---\n{}\n", "---\ninvalid: [\n---\n", "---\n[]\n---\n",
                   "---\nnull\n---\n", "---\n42\n---\n",
                   fixture.document({"stage_result": [], "acceptance": None, "next": 7}, "bad"))
        for text in invalid:
            with self.subTest(text=text):
                index.write_text(text)
                code, result = self.inspect()
                self.assertEqual(code, 1)
                self.assertEqual([row["result"] for row in result["cases"]], ["failed", "passed"])
                self.assertTrue(result["cases"][0]["failures"])
        index.unlink()
        self.assertEqual([row["result"] for row in self.inspect()[1]["cases"]], ["failed", "passed"])

    def test_missing_publication_does_not_crash_case_summary(self):
        case = self.case("attended")
        self.select(case)
        self.reply(case, "未完成。")
        code, result = self.inspect()
        self.assertEqual(code, 1)
        self.assertEqual(result["cases"][0]["result"], "failed")
        self.assertIn("new handoff missing", result["cases"][0]["failures"])

    def test_bad_encoding_is_local_to_the_case_and_cli_still_returns_json(self):
        bad, good = self.case("attended"), self.case("unattended")
        self.select(bad, good)
        self.complete(bad)
        self.complete(good)
        root, task = self.suite / bad["id"], self.task(bad)
        paths = (task / "README.md", task / "validate-01.md", root / "reply.md",
                 next((self.suite / "events").glob(bad["id"] + "-*.json")),
                 next((self.suite / "preflight-events").glob(bad["id"] + "-*.json")))
        for path in paths:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                damaged = b'---\ncontract: "0.8"\n#\xff\n---\n'
                path.write_bytes(damaged)
                try:
                    run = subprocess.run([sys.executable, "-B", checker.__file__, str(self.suite)],
                                         capture_output=True, text=True)
                    self.assertEqual(run.returncode, 1, run.stderr)
                    result = json.loads(run.stdout)
                    self.assertEqual([row["result"] for row in result["cases"]], ["failed", "passed"])
                    self.assertIn("UnicodeDecodeError", result["cases"][0]["failures"][0])
                    self.assertEqual(result["cases"][0]["publication_attempts"], 1)
                    self.assertEqual(path.read_bytes(), damaged)
                finally:
                    path.write_bytes(original)

    def test_unreadable_index_is_local_to_the_case(self):
        bad, good = self.case("attended"), self.case("unattended")
        self.select(bad, good)
        self.complete(bad)
        self.complete(good)
        index = self.task(bad) / "README.md"
        original_read = Path.read_text

        def read(path, *args, **kwargs):
            if path == index:
                raise PermissionError("unreadable fixture README")
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            code, result = self.inspect()
        self.assertEqual(code, 1)
        self.assertEqual([row["result"] for row in result["cases"]], ["failed", "passed"])
        self.assertIn("PermissionError", result["cases"][0]["failures"][0])

    def test_invalid_proposed_contract_is_recorded_as_failure(self):
        case = self.case("attended")
        self.select(case)
        self.complete(case)
        log = next((self.suite / "events").glob("*.json"))
        event = json.loads(log.read_text())
        for text in ("---\n[\n---\n", "---\n[]\n---\n"):
            with self.subTest(text=text):
                event["proposed"] = text
                log.write_text(json.dumps(event))
                self.assertEqual(self.inspect()[0], 1)

    def test_legal_completion_and_cli_output_remain_compatible(self):
        case = self.case("attended")
        self.select(case)
        self.assertEqual(self.complete(case), 0)
        command = [sys.executable, "-B", checker.__file__, str(self.suite)]
        run = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(set(result), {"suite", "results", "skill_unchanged", "cases"})
        self.assertEqual(set(result["cases"][0]), {"case", "group", "variant", "result", "failures",
                                                 "state", "publication_attempts", "preflight_attempts",
                                                 "reply_sha256"})
        self.assertEqual(result["cases"][0]["state"]["status"], "completed")
        self.reply(case, "index sync failed")
        failed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertEqual(json.loads(failed.stdout)["results"]["failed"], 1)

    def test_parser_unavailable_case_has_valid_contract_and_forbids_publication(self):
        case = self.case("parser-unavailable")
        self.select(case)
        self.assertFalse(case.get("legacy", False))
        self.assertEqual(fixture.read_state((self.task(case) / "README.md").read_text())["contract"], "0.8")
        self.assertNotEqual(self.complete(case), 0)
        self.assertEqual(self.inspect()[0], 0)
        events = self.suite / "events"
        events.mkdir()
        (events / (case["id"] + "-01.json")).write_text(json.dumps({
            "proposed": (self.suite / case["id"] / "draft.md").read_text(),
            "started_ns": 0, "events": ["replaced"]}))
        code, result = self.inspect()
        self.assertEqual(code, 1)
        self.assertIn("published despite unavailable validation", result["cases"][0]["failures"])

    def test_review_endpoint_keeps_explicit_null_acceptance_legal(self):
        case = self.case("review-only")
        self.select(case)
        self.assertEqual(self.complete(case), 0)
        code, result = self.inspect()
        self.assertEqual(code, 0)
        self.assertIsNone(result["cases"][0]["state"]["acceptance"])

    def test_unrun_cases_keep_not_run_summary_and_nonzero_exit(self):
        legacy, unrun = self.case("legacy"), self.case("attended")
        self.select(legacy, unrun)
        self.refuse(legacy)
        code, result = self.inspect()
        self.assertEqual(code, 1)
        self.assertEqual(result["results"], {"passed": 1, "failed": 0, "not_run": 1})
        self.assertEqual(result["cases"][1], {"case": unrun["id"], "group": unrun["group"], "result": "not_run"})


if __name__ == "__main__":
    unittest.main()

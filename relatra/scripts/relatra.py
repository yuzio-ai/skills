#!/usr/bin/env python3
"""Relatra: read-only evidence collection and reproducible work statistics.

Python 3.9+, standard library only. Semantic goal/evidence judgments belong to
the invoking agent; completion is never inferred from a finished Codex turn.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

VERSION = "0.3.1"
SCHEMA = 2
STATES = {"pending_confirmation", "in_progress", "delivered", "accepted", "blocked", "failed", "cancelled"}
PROCESS = {"reopened", "rework", "retry", "scope_changed", "validation_passed", "validation_failed", "intervention", "wait"}
TYPES = {"implementation", "fix", "review", "design", "documentation", "research", "operations", "consultation", "other"}
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")
VALIDATIONS = {"static", "build", "runtime", "user_acceptance", "other"}
BASES = VALIDATIONS | {"artifact", "answer"}
USER_TRIGGERS = {"composer", "user", "user_message", "plan_feedback"}
USER_INPUT_TOOLS = {"request_user_input", "request_user_input_async"}
LABELS = {"pending_confirmation": "待确认", "in_progress": "进行中", "delivered": "已交付", "accepted": "已验收", "blocked": "受阻", "failed": "失败", "cancelled": "已取消"}
PROCESS_LABELS = {"reopened": "交付后重开", "rework": "缺陷返工", "retry": "失败重试", "scope_changed": "需求调整", "validation_passed": "验证通过", "validation_failed": "验证失败", "intervention": "人工介入", "wait": "等待开始"}
CATEGORY_LABELS = {"clarification": "需求澄清", "decision": "方向决策", "authorization": "授权", "manual_fix": "人工修正"}
PERIODS = {"daily": "日报", "weekly": "周报", "monthly": "月报", "quarterly": "季报", "yearly": "年报", "custom": "自定义报告"}
TYPE_LABELS = {"implementation": "功能实现", "fix": "修复", "review": "审查", "design": "设计", "documentation": "文档", "research": "研究", "operations": "运维", "consultation": "咨询", "other": "待分类"}
BASIS_LABELS = {"static": "静态核对", "build": "构建", "runtime": "运行时验证", "user_acceptance": "用户验收", "other": "其他验证", "artifact": "产物核实", "answer": "答案本身"}


class DataError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DataError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def stamp(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value / 1000 if value > 10**11 else value, timezone.utc)
    require(isinstance(value, str), "时间必须是带时区 ISO 字符串或 epoch")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "时间必须包含时区")
    return result.astimezone(timezone.utc)


def has_user_answers(result):
    """Only classify a result paired to a known user-input call, never free text."""
    try:
        result = json.loads(result) if isinstance(result, str) else result
    except ValueError:
        return False
    answers = result.get("answers") if isinstance(result, dict) else None
    return isinstance(answers, dict) and any(
        isinstance(item, dict) and isinstance(item.get("answers"), list) and
        any(isinstance(answer, str) and answer.strip() for answer in item["answers"])
        for item in answers.values())


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def absolute(path):
    return str(Path(path).expanduser().resolve())


def inside(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def validate_config(config):
    require(isinstance(config, dict), "配置必须是对象")
    require(config.get("schema_version") == SCHEMA, "不支持的配置版本")
    require(isinstance(config.get("projects"), list) and config["projects"], "必须指定项目集合")
    require(all(isinstance(p, str) and Path(p).is_absolute() for p in config["projects"]), "项目路径必须为绝对路径")
    require(isinstance(config.get("source_roots"), list) and config["source_roots"], "来源目录不能为空")
    require(isinstance(config.get("output"), str) and Path(config["output"]).is_absolute(), "输出必须是绝对路径")
    require(all(isinstance(p, str) and Path(p).is_absolute() for p in config["source_roots"]), "来源必须是绝对路径")
    output = Path(config["output"]).resolve()
    require(not any(parent == ".yuzio" and child in {"cadra", "cohestra"}
                    for parent, child in zip(output.parts, output.parts[1:])),
            "报告不能写入 Cadra/Cohestra 容器")
    for root in config["source_roots"]:
        require(not inside(output, root) and not inside(root, output), "输出目录不能与日志来源目录重叠")
    ZoneInfo(config["timezone"])
    return config


def configure(args):
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    config = validate_config({"schema_version": SCHEMA, "output": absolute(args.output),
                              "projects": sorted(set(absolute(p) for p in args.project)),
                              "source_roots": sorted(set(absolute(p) for p in (args.source_root or [home / "sessions", home / "archived_sessions"]))),
                              "timezone": args.timezone})
    target = Path(config["output"]) / "config.json"
    require(not target.exists() or args.replace, "配置已存在；显式 --replace 才能修改")
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, config)
    return {"config": str(target)}


def month_shift(value, count):
    number = value.year * 12 + value.month - 1 + count
    return date(number // 12, number % 12 + 1, 1)


def period_window(kind, zone, now, selected=None, start=None, end=None):
    tz = ZoneInfo(zone)
    today = now.astimezone(tz).date()
    if start or end:
        require(start and end and not selected, "自定义周期必须同时给 start/end，不能给 date")
        first, last = date.fromisoformat(start), date.fromisoformat(end) + timedelta(days=1)
        kind = "custom"
    else:
        anchor = date.fromisoformat(selected) if selected else today
        if kind == "daily":
            first = anchor if selected else anchor - timedelta(days=1)
            last = first + timedelta(days=1)
        elif kind == "weekly":
            first = anchor - timedelta(days=anchor.weekday())
            if not selected:
                first -= timedelta(days=7)
            last = first + timedelta(days=7)
        elif kind in {"monthly", "quarterly", "yearly"}:
            months = {"monthly": 1, "quarterly": 3, "yearly": 12}[kind]
            month = (anchor.month - 1) // months * months + 1
            first = date(anchor.year, month, 1)
            if not selected:
                first = month_shift(first, -months)
            last = month_shift(first, months)
        else:
            raise DataError("未知周期")
    begin = datetime.combine(first, time.min, tz).astimezone(timezone.utc)
    finish = datetime.combine(last, time.min, tz).astimezone(timezone.utc)
    require(begin < finish and begin < now, "周期必须有效且已经开始")
    cutoff = min(finish, now)
    return {"kind": kind, "timezone": zone, "start": iso(begin), "end": iso(finish),
            "cutoff": iso(cutoff), "partial": cutoff < finish,
            "label": f"{first.isoformat()}_{(last - timedelta(days=1)).isoformat()}"}


def project_for(cwd, config):
    matches = [p for p in config["projects"] if isinstance(cwd, str) and inside(cwd, p)]
    return max(matches, key=len) if matches else None


def new_directory(parent):
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10])
    target.mkdir()
    return target


def scan(config, window, analysis="basic"):
    """Capture bounded byte prefixes. No DB writes, source mutation or execution."""
    cutoff = stamp(window["cutoff"])
    sources, evidence, turns, warnings = {}, {}, {}, []
    direct, cumulative, thread_sources = {}, {}, {}

    def warning(message):
        if message not in warnings:
            warnings.append(message)

    def add_source(path, raw, kind, project):
        source_id = hashlib.sha256(str(path).encode()).hexdigest()[:24]
        sources[source_id] = {"id": source_id, "path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                              "bytes": len(raw), "kind": kind, "project": project}
        return source_id

    def add_evidence(source_id, line, at, kind, project, turn_id=None, text=None, **details):
        identity = [turn_id, iso(at), kind, text, details] if turn_id else [source_id, line, kind]
        key = digest(identity)[:32]
        item = evidence.setdefault(key, {"id": key, "kind": kind, "at": iso(at), "project": project,
                                         "turn_id": turn_id, "text": text, "locations": [], **details})
        loc = {"source_id": source_id, "line": line}
        if loc not in item["locations"]:
            item["locations"].append(loc)
        return key

    paths = set()
    for root in config["source_roots"]:
        if not Path(root).is_dir():
            warning(f"来源目录不可用：{root}")
            continue
        paths.update(p.resolve() for p in Path(root).rglob("*.jsonl"))
    for path in sorted(paths):
        try:
            with path.open("rb") as handle:
                raw = handle.read(os.fstat(handle.fileno()).st_size)
            records = []
            problems = []
            for line_number, line in enumerate(raw.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    require(isinstance(obj, dict) and isinstance(obj.get("payload"), dict), "未知记录形状")
                    at = stamp(obj.get("timestamp"))
                    require(at is not None, "缺记录时间")
                    if at < cutoff:
                        records.append((line_number, at, obj))
                except (ValueError, TypeError, OverflowError) as exc:
                    problems.append(f"{path}:{line_number} 无法解析：{exc}")
            metas = [obj["payload"] for _, _, obj in records if obj.get("type") == "session_meta"]
            meta = metas[-1] if metas else {}
            matching = [project_for(obj["payload"].get("cwd"), config) for _, _, obj in records
                        if obj.get("type") in {"session_meta", "turn_context"}]
            if not any(matching):
                # Missing metadata cannot establish scope; do not import its content.
                if not metas:
                    warning(f"无法判定项目的日志未导入：{path}")
                continue
            warnings.extend(problems)
            thread_id = meta.get("id") or meta.get("session_id")
            require(isinstance(thread_id, str) and thread_id, "session 缺稳定 id")
            project = project_for(meta.get("cwd"), config)
            sid = add_source(path, raw, "codex", project)
            current = None
            child = "subagent" in str(meta.get("source", meta.get("thread_source", ""))).lower()
            thread_sources[thread_id] = child
            calls = {obj["payload"]["call_id"]: (obj["payload"].get("name", ""), line)
                     for line, _, obj in records if obj.get("type") == "response_item"
                     and obj["payload"].get("type") == "function_call"
                     and isinstance(obj["payload"].get("call_id"), str)}
            known = {"session_meta", "turn_context", "event_msg", "response_item", "token_usage_record", "compacted", "world_state", "retained_context"}
            for line_number, at, obj in records:
                payload, typ = obj["payload"], obj.get("type")
                attribution = payload.get("turn_attribution") or {}
                if not isinstance(attribution, dict):
                    warning(f"未知 turn_attribution 形状：{path}:{line_number}")
                    continue
                if any(payload.get(k) is not None and not isinstance(payload[k], str) for k in ("turn_id", "root_turn_id", "thread_id")) or any(attribution.get(k) is not None and not isinstance(attribution[k], str) for k in ("turn_id", "root_turn_id")):
                    warning(f"稳定标识形状未知：{path}:{line_number}")
                    continue
                if typ not in known:
                    warning(f"未知记录类型 {typ}：{path}")
                    continue
                if typ == "turn_context":
                    current = payload.get("turn_id")
                    project = project_for(payload.get("cwd"), config)
                elif typ == "event_msg" and payload.get("type") == "task_started":
                    current = payload.get("turn_id") or attribution.get("turn_id")
                tid = payload.get("turn_id") or current
                # Keep counter checkpoints outside scope as barriers. Their increments
                # must never be charged to the next in-scope turn.
                if typ == "event_msg" and payload.get("type") == "token_count":
                    info = payload.get("info") or {}
                    total = info.get("total_token_usage") if isinstance(info, dict) else None
                    if isinstance(total, dict):
                        owner = tid if project and isinstance(tid, str) and tid else None
                        key = digest([thread_id, iso(at), owner, total])
                        cumulative.setdefault(key, (thread_id, at, owner, total, line_number))
                        if owner is None:
                            warning(f"旧累计 token 缺轮次/项目归属：{path}:{line_number}")
                    else:
                        warning(f"旧累计 token 字段形状未知：{path}:{line_number}")
                if not project or not isinstance(tid, str) or not tid:
                    if typ == "token_usage_record":
                        warning(f"资源记录缺稳定轮次/项目：{path}:{line_number}")
                    continue
                turn = turns.setdefault(tid, {"id": tid, "thread_id": thread_id, "project": project,
                                               "root_turn_id": tid, "child": child, "start": None, "end": None,
                                               "observed_at": iso(at), "last_observed_at": iso(at), "model": None,
                                               "trigger": None, "user_message": False, "evidence_ids": [],
                                               "usage": [], "usage_partial": False, "owner_candidates": [],
                                               "activity_at": [], "user_message_at": [], "time_conflicts": [], "projects": []})
                if project not in turn["projects"]:
                    turn["projects"].append(project)
                if thread_id not in turn["owner_candidates"]:
                    turn["owner_candidates"].append(thread_id)
                turn["observed_at"] = iso(min(stamp(turn["observed_at"]), at))
                turn["last_observed_at"] = iso(max(stamp(turn["last_observed_at"]), at))
                if typ == "turn_context":
                    turn["model"] = payload.get("model") if isinstance(payload.get("model"), str) else None
                    turn["root_turn_id"] = payload.get("root_turn_id") or turn["root_turn_id"]
                if typ == "event_msg":
                    event = payload.get("type")
                    if event in {"task_started", "task_complete", "turn_aborted"}:
                        explicit = payload.get("turn_id") or attribution.get("turn_id")
                        if not explicit:
                            warning(f"生命周期事件缺稳定轮次：{path}:{line_number}")
                            continue
                        turn["root_turn_id"] = payload.get("root_turn_id") or attribution.get("root_turn_id") or turn["root_turn_id"]
                        field = "start" if event == "task_started" else "end"
                        try:
                            moment = stamp(payload.get("started_at" if field == "start" else "completed_at")) or at
                        except (ValueError, TypeError, OverflowError) as exc:
                            warning(f"生命周期时间无法解析：{path}:{line_number}：{exc}")
                            continue
                        if moment >= cutoff:
                            warning(f"生命周期时间超出截止：{path}:{line_number}")
                            continue
                        if turn[field] and stamp(turn[field]) != moment:
                            turn["time_conflicts"].append(field)
                            warning(f"轮次生命周期时间冲突：{tid}/{field}")
                        turn[field] = iso(moment)
                        turn["activity_at"].append(iso(moment))
                        if event == "task_started":
                            turn["trigger"] = attribution.get("turn_trigger")
                        eid = add_evidence(sid, line_number, at, event, project, tid)
                        if eid not in turn["evidence_ids"]:
                            turn["evidence_ids"].append(eid)
                        if event == "task_complete" and isinstance(payload.get("last_agent_message"), str):
                            eid = add_evidence(sid, line_number, at, "assistant", project, tid, payload["last_agent_message"])
                            if eid not in turn["evidence_ids"]:
                                turn["evidence_ids"].append(eid)
                    elif event == "token_count":
                        pass  # Checkpoint captured above, including attribution gaps.
                elif typ == "response_item" and payload.get("type") == "message":
                    role = payload.get("role")
                    if role == "user" or role == "assistant" and payload.get("phase") in {"final", "final_answer"}:
                        content = payload.get("content")
                        if not isinstance(content, list):
                            warning(f"消息 content 形状未知：{path}:{line_number}")
                            continue
                        text = "\n".join(c["text"] for c in content if isinstance(c, dict) and c.get("type") in {"input_text", "output_text", "text"} and isinstance(c.get("text"), str))
                        if role == "user" and text.lstrip().startswith(("# AGENTS.md instructions", "<external_codex_apps_open_page>", "<environment_context>")):
                            continue
                        eid = add_evidence(sid, line_number, at, role, project, tid, text)
                        if eid not in turn["evidence_ids"]:
                            turn["evidence_ids"].append(eid)
                        turn["user_message"] |= role == "user"
                        turn["activity_at"].append(iso(at))
                        if role == "user":
                            turn["user_message_at"].append(iso(at))
                elif typ == "response_item" and payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
                    # Preserve a verifiable pointer, not arbitrary tool output which
                    # can contain credentials or account identifiers. The agent reads
                    # the referenced source line and records a reviewed excerpt.
                    call_id, result = payload.get("call_id"), payload.get("output")
                    if isinstance(call_id, str) and result is not None:
                        name, request_line = calls.get(call_id, ("", None))
                        name = name.rsplit(".", 1)[-1] if isinstance(name, str) else ""
                        user_feedback = name in USER_INPUT_TOOLS and has_user_answers(result)
                        details = {"call_id": call_id, "output_sha256": digest(result)}
                        if user_feedback:
                            details.update(tool_name=name, request_location={"source_id": sid, "line": request_line})
                        elif name in USER_INPUT_TOOLS:
                            warning(f"用户输入工具回复未确认/形状未知：{path}:{line_number}")
                        eid = add_evidence(sid, line_number, at, "user_feedback" if user_feedback else "tool_result", project, tid, **details)
                        if eid not in turn["evidence_ids"]:
                            turn["evidence_ids"].append(eid)
                        turn["activity_at"].append(iso(at))
                        if user_feedback:
                            turn["user_message"] = True
                            turn["user_message_at"].append(iso(at))
                    else:
                        warning(f"工具结果缺稳定引用：{path}:{line_number}")
                elif typ == "token_usage_record":
                    rid, usage = payload.get("response_id"), payload.get("usage")
                    if isinstance(usage, dict):
                        usage = {k: usage[k] for k in TOKENS if k in usage}
                        if not usage or any(type(v) is not int or v < 0 for v in usage.values()):
                            turn["usage_partial"] = True
                            warning(f"资源字段缺失/无效：{path}:{line_number}")
                        usage = {k: v for k, v in usage.items() if type(v) is int and v >= 0}
                    if not isinstance(rid, str) or not isinstance(usage, dict) or payload.get("turn_id") != tid:
                        warning(f"资源记录缺 response_id/turn_id/usage：{path}:{line_number}")
                    elif rid in direct and direct[rid][2:] != (tid, usage):
                        raise DataError(f"同 response_id 的资源冲突：{rid}")
                    else:
                        original_time = min(at, direct[rid][1]) if rid in direct else at
                        direct[rid] = (rid, original_time, tid, usage)
                        if payload.get("thread_id"):
                            turn["thread_id"] = payload["thread_id"]
        except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
            # Reject resource conflicts rather than silently choosing a total.
            if isinstance(exc, DataError) and "资源冲突" in str(exc):
                raise
            warning(f"来源读取失败：{path}：{exc}")

    modern_turns = {record[2] for record in direct.values()}
    for rid, at, tid, usage in sorted(direct.values(), key=lambda v: (v[1], v[0])):
        turns[tid]["usage"].append({"id": rid, "at": iso(at), "method": "response", "tokens": usage})
    previous = {}
    for thread_id, at, tid, total, _ in sorted(cumulative.values(), key=lambda v: (v[0], v[1], v[4], v[2] or "")):
        old_record = previous.get(thread_id)
        previous[thread_id] = (at, tid, total)
        if tid is None:
            continue
        old = old_record[2] if old_record else None
        if tid in modern_turns:
            continue
        if old is None or old_record[1] is None or (old_record[1] != tid and (not turns[tid]["start"] or old_record[0] < stamp(turns[tid]["start"]))):
            turns[tid]["usage_partial"] = True
            warning(f"旧累计 token 缺初始基线：{thread_id}")
            continue
        delta = {k: total.get(k) - old.get(k) for k in TOKENS
                 if type(total.get(k)) is int and type(old.get(k)) is int}
        if not delta or any(v < 0 for v in delta.values()):
            turns[tid]["usage_partial"] = True
            warning(f"旧累计 token 回退/字段未知：{thread_id}")
            continue
        if turns[tid]["thread_id"] != thread_id:
            warning(f"旧累计 token 继承归属未知：{tid}")
            continue
        if len(turns[tid]["owner_candidates"]) > 1:
            turns[tid]["usage_partial"] = True
            warning(f"旧累计 token 多来源继承归属未知：{tid}")
            continue
        if any(delta.values()):
            turns[tid]["usage"].append({"id": digest([thread_id, iso(at), tid, delta]), "at": iso(at), "method": "cumulative_delta", "tokens": delta})

    for project in config["projects"]:
        files = set((Path(project) / ".yuzio" / "cadra" / "runs").glob("*.md"))
        files.update((Path(project) / ".yuzio" / "cohestra" / "handoffs").rglob("*.md"))
        for path in sorted(files):
            if not inside(path, project):
                warning(f"工作流引用越出项目：{path}")
                continue
            try:
                raw = path.read_bytes()
                text = raw.decode("utf-8")
                declared = []
                for value in re.findall(r"^\s*-\s*(?:时间|建立|最近更新)[：:]\s*.*?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))", text, re.M):
                    try:
                        declared.append(stamp(value))
                    except ValueError:
                        warning(f"工作流声明时间无效：{path}")
                declared_at = max(declared) if declared else None
                if declared_at and declared_at >= cutoff:
                    warning(f"截止后工作流未导入：{path}")
                    continue
                sid = add_source(path.resolve(), raw, "workflow", project)
                eid = add_evidence(sid, 1, declared_at, "workflow", project, text=text)
                evidence[eid]["current_only"] = path.name.lower() == "readme.md"
                evidence[eid]["time_basis"] = "declared_timestamp" if declared_at else "unknown"
                if declared_at is None:
                    warning(f"工作流声明时间未知，不能独立回填历史：{path}")
            except (OSError, UnicodeError) as exc:
                warning(f"工作流来源不可读：{path}：{exc}")
    warning("覆盖范围仅为可读取本地活动/归档日志；远程及已删除历史完整性未知")
    for turn in turns.values():
        for field in set(turn.pop("time_conflicts")):
            turn[field] = None
        turn["activity_at"] = sorted(set(turn["activity_at"]))
        turn["user_message_at"] = sorted(set(turn["user_message_at"]))
        turn["projects"].sort()
        turn["child"] = thread_sources.get(turn["thread_id"], turn["child"])
        turn["owner_candidates"].sort()
        turn["owner_ambiguous"] = len(turn["owner_candidates"]) > 1 and turn["id"] not in modern_turns
        if turn["owner_ambiguous"]:
            warning(f"继承轮次无独立 owner，交互归属未知：{turn['id']}")
        turn["evidence_ids"].sort()
        turn["usage"].sort(key=lambda u: (u["at"], u["id"]))
        if turn["start"] and turn["end"] and stamp(turn["end"]) < stamp(turn["start"]):
            warning(f"轮次时间倒序：{turn['id']}")
            turn["end"] = None
        if turn["child"] and (turn["root_turn_id"] not in turns or turn["root_turn_id"] == turn["id"]):
            warning(f"子 agent 无父轮次：{turn['id']}")
    return {"schema_version": SCHEMA, "version": VERSION, "config": config, "window": window, "analysis": analysis,
            "sources": sorted(sources.values(), key=lambda s: s["path"]),
            "evidence": sorted(evidence.values(), key=lambda e: e["id"]),
            "turns": sorted(turns.values(), key=lambda t: (t["observed_at"], t["id"])), "warnings": sorted(set(warnings))}


def candidates(facts, assigned=()):
    turns = {t["id"]: t for t in facts["turns"]}
    start, end = stamp(facts["window"]["start"]), stamp(facts["window"]["cutoff"])
    groups = {}
    for turn in turns.values():
        if turn["id"] in assigned or not observed(turn, start, end):
            continue
        root = turns.get(turn["root_turn_id"], turn)
        key = (root["project"], root["thread_id"])
        groups.setdefault(key, []).append(turn["id"])
    tasks = [{"id": "candidate-" + digest([key, sorted(ids)])[:16], "revision": 1, "project": key[0],
              "title": "待确认目标 · " + key[1], "type": "other", "started_at": None,
              "turn_ids": sorted(ids), "events": [], "limitations": ["尚未按独立目标归并并核实交付"], "next_step": "核实目标及交付证据"}
             for key, ids in sorted(groups.items())]
    return {"schema_version": SCHEMA, "analysis": facts["analysis"], "process_reviewed": False,
            "tasks": tasks, "excluded_turns": [], "summary": "", "recommendations": []}


def load_report(folder):
    """Read sealed, self-contained v2 inputs, never follow old absolute pointers."""
    folder = Path(folder)
    manifest = read_json(folder / "manifest.json")
    require(isinstance(manifest, dict), "报告 manifest 必须是对象")
    require(manifest.get("schema_version") == SCHEMA, "旧报告仅供阅读；请重新配置和采集 v2 数据")
    facts, ledger = read_json(folder / "facts.json"), read_json(folder / "tasks.json")
    hashes = manifest.get("input_hashes", {})
    require(isinstance(hashes, dict), "报告 input_hashes 必须是对象")
    require(digest(facts) == hashes.get("facts") and digest(ledger) == hashes.get("ledger"),
            "报告基础快照/账本与 manifest 哈希不符")
    validate_ledger(facts, ledger)
    return facts, ledger, manifest


def same_scope(a, b):
    return (a["schema_version"] == b["schema_version"] and a["version"] == b["version"] and
            all(set(a["config"][k]) == set(b["config"][k]) for k in ("projects", "source_roots")) and
            a["config"]["timezone"] == b["config"]["timezone"])


def previous_report(facts, explicit=None):
    paths = [Path(explicit).resolve()] if explicit else sorted((Path(facts["config"]["output"]) / "reports").glob("*/*"))
    selected, warnings = None, []
    for folder in paths:
        if not folder.is_dir():
            if explicit:
                raise DataError("指定的前版报告目录不存在")
            continue
        try:
            old, ledger, manifest = load_report(folder)
            compatible = same_scope(facts, old) and stamp(old["window"]["cutoff"]) <= stamp(facts["window"]["cutoff"])
            if explicit:
                require(compatible, "指定前版的项目、来源、时区、版本或截止时间不适用")
            if compatible:
                generated = stamp(manifest.get("generated_at"))
                require(generated is not None, "前版缺生成时间")
                choice = (stamp(old["window"]["cutoff"]), generated, str(folder), old, ledger)
                if selected is None or choice[:3] > selected[:3]:
                    selected = choice
        except (ValueError, OSError, TypeError, KeyError) as exc:
            if explicit:
                raise DataError(f"前版报告不可复用：{exc}") from exc
            warnings.append(f"前版报告未复用：{folder}：{exc}")
    return selected, warnings


def task_status(task):
    events = sorted(enumerate(task.get("events", [])), key=lambda p: (stamp(p[1].get("at")) or datetime.max.replace(tzinfo=timezone.utc), p[0]))
    state = "pending_confirmation"
    for _, event in events:
        if event.get("at") is not None:
            if event["kind"] in STATES:
                state = event["kind"]
            elif event["kind"] == "reopened":
                state = "in_progress"
    return state


def reuse_ledger(facts, previous):
    """Reuse semantic decisions only while their referenced evidence still matches."""
    if previous is None:
        ledger = candidates(facts)
        queue = [{"id": t["id"], "revision": t["revision"], "reason": "本期未归属活动"} for t in ledger["tasks"]]
        return ledger, queue
    _, _, folder, old, prior = previous
    turns, old_turns = ({t["id"]: t for t in value["turns"]} for value in (facts, old))
    evidence, old_evidence = ({e["id"]: e for e in value["evidence"]} for value in (facts, old))
    missing_turns = old_turns.keys() - turns.keys()
    if missing_turns:
        facts["warnings"].append(f"前版 {len(missing_turns)} 个轮次本次不可读取，历史与资源覆盖有缺口")
    ledger = candidates(facts, set(turns))
    ledger["excluded_turns"] = [copy.deepcopy(e) for e in prior.get("excluded_turns", []) if e["turn_id"] in turns]
    queue = []
    latest = {}
    for task in prior["tasks"]:
        latest[task["id"]] = max(latest.get(task["id"], 0), task["revision"])
    for original in prior["tasks"]:
        task = copy.deepcopy(original)
        refs = set(task.get("turn_ids", []))
        proof = set(task.get("start_evidence", [])) | {eid for e in task.get("events", []) for eid in e["evidence"]}
        def signature(item):
            return {k: v for k, v in item.items() if k != "locations"}
        invalid = not refs <= turns.keys() or any(
            eid not in evidence or eid not in old_evidence or signature(evidence[eid]) != signature(old_evidence[eid]) for eid in proof)
        # Revalidate ownership and temporal constraints against the fresh facts too.
        try:
            validate_ledger(facts, dict(ledger, tasks=[task]))
        except (ValueError, KeyError, TypeError):
            invalid = True
        if invalid:
            task.update(turn_ids=sorted(tid for tid in refs & turns.keys()
                                        if task["project"] in turns[tid].get("projects", [turns[tid]["project"]])),
                        started_at=None, events=[], outcome="", review_required=True)
            task.pop("start_evidence", None)
            task.pop("start_note", None)
            task["limitations"] = list(dict.fromkeys(task.get("limitations", []) + ["前版依据缺失或变化，原状态及交付时间尚未重新核实"]))
            task["next_step"] = "核读当前证据并恢复完整历史；不能作为新的首次交付"
            reason = "前版引用失配；原判断保留在 " + folder
        else:
            related = descendants(refs, turns)
            changed = (related != descendants(refs, old_turns) or
                       any(tid not in old_turns or turns[tid] != old_turns[tid] for tid in related))
            unresolved = task["revision"] == latest[task["id"]] and (
                task_status(task) not in {"delivered", "accepted", "cancelled"} or task.get("next_step", "").strip())
            reason = "关联轮次有新增、移除或变化" if changed else "未闭合目标" if unresolved else None
        ledger["tasks"].append(task)
        if reason:
            queue.append({"id": task["id"], "revision": task["revision"], "reason": reason})
    assigned = descendants({tid for t in ledger["tasks"] for tid in t.get("turn_ids", [])} |
                           {e["turn_id"] for e in ledger["excluded_turns"]}, turns)
    for task in candidates(facts, assigned)["tasks"]:
        ledger["tasks"].append(task)
        queue.append({"id": task["id"], "revision": task["revision"], "reason": "本期未归属活动"})
    return ledger, queue


def collect(args):
    config = validate_config(read_json(args.config))
    now = stamp(args.now) if args.now else datetime.now(timezone.utc)
    window = period_window(args.period, config["timezone"], now, args.date, args.start, args.end)
    facts = scan(config, window, args.analysis)
    previous, warnings = previous_report(facts, args.previous_report)
    facts["warnings"] = sorted(set(facts["warnings"] + warnings + ["账本从周期活动建立，未全面盘点更早遗留目标"]))
    ledger, queue = reuse_ledger(facts, previous)
    validate_ledger(facts, ledger)
    target = new_directory(Path(config["output"]) / "snapshots")
    write_json(target / "facts.json", facts)
    write_json(target / "tasks.json", ledger)
    manifest = {"schema_version": SCHEMA, "version": VERSION,
                "captured_at": iso(datetime.now(timezone.utc)), "facts_hash": digest(facts),
                "previous_report": previous[2] if previous else None, "review_queue": queue}
    write_json(target / "manifest.json", manifest)
    return {"snapshot": str(target), "turns": len(facts["turns"]), "previous_report": manifest["previous_report"],
            "review_queue": queue, "warnings": facts["warnings"]}


def descendants(refs, turns):
    refs = set(refs)
    while True:
        expanded = refs | {tid for tid, turn in turns.items() if turn["root_turn_id"] in refs}
        if expanded == refs:
            return refs
        refs = expanded


def validate_ledger(facts, ledger):
    require(isinstance(facts, dict) and isinstance(ledger, dict), "facts/ledger 必须是对象")
    require(facts.get("schema_version") == SCHEMA and ledger.get("schema_version") == SCHEMA, "不支持的数据版本")
    require(facts.get("analysis") in {"basic", "deep"} and ledger.get("analysis") == facts["analysis"], "账本分析模式必须与快照一致")
    require(type(ledger.get("process_reviewed")) is bool, "process_reviewed 必须明确为布尔值")
    require(not ledger["process_reviewed"] or facts["analysis"] == "deep", "普通模式不能声明过程分析完成")
    validate_config(facts["config"])
    require(isinstance(ledger.get("tasks"), list), "tasks 必须是数组")
    require(isinstance(ledger.get("summary", ""), str), "summary 必须是字符串")
    turns = {t["id"]: t for t in facts["turns"]}
    ev = {e["id"]: e for e in facts["evidence"]}
    cutoff, keys, process_ids = stamp(facts["window"]["cutoff"]), set(), {}
    for task in ledger["tasks"]:
        require(isinstance(task, dict), "task 必须是对象")
        key = (task.get("id"), task.get("revision"))
        require(isinstance(key[0], str) and key[0] and type(key[1]) is int and key[1] > 0 and key not in keys, "任务 id/revision 缺失或重复")
        keys.add(key)
        require(task.get("project") in facts["config"]["projects"], "任务项目不在指定集合")
        require(isinstance(task.get("title"), str) and task["title"] and task.get("type") in TYPES, "任务缺标题或合法类型")
        refs = task.get("turn_ids", [])
        require(isinstance(refs, list) and all(isinstance(t, str) for t in refs) and len(refs) == len(set(refs)) and all(t in turns for t in refs), "任务轮次引用无效")
        require(not refs or any(task["project"] in turns[t].get("projects", [turns[t]["project"]]) for t in refs), "主项目必须有相关轮次")
        require(isinstance(task.get("limitations", []), list) and all(isinstance(s, str) for s in task.get("limitations", [])), "limitations 必须是字符串数组")
        require(all(isinstance(task.get(k, ""), str) for k in ("goal", "outcome", "next_step")), "任务文字字段必须是字符串")
        start = stamp(task.get("started_at"))
        require(start is None or start < cutoff, "任务开始时间超出快照")
        related = descendants(refs, turns)
        related_projects = {task["project"]} | {p for t in related for p in turns[t].get("projects", [turns[t]["project"]])}
        if start is not None:
            start_evidence = task.get("start_evidence")
            require(isinstance(start_evidence, list) and start_evidence and all(isinstance(e, str) and e in ev for e in start_evidence), "已知开始时间需 start_evidence")
            require(isinstance(task.get("start_note"), str) and task["start_note"].strip(), "开始时间需说明证据判断 start_note")
            require(any(ev[e]["kind"] in {"user", "user_feedback", "task_started", "tool_result", "workflow"} and not ev[e].get("current_only") for e in start_evidence), "开始时间不能只依据 agent 自述或当前 README")
            require(all(ev[e].get("turn_id") is None or ev[e]["turn_id"] in related for e in start_evidence) and all(ev[e].get("project") in related_projects for e in start_evidence), "开始证据不属于任务")
            require(any(ev[e].get("at") is not None for e in start_evidence), "未定日期来源不能单独确定开始时间")
        ids = set()
        require(isinstance(task.get("events", []), list), "events 必须是数组")
        require(type(task.get("review_required", False)) is bool, "review_required 必须是布尔值")
        require(not task.get("review_required") or not task.get("events"), "依据失配目标须重新核实完整历史并解除 review_required 后才能记录状态")
        for event in task.get("events", []):
            require(isinstance(event, dict), "event 必须是对象")
            require(isinstance(event.get("id"), str) and event["id"] and event["id"] not in ids, "事件 id 缺失或重复")
            ids.add(event["id"])
            require(event.get("kind") in STATES | PROCESS, "未知事件类型")
            at = stamp(event.get("at"))
            require(at is None or at < cutoff and (start is None or at >= start), "事件时间超出快照/早于任务开始")
            refs_ev = event.get("evidence")
            require(isinstance(refs_ev, list) and refs_ev and all(isinstance(e, str) and e in ev for e in refs_ev), "事件缺可追溯证据")
            require(not all(ev[e].get("current_only") for e in refs_ev), "不能只用当前 README 重建状态")
            require(isinstance(event.get("note"), str) and event["note"].strip(), "事件需说明证据判断")
            require(all(ev[e].get("turn_id") is None or ev[e]["turn_id"] in related for e in refs_ev), "事件证据不属于任务关联轮次")
            require(all(ev[e].get("project") in related_projects for e in refs_ev), "事件证据来源项目无关")
            if at is not None:
                require(any(ev[e].get("at") is not None for e in refs_ev), "未定日期工作流不能单独确定事件日期；需关联有日期证据")
            if event["kind"] in {"delivered", "accepted", "validation_passed", "validation_failed"}:
                basis = event.get("basis")
                require(basis in BASES, "交付/验收/验证需明确 basis 证据层级")
                kinds = {ev[e]["kind"] for e in refs_ev if not ev[e].get("current_only")}
                if basis == "answer":
                    require(task["type"] in {"consultation", "review", "design", "documentation", "research"} and "assistant" in kinds and event["kind"] == "delivered", "answer 仅证明答案本身交付，不能证明实现或验收")
                elif basis == "user_acceptance":
                    require(bool(kinds & {"user", "user_feedback"}), "用户验收需明确用户消息证据")
                    if "user_feedback" in kinds:
                        require(isinstance(event.get("verified_excerpt"), str) and event["verified_excerpt"].strip(), "工具中的用户认可需已审阅的 verified_excerpt")
                else:
                    require(bool(kinds & {"tool_result", "workflow"}), "agent 自述不能单独证明交付或验证")
                    if "tool_result" in kinds:
                        require(isinstance(event.get("verified_excerpt"), str) and event["verified_excerpt"].strip(), "工具引用需保存已审阅且无敏感数据的 verified_excerpt")
                if event["kind"].startswith("validation_"):
                    require(event.get("category") in VALIDATIONS, "验证事件需合法分类")
                    require(basis == event["category"], "验证 category 与 basis 必须一致")
            if event["kind"] in PROCESS:
                prior = process_ids.setdefault(event["id"], event)
                require(prior == event, "同一过程事件 id 的内容冲突")
            if event["kind"] == "intervention":
                require(event.get("category") in {"clarification", "decision", "authorization", "manual_fix"}, "人工介入需合法分类")
            if event["kind"] == "wait":
                require(event.get("category") in {"input", "approval", "environment", "dependency"}, "等待需合法分类")
                until = stamp(event.get("until"))
                require(until is None or at is not None and until >= at and until <= cutoff, "等待终点无效")
    excluded = ledger.get("excluded_turns", [])
    require(isinstance(excluded, list), "excluded_turns 必须是数组")
    assigned = {tid for task in ledger["tasks"] for tid in task.get("turn_ids", [])}
    seen = set()
    for item in excluded:
        require(isinstance(item, dict), "排除轮次必须是对象")
        tid = item.get("turn_id")
        require(tid in turns and tid not in assigned and tid not in seen and item.get("reason"), "排除轮次不存在、重复或仍分配给任务")
        seen.add(tid)
    recommendations = ledger.get("recommendations", [])
    require(isinstance(recommendations, list) and len(recommendations) <= 3, "建议最多三条")
    ids = {t["id"] for t in ledger["tasks"]}
    for item in recommendations:
        require(isinstance(item, dict), "建议必须是对象")
        require(isinstance(item.get("text"), str) and item["text"].strip() and isinstance(item.get("task_ids"), list) and item["task_ids"] and all(t in ids for t in item["task_ids"]), "建议需引用存在的任务")
        refs = descendants({tid for task in ledger["tasks"] if task["id"] in item["task_ids"] for tid in task.get("turn_ids", [])}, turns)
        proof = item.get("evidence")
        require(isinstance(proof, list) and proof and all(isinstance(e, str) and e in ev for e in proof), "建议需引证 evidence")
        require(all(ev[e].get("turn_id") is None or ev[e]["turn_id"] in refs for e in proof), "建议证据不属于所引任务")


def clipped(turn, start, end):
    first, last = stamp(turn.get("start")), stamp(turn.get("end"))
    if first is None or last is None or last < first:
        return None
    first, last = max(first, start), min(last, end)
    return (first, last) if first < last else None


def union_seconds(intervals):
    total, finish = 0.0, None
    for first, last in sorted(intervals):
        if finish is None or first > finish:
            total += (last - first).total_seconds()
        elif last > finish:
            total += (last - finish).total_seconds()
        finish = max(finish, last) if finish else last
    return round(total, 3)


def observed(turn, start, end):
    if clipped(turn, start, end):
        return True
    activity = turn.get("activity_at", [turn["last_observed_at"]])
    return any(start <= stamp(at) < end for at in activity) or any(start <= stamp(u["at"]) < end for u in turn["usage"])


def execution(turns, start, end):
    intervals = [v for t in turns if (v := clipped(t, start, end))]
    period_usages = [[u for u in t["usage"] if start <= stamp(u["at"]) < end] for t in turns]
    usages = [u for records in period_usages for u in records]
    token_values, samples = {}, {}
    for key in TOKENS:
        values = [u["tokens"].get(key) for u in usages if type(u["tokens"].get(key)) is int and u["tokens"][key] >= 0]
        token_values[key] = sum(values) if values else None
        samples[key] = len(values)
    with_usage = sum(any(start <= stamp(u["at"]) < end and any(type(u["tokens"].get(k)) is int and u["tokens"][k] >= 0 for k in TOKENS) for u in t["usage"]) for t in turns)
    # A field is complete for a turn only when every observed response in this
    # window supplies it. Keep partial sums and other fields independently valid.
    field_coverage = {key: sum(bool(records) and all(type(u["tokens"].get(key)) is int and
                          u["tokens"][key] >= 0 for u in records) for records in period_usages) for key in TOKENS}
    def user_in_period(turn):
        # Legacy facts without message timestamps cannot establish a period count.
        return any(start <= stamp(at) < end for at in turn.get("user_message_at", []))
    return {"turns": len(turns), "timed_turns": len(intervals),
            "open_or_untimed_turns": sum(clipped(t, start, end) is None for t in turns),
            "execution_seconds_sum": round(sum((b - a).total_seconds() for a, b in intervals), 3) if intervals else None,
            "occupied_seconds": union_seconds(intervals) if intervals else None,
            "confirmed_user_turns": sum(user_in_period(t) and t.get("trigger") in USER_TRIGGERS and not t["child"] and not t.get("owner_ambiguous") for t in turns),
            "candidate_user_turns": sum(user_in_period(t) and t.get("trigger") not in USER_TRIGGERS and not t["child"] and not t.get("owner_ambiguous") for t in turns),
            "ambiguous_owner_turns": sum(bool(t.get("owner_ambiguous")) for t in turns),
            "tokens": token_values, "token_field_samples": samples, "recorded_calls": len(usages),
            "token_field_turn_coverage": field_coverage,
            "token_turn_coverage": {"known": with_usage, "observed": len(turns)},
            "partial_usage_turns": sum(t["usage_partial"] for t in turns)}


def aggregate(facts, ledger):
    validate_ledger(facts, ledger)
    reviewed = facts["analysis"] == "deep" and ledger["process_reviewed"]
    start, end = stamp(facts["window"]["start"]), stamp(facts["window"]["cutoff"])
    turns = {t["id"]: t for t in facts["turns"]}
    excluded = descendants({item["turn_id"] for item in ledger.get("excluded_turns", [])}, turns)
    assignments = {}
    task_turns = {}
    for task in ledger["tasks"]:
        key = (task["id"], task["revision"])
        refs = descendants(task.get("turn_ids", []), turns)
        refs -= excluded
        task_turns[key] = refs
        for tid in refs:
            assignments.setdefault(tid, set()).add(key)
    rows, cycles = [], []
    counts = {"delivered": 0, "accepted": 0, "failed": 0}
    stock = {state: 0 for state in STATES}
    process = {kind: 0 for kind in PROCESS}
    interventions, waits, unknown_events, seen_process = {}, [], 0, set()
    latest = {}
    for task in ledger["tasks"]:
        latest[task["id"]] = max(latest.get(task["id"], 0), task["revision"])
    for task in ledger["tasks"]:
        key = (task["id"], task["revision"])
        refs = task_turns[key]
        dated = sorted(enumerate(task.get("events", [])), key=lambda pair: (pair[1].get("at") is None, stamp(pair[1].get("at")) or end, pair[0]))
        events = [e for _, e in dated if e.get("at") is not None and stamp(e["at"]) < end]
        status = "pending_confirmation"
        for event in events:
            if event["kind"] in STATES:
                status = event["kind"]
            elif event["kind"] == "reopened":
                status = "in_progress"
        active = [turns[tid] for tid in sorted(refs) if observed(turns[tid], start, end)]
        period_events = [e for e in events if start <= stamp(e["at"]) < end]
        started = stamp(task.get("started_at"))
        unknown = [e for e in task.get("events", []) if e.get("at") is None]
        if not active and not period_events and not unknown and not task.get("review_required") and not (
                task["revision"] == latest[task["id"]] and (task.get("next_step", "").strip() or
                status not in {"delivered", "accepted", "cancelled"})):
            continue
        superseded = task["revision"] < latest[task["id"]]
        if not superseded:
            stock[status] += 1
        delivery = next((e for e in events if e["kind"] in {"delivered", "accepted"}), None)
        acceptance = next((e for e in events if e["kind"] == "accepted"), None)
        failure = any(e["kind"] == "failed" for e in period_events)
        this_delivery = delivery is not None and start <= stamp(delivery["at"]) < end
        counts["delivered"] += this_delivery
        counts["accepted"] += acceptance is not None and start <= stamp(acceptance["at"]) < end
        counts["failed"] += failure
        cycle = (stamp(delivery["at"]) - started).total_seconds() if delivery and started else None
        if this_delivery and cycle is not None:
            cycles.append(cycle)
        unknown_events += len(unknown)
        for event in period_events:
            if event["kind"] in PROCESS and event["id"] not in seen_process:
                process[event["kind"]] += 1
                if event["kind"] == "intervention":
                    category = event["category"]
                    interventions[category] = interventions.get(category, 0) + 1
                seen_process.add(event["id"])
        for event in events:
            if event["kind"] == "wait" and event.get("until"):
                first, last = max(stamp(event["at"]), start), min(stamp(event["until"]), end)
                if first < last:
                    waits.append((first, last))
        shared = any(len(assignments[t["id"]]) > 1 for t in active)
        rows.append({"id": task["id"], "revision": task["revision"], "project": task["project"], "title": task["title"],
                     "type": task["type"], "goal": task.get("goal", ""), "outcome": task.get("outcome", ""), "status": status, "superseded": superseded,
                     "delivered_this_period": bool(this_delivery), "accepted_this_period": acceptance is not None and start <= stamp(acceptance["at"]) < end,
                     "cycle_seconds": cycle, "turn_ids": sorted(refs), "events": events,
                     "unknown_date_events": unknown,
                     "limitations": task.get("limitations", []), "next_step": task.get("next_step", ""),
                     "resource_attribution": "shared_unknown" if shared else "observed",
                     "execution": None if shared else execution(active, start, end)})
    active_turns = [t for tid, t in sorted(turns.items()) if tid not in excluded and observed(t, start, end)]
    missing = sorted(t["id"] for t in active_turns if t["id"] not in assignments)
    feedback = {e["id"] for e in facts["evidence"] if e["kind"] == "user_feedback" and
                e.get("turn_id") not in excluded and start <= stamp(e["at"]) < end}
    classified = {eid for row in rows for event in row["events"] if event["kind"] == "intervention" and
                  start <= stamp(event["at"]) < end for eid in event["evidence"]} & feedback
    composition = {}
    for row in rows:
        if not row["superseded"]:
            key = (row["project"], row["type"])
            composition[key] = composition.get(key, 0) + 1
    return {"schema_version": SCHEMA, "version": VERSION, "window": facts["window"],
            "analysis": facts["analysis"], "process_reviewed": reviewed,
            "input_hashes": {"facts": digest(facts), "ledger": digest(ledger)},
            "counts": counts, "end_states": stock, "process_events": process if reviewed else None,
            "interventions": dict(sorted(interventions.items())) if reviewed else None,
            "recorded_wait_seconds_union": union_seconds(waits) if reviewed and waits else None,
            "completion_cycle": {"median_seconds": statistics.median(cycles) if cycles else None,
                                 "known_samples": len(cycles), "missing_samples": counts["delivered"] - len(cycles)},
            "execution": execution(active_turns, start, end),
            "task_composition": [{"project": p, "type": typ, "tasks": n} for (p, typ), n in sorted(composition.items())],
            "coverage": {"observed_period_turns": len(active_turns), "mapped_period_turns": len(active_turns) - len(missing),
                         "unmapped_turn_ids": missing, "excluded_turns": sorted(excluded), "unknown_date_events": unknown_events,
                         "user_feedback": {"observed": len(feedback), "classified": len(classified) if reviewed else None,
                                           "unclassified_evidence_ids": sorted(feedback - classified) if reviewed else None},
                         "historical_completeness": "unknown", "scope": "readable_local_logs"},
            "tasks": sorted(rows, key=lambda r: (r["project"], r["id"], r["revision"])),
            "summary": ledger.get("summary", ""), "recommendations": [item for item in ledger.get("recommendations", []) if set(item["task_ids"]) <= {t["id"] for t in rows}],
            "warnings": facts["warnings"]}


def trend(stats, facts):
    """Recompute buckets from raw turn intervals/usage and first deliveries."""
    window = stats["window"]
    tz = ZoneInfo(window["timezone"])
    begin, finish = stamp(window["start"]), stamp(window["cutoff"])
    kind = window["kind"]
    if kind == "daily" or stats["analysis"] != "deep":
        return []
    day = begin.astimezone(tz).date()
    buckets = []
    while datetime.combine(day, time.min, tz).astimezone(timezone.utc) < finish:
        monthly = kind in {"quarterly", "yearly"} or kind == "custom" and (finish - begin).days > 90
        following = month_shift(day.replace(day=1), 1) if monthly else day + timedelta(days=7 if kind == "monthly" else 1)
        first = max(begin, datetime.combine(day, time.min, tz).astimezone(timezone.utc))
        last = min(finish, datetime.combine(following, time.min, tz).astimezone(timezone.utc))
        delivered = []
        for task in stats["tasks"]:
            event = next((e for e in task["events"] if e["kind"] in {"delivered", "accepted"}), None)
            if event and first <= stamp(event["at"]) < last:
                delivered.append(task)
        excluded = set(stats["coverage"]["excluded_turns"])
        active = [t for t in facts["turns"] if t["id"] not in excluded and observed(t, first, last)]
        cycles = [t["cycle_seconds"] for t in delivered if t["cycle_seconds"] is not None]
        events = {e["id"]: e for task in stats["tasks"] for e in task["events"]
                  if e["kind"] in PROCESS and first <= stamp(e["at"]) < last}
        buckets.append({"start": iso(first), "end": iso(last), "label": day.isoformat(), "delivered": len(delivered),
                        "cycle_median_seconds": statistics.median(cycles) if cycles else None,
                        "cycle_samples": len(cycles), "execution": execution(active, first, last),
                        "process_events": {kind: sum(e["kind"] == kind for e in events.values()) for kind in sorted(PROCESS)} if stats["process_reviewed"] else None})
        day = following
    return buckets


def compare(stats, facts, baseline_folder):
    """Explicit baseline only; verify and recompute saved inputs, not averages."""
    old_facts, old_tasks, _ = load_report(baseline_folder)
    baseline = aggregate(old_facts, old_tasks)
    same = (set(facts["config"]["projects"]) == set(old_facts["config"]["projects"]) and
            set(facts["config"]["source_roots"]) == set(old_facts["config"]["source_roots"]) and
            facts["version"] == old_facts["version"] and
            stats["window"]["kind"] == baseline["window"]["kind"] and
            stats["window"]["timezone"] == baseline["window"]["timezone"] and
            not stats["window"]["partial"] and not baseline["window"]["partial"] and
            stamp(baseline["window"]["end"]) <= stamp(stats["window"]["start"]))
    if not same:
        return {"comparable": False, "reason": "项目、来源、版本、周期、时区不一致，阶段性或窗口重叠", "groups": []}
    if stats["window"]["kind"] == "custom":
        current_days = (stamp(stats["window"]["end"]).astimezone(ZoneInfo(stats["window"]["timezone"])).date() - stamp(stats["window"]["start"]).astimezone(ZoneInfo(stats["window"]["timezone"])).date()).days
        previous_days = (stamp(baseline["window"]["end"]).astimezone(ZoneInfo(baseline["window"]["timezone"])).date() - stamp(baseline["window"]["start"]).astimezone(ZoneInfo(baseline["window"]["timezone"])).date()).days
        if current_days != previous_days:
            return {"comparable": False, "reason": "自定义周期天数不同", "groups": []}
    def grouped(value):
        groups = {}
        for task in value["tasks"]:
            key = (task["project"], task["type"])
            group = groups.setdefault(key, {"observed_tasks": 0, "delivered": 0, "cycles": []})
            group["observed_tasks"] += not task["superseded"]
            group["delivered"] += task["delivered_this_period"]
            if task["delivered_this_period"] and task["cycle_seconds"] is not None:
                group["cycles"].append(task["cycle_seconds"])
        for group in groups.values():
            cycles = group.pop("cycles")
            group.update(cycle_median_seconds=statistics.median(cycles) if cycles else None, cycle_samples=len(cycles))
        return groups
    current, prior = grouped(stats), grouped(baseline)
    def coverage_profile(value):
        c, ex = value["coverage"], value["execution"]
        n = c["observed_period_turns"]
        return (c["mapped_period_turns"] / n, ex["token_turn_coverage"]["known"] / n, ex["timed_turns"] / n,
                bool(c["unknown_date_events"]), bool(ex["partial_usage_turns"]),
                tuple(ex["token_field_turn_coverage"][k] / n for k in TOKENS)) if n else None
    diagnostics = any(not w.startswith(("覆盖范围仅为", "账本从周期活动建立"))
                      for value in (stats, baseline) for w in value["warnings"])
    comparable = not diagnostics and coverage_profile(stats) is not None and coverage_profile(stats) == coverage_profile(baseline)
    process_comparable = (comparable and stats["process_reviewed"] and baseline["process_reviewed"] and
                          not stats["coverage"]["user_feedback"]["unclassified_evidence_ids"] and
                          not baseline["coverage"]["user_feedback"]["unclassified_evidence_ids"])
    return {"comparable": comparable, "reason": None if comparable else "存在采集诊断、覆盖不同或缺少观察样本；仅并列观察值，不能判断效率改善",
            "baseline_window": baseline["window"], "baseline_hashes": baseline["input_hashes"],
            "coverage_current": stats["coverage"], "coverage_baseline": baseline["coverage"],
            "execution_current": stats["execution"], "execution_baseline": baseline["execution"],
            "process_comparable": process_comparable,
            "quality_current": stats["process_events"] if process_comparable else None,
            "quality_baseline": baseline["process_events"] if process_comparable else None,
            "note": "仅并列同类观察值；样本构成与缺失仍需审阅，不推断因果或模型排名", "groups": [
                {"project": k[0], "type": k[1], "current": current.get(k), "baseline": prior.get(k)} for k in sorted(set(current) | set(prior))]}


def md_text(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def display(value, suffix=""):
    if value is None:
        return "未知"
    if isinstance(value, (int, float, Decimal)):
        text = format(Decimal(str(value)), ",f")
        return (text.rstrip("0").rstrip(".") if "." in text else text) + suffix
    return str(value)


def duration(value, brief=False):
    if value is None:
        return "未知"
    seconds = Decimal(str(value))
    if seconds < 60:
        return display(seconds, " 秒")
    if brief:
        minutes = int((seconds / 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        hours, minutes = divmod(minutes, 60)
        parts = ([f"{hours} 小时"] if hours else []) + ([f"{minutes} 分"] if minutes else [])
        return ("约" if seconds % 60 else "") + " ".join(parts)
    hours = int(seconds // 3600)
    minutes = int(seconds % 3600 // 60)
    remaining = seconds % 60
    parts = ([f"{hours} 小时"] if hours else []) + ([f"{minutes} 分"] if minutes else [])
    if remaining:
        parts.append(display(remaining, " 秒"))
    return " ".join(parts) + f"（{display(seconds, ' 秒')}）"


def short_tokens(value):
    if value is None:
        return "未知"
    number = Decimal(str(value))
    scale, unit = (Decimal(100000000), "亿") if number >= 100000000 else (Decimal(10000), "万")
    if number < scale:
        return display(number)
    rounded = (number / scale).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return ("约" if rounded * scale != number else "") + display(rounded) + unit


def activity_dates(stats, facts):
    """Presentation only: observed endpoints do not imply continuous coverage."""
    window = stats["window"]
    start, end = stamp(window["start"]), stamp(window["cutoff"])
    excluded = set(stats["coverage"]["excluded_turns"])
    times = []
    for turn in facts["turns"]:
        if turn["id"] in excluded:
            continue
        interval = clipped(turn, start, end)
        if interval:
            times.extend([interval[0], min(interval[1], end - timedelta(microseconds=1))])
        activity = turn.get("activity_at", [turn.get("last_observed_at")])
        for value in activity + [usage["at"] for usage in turn["usage"]]:
            at = stamp(value)
            if at is not None and start <= at < end:
                times.append(at)
    tz = ZoneInfo(window["timezone"])
    return (min(times).astimezone(tz).date(), max(times).astimezone(tz).date()) if times else None


def coverage_text(stats):
    coverage, ex = stats["coverage"], stats["execution"]
    text = (f"覆盖：任务归属 {coverage['mapped_period_turns']}/{coverage['observed_period_turns']} 轮；"
            f"时间已知 {ex['timed_turns']}/{ex['turns']} 轮；"
            f"token 总量已知 {ex['token_field_turn_coverage']['total_tokens']}/{ex['turns']} 轮。")
    if ex["partial_usage_turns"]:
        text += f"资源记录不完整 {ex['partial_usage_turns']} 轮。"
    if coverage["unknown_date_events"]:
        text += f"未定日期事件 {coverage['unknown_date_events']} 项。"
    return text


def task_anchor(task):
    """Stable across title, order and period changes; revisions stay distinct."""
    return "task-" + digest([task["id"], task["revision"]])[:16]


def report_header(stats, facts, details=False):
    window = stats["window"]
    cutoff = stamp(window["cutoff"]).astimezone(ZoneInfo(window["timezone"])).isoformat()
    first, last = window["label"].split("_")
    output = [f"# Relatra {PERIODS[window['kind']]} · {window['label']}" + (" · 明细" if details else ""), "",
              f"统计周期：{first} 至 {last}；实际截止：{cutoff}；时区：{window['timezone']}。",
              "范围：指定项目的可读取本地记录。",
              *(["阶段性报告，周期尚未结束。"] if window["partial"] else [])]
    dates = activity_dates(stats, facts)
    if dates:
        output += [f"已发现活动日期：{dates[0]} 至 {dates[1]}（仅首末日期，不代表连续完整覆盖）。"]
        if dates[0] > stamp(window["start"]).astimezone(ZoneInfo(window["timezone"])).date():
            output += [f"{dates[0]} 之前的本期工作情况未知。"]
    else:
        output += ["本期未发现可归属记录；活动日期未知。"]
    return output + [""]


def render(stats, facts):
    """Keep editorial judgments in the agent-authored ledger summary."""
    output = report_header(stats, facts)
    if stats["summary"].strip():
        output += [stats["summary"].strip(), ""]
    else:
        counts = stats["counts"]
        output += ["## 本期概况", "", "尚未整理重点摘要；完整任务、限制与后续行动见明细。",
                   f"本期交付（含验收） {counts['delivered']}；首次验收 {counts['accepted']}；发生失败的任务 {counts['failed']}。",
                   "期末状态：" + ("；".join(f"{LABELS[k]} {v}" for k, v in sorted(stats["end_states"].items()) if v) or "未发现可归属任务") + "。", ""]
    diagnostics = [w for w in stats["warnings"] if not w.startswith("覆盖范围仅为")]
    ex = stats["execution"]
    output += [coverage_text(stats) + ("另有采集与历史提示，具体影响见[明细](details.md)。" if diagnostics else ""), ""]
    timing = duration(ex["execution_seconds_sum"], brief=True)
    tokens = short_tokens(ex["tokens"]["total_tokens"])
    cached = short_tokens(ex["tokens"]["cached_input_tokens"])
    if ex["execution_seconds_sum"] is not None and (diagnostics or ex["timed_turns"] < ex["turns"]):
        timing += "（部分观测值）"
    if ex["tokens"]["total_tokens"] is not None and (diagnostics or ex["partial_usage_turns"] or
            ex["token_field_turn_coverage"]["total_tokens"] < ex["turns"]):
        tokens += "（部分观测值）"
    if ex["tokens"]["cached_input_tokens"] is not None and (diagnostics or ex["partial_usage_turns"] or
            ex["token_field_turn_coverage"]["cached_input_tokens"] < ex["turns"]):
        cached += "（部分观测值）"
    output += [f"已观测累计执行时间：{timing}；token：{tokens}，其中缓存输入：{cached}。完整任务、证据与统计见[明细](details.md)。", ""]
    return "\n".join(output)


def render_details(stats, facts):
    ex, coverage = stats["execution"], stats["coverage"]
    deep = stats["analysis"] == "deep"
    counts = stats["counts"]
    output = report_header(stats, facts, details=True) + ["[返回重点正文](report.md)；历史来源完整性未知。", "",
              "## 周期概览", "",
              f"本期交付（含验收） {counts['delivered']}；首次验收 {counts['accepted']}；发生失败的任务 {counts['failed']}。",
              "期末状态：" + ("；".join(f"{LABELS[k]} {v}" for k, v in sorted(stats["end_states"].items()) if v) or "未发现可归属任务") + "。", ""]
    output += ["## 具体任务与成果", ""]
    projects = sorted({t["project"] for t in stats["tasks"]})
    for project in projects:
        output += [f"### {md_text(project)}", ""]
        for task in (t for t in stats["tasks"] if t["project"] == project):
            output += [f'<a id="{task_anchor(task)}"></a>', "",
                       f"#### {md_text(task['title'])}（{LABELS[task['status']]}" + ("，历史修订" if task["superseded"] else "") + "）", "",
                       f"当前结论：{md_text(task['outcome'] or '当前结论待核实')}。"]
            if task["limitations"]:
                output += ["", "当前限制：" + md_text("；".join(task["limitations"])) + "。"]
            if task["next_step"].strip():
                output += ["", "未闭合行动：" + md_text(task["next_step"]) + "。"]
            output += ["", f"目标标识：`{md_text(task['id'])}`；修订：{task['revision']}；本期首次交付：{'是' if task['delivered_this_period'] else '否'}；本期首次验收：{'是' if task['accepted_this_period'] else '否'}。"]
            if task["goal"]:
                output += ["", f"目标：{md_text(task['goal'])}。"]
            events = task["events"] + task["unknown_date_events"]
            if events:
                output += ["", "历史事件与证据：", ""]
                for event in events:
                    kind = LABELS.get(event["kind"], PROCESS_LABELS.get(event["kind"], event["kind"]))
                    output += [f"- {event['at'] or '日期未知'} · {kind}：{md_text(event['note'])}；验证层级：{BASIS_LABELS.get(event.get('basis'), '状态记录')}。",
                               f"  关键证据：{', '.join(event['evidence'])}（详见 statistics.json）。"]
            else:
                output += ["", "交付证据尚待核实。"]
            output += [""]
    if not projects:
        output += ["本期未发现范围内可归属的任务。", ""]
    output += ["## 资源与覆盖", "",
               f"累计执行 {duration(ex['execution_seconds_sum'])}；去重占用 {duration(ex['occupied_seconds'])}；已观测 token 总量 {display(ex['tokens']['total_tokens'])}，其中缓存输入 {display(ex['tokens']['cached_input_tokens'])}。",
               coverage_text(stats),
               "执行时间包含工具及轮内等待，不代表人工投入；未知不补零，不换算费用。", ""]
    if not deep:
        output += ["返工、重试、人工介入与等待未统计；不能解释为零次。", ""]
    diagnostics = [w for w in stats["warnings"] if not w.startswith("覆盖范围仅为")]
    if diagnostics:
        output += [f"采集与历史覆盖有 {len(diagnostics)} 条提示，成果和资源可能不完整：", ""]
        output += [f"- {md_text(w)}" for w in diagnostics]
        if any("未全面盘点更早遗留" in w for w in diagnostics):
            output += ["", "账本未全面盘点更早遗留目标。"]
        output += [""]
    if deep:
        cycle = stats["completion_cycle"]
        output += ["## 执行效率与质量", "",
                   f"完成周期中位数 {display(cycle['median_seconds'], ' 秒')}；有效 {cycle['known_samples']} / 缺失 {cycle['missing_samples']}。",
                   f"已确认/候选用户交互轮 {ex['confirmed_user_turns']} / {ex['candidate_user_turns']}。"]
        if stats["process_reviewed"]:
            output += ["过程事件：" + "；".join(f"{PROCESS_LABELS[k]} {v}" for k, v in sorted(stats["process_events"].items())) + "。",
                       "人工介入分类：" + ("；".join(f"{CATEGORY_LABELS[k]} {v}" for k, v in stats["interventions"].items()) or "未记录") + "。",
                       f"明确等待区间并集 {display(stats['recorded_wait_seconds_union'], ' 秒')}；未记录不等于未发生。"]
            feedback = coverage["user_feedback"]
            output += [f"工具用户答复：已分类 {feedback['classified']} / 已观察 {feedback['observed']}。"]
            if feedback["unclassified_evidence_ids"]:
                output += ["工具用户答复尚未分类，人工介入统计不完整。"]
        else:
            output += ["本期过程分析尚未完成，过程指标未统计；不能沿用前版的完整性结论。"]
        output += [""]
    if stats.get("trend"):
        output += ["## 周期内趋势", "", "| 区间起点 | 首次交付 | 周期中位数 / 样本 | 累计 / 占用秒 | 返工 / 重试 | token 总量 / 覆盖轮 |", "|---|---|---|---|---|---|"]
        for bucket in stats["trend"]:
            bx, process = bucket["execution"], bucket["process_events"]
            quality = f"{process['rework']} / {process['retry']}" if process is not None else "未统计"
            output.append(f"| {bucket['label']} | {bucket['delivered']} | {display(bucket['cycle_median_seconds'])} / {bucket['cycle_samples']} | {display(bx['execution_seconds_sum'])} / {display(bx['occupied_seconds'])} | {quality} | {display(bx['tokens']['total_tokens'])} / {bx['token_turn_coverage']['known']}:{bx['turns']} |")
        output += [""]
    comparison = stats.get("comparison")
    if comparison:
        output += ["## 前期比较", ""]
        if not comparison["comparable"]:
            output += [comparison["reason"], ""]
        if comparison.get("groups"):
            output += ["| 项目 / 类型 | 本期 / 前期交付 | 本期 / 前期周期中位数（秒） |", "|---|---|---|"]
            for group in comparison["groups"]:
                a, b = group["current"] or {}, group["baseline"] or {}
                output.append(f"| {md_text(group['project'])} / {TYPE_LABELS[group['type']]} | {a.get('delivered', '未知')} / {b.get('delivered', '未知')} | {display(a.get('cycle_median_seconds'))} / {display(b.get('cycle_median_seconds'))} |")
            ca, cb = comparison["coverage_current"], comparison["coverage_baseline"]
            a, b = comparison["execution_current"], comparison["execution_baseline"]
            output += ["", f"归属覆盖：本期 {ca['mapped_period_turns']}/{ca['observed_period_turns']}；前期 {cb['mapped_period_turns']}/{cb['observed_period_turns']}。",
                       f"累计执行秒：本期 {display(a['execution_seconds_sum'])} / 前期 {display(b['execution_seconds_sum'])}；token 总量：本期 {display(a['tokens']['total_tokens'])} / 前期 {display(b['tokens']['total_tokens'])}。",
                       "样本及资源字段覆盖见 statistics.json；覆盖或构成改变时不能直接解释为效率改善。"]
            if comparison["process_comparable"]:
                a, b = comparison["quality_current"], comparison["quality_baseline"]
                output += [f"返工/重试：本期 {a['rework']}/{a['retry']}；前期 {b['rework']}/{b['retry']}。"]
            else:
                output += ["过程指标未比较：双方须完成深度分析并满足覆盖条件。"]
            output += [""]
    output += ["## 遗留与下一步", ""]
    pending = [t for t in stats["tasks"] if not t["superseded"] and
               (t["status"] in {"blocked", "failed", "pending_confirmation", "in_progress"} or t["next_step"].strip())]
    output += [f"- {md_text(t['title'])}（{LABELS[t['status']]}）：{md_text(t['next_step'] or '需要核实下一步')}" for t in pending] or ["无已记录的遗留事项；来源完整性仍未知。"]
    if stats["recommendations"]:
        output += ["", "## 改进建议", ""]
        output += [f"- {item['text']}（任务：{', '.join(item['task_ids'])}；证据：{', '.join(item['evidence'])}）" for item in stats["recommendations"]]
    output += ["", "详细事件、证据、资源字段及诊断见同目录 statistics.json；复算输入见 facts.json、tasks.json 和 manifest.json。", ""]
    return "\n".join(output)


def report(args):
    snapshot = Path(args.snapshot).resolve()
    facts = read_json(snapshot / "facts.json")
    seal = read_json(snapshot / "manifest.json")
    require(isinstance(seal, dict), "快照 manifest 必须是对象")
    require(seal.get("schema_version") == SCHEMA, "旧快照仅供阅读；请重新采集 v2 数据")
    if "input_hashes" in seal:
        facts, _, seal = load_report(snapshot)
    else:
        require(seal.get("facts_hash") == digest(facts), "采集快照与原始 manifest 哈希不符；请重新采集，不能改写 facts")
    tasks_path = Path(args.tasks).resolve() if args.tasks else snapshot / "tasks.json"
    ledger = read_json(tasks_path)
    require(bool(args.revises) == bool(args.reason and args.reason.strip()), "更正必须成对提供 --revises 与非空 --reason")
    require("input_hashes" not in seal or digest(ledger) == seal["input_hashes"]["ledger"] or args.revises,
            "修改已生成报告的账本必须提供 --revises 与 --reason")
    if args.revises:
        parent, _, _ = load_report(args.revises)
        require(same_scope(facts, parent) and all(facts["window"][k] == parent["window"][k] for k in ("kind", "start", "end")) and
                stamp(facts["window"]["cutoff"]) >= stamp(parent["window"]["cutoff"]), "被更正报告与当前范围或周期不一致")
    stats = aggregate(facts, ledger)
    stats["trend"] = trend(stats, facts)
    stats["comparison"] = compare(stats, facts, args.baseline) if args.baseline else None
    config = validate_config(facts["config"])
    target = new_directory(Path(config["output"]) / "reports" / (facts["window"]["kind"] + "-" + facts["window"]["label"]))
    write_json(target / "statistics.json", stats)
    write_json(target / "tasks.json", ledger)
    write_json(target / "facts.json", facts)
    write_json(target / "manifest.json", {"schema_version": SCHEMA, "version": VERSION, "generated_at": iso(datetime.now(timezone.utc)),
                                         "facts": str(target / "facts.json"), "snapshot": str(snapshot), "tasks_input": str(tasks_path),
                                         "input_hashes": stats["input_hashes"], "baseline": absolute(args.baseline) if args.baseline else None,
                                         "previous_report": seal.get("previous_report"),
                                         "revises": absolute(args.revises) if args.revises else None,
                                         "reason": args.reason.strip() if args.reason else None})
    (target / "report.md").write_text(render(stats, facts), encoding="utf-8")
    (target / "details.md").write_text(render_details(stats, facts), encoding="utf-8")
    return {"report": str(target / "report.md"), "statistics": str(target / "statistics.json"), "counts": stats["counts"], "coverage": stats["coverage"]}


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    conf = sub.add_parser("configure", help="保存明确项目集合和报告目录")
    conf.add_argument("--output", required=True)
    conf.add_argument("--project", action="append", required=True)
    conf.add_argument("--source-root", action="append")
    conf.add_argument("--timezone", default="Asia/Shanghai")
    conf.add_argument("--replace", action="store_true")
    coll = sub.add_parser("collect", help="只读采集并生成待确认候选")
    coll.add_argument("--config", required=True)
    coll.add_argument("--period", choices=list(PERIODS.keys())[:-1], default="weekly")
    coll.add_argument("--date")
    coll.add_argument("--start")
    coll.add_argument("--end")
    coll.add_argument("--now")
    coll.add_argument("--analysis", choices=["basic", "deep"], default="basic")
    coll.add_argument("--previous-report", help="指定复用报告；默认在当前报告目录自动选择")
    rep = sub.add_parser("report", help="校验语义账本，新增报告版本")
    rep.add_argument("--snapshot", required=True)
    rep.add_argument("--tasks")
    rep.add_argument("--revises", help="被更正的报告目录")
    rep.add_argument("--reason", help="本次完整账本更正原因，与 --revises 成对使用")
    rep.add_argument("--baseline", help="显式前期报告目录；核对基础输入并重算同类趋势")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = {"configure": configure, "collect": collect, "report": report}[args.command](args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Relatra: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

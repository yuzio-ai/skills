# YUZIO Skills

**English** · [中文](README.zh-CN.md)

Reusable agent skills, maintained in one place. Installation is left to general-purpose tooling; task context stays in each project.

| Skill | Purpose | Entry |
|---|---|---|
| cohestra | Initializes project context; the six stages can start from any stage; initializes first when the container is missing; uses verify to check for drift between stages | [SKILL.md](cohestra/SKILL.md) |
| cadra | Manages task preparation, queue, order, status, recovery and run reports; serial unattended execution; single-task engineering flow is delegated to Cohestra stages | [SKILL.md](cadra/SKILL.md) |

## cohestra

One collaboration is split into six stages — **need → design → code → review → fix → validate** — plus `init`, which creates the project container, and `verify`, which checks for drift between stages. The six stages are a list of responsibilities, not a mandatory route: any stage can be the starting point, and the user decides where the work ends.

Every task README carries a machine-readable contract as YAML front matter — task status, stage result, candidate, blocking state, the next stage and whether continuing is allowed — so an external orchestrator can drive single-stage calls without parsing prose; the fields and enums are defined in the common flow, section 7. The Markdown body stays human-readable. Cohestra runs one stage per call, stops when the stage ends, and knows nothing about queues or schedulers: orchestration stays outside the skill.

The rules and stage prompts live inside the skill package (currently documented in Chinese); this file is only a guide. The sources of truth are the files below.

| To learn about | Read |
|---|---|
| Routing, execution rules, version and provenance | [cohestra/SKILL.md](cohestra/SKILL.md) |
| Common flow, terminology, artifact and shared-write rules | [references/workflow.md](cohestra/references/workflow.md) |
| Per-stage responsibilities, with copy-pasteable invocation snippets | [references/](cohestra/references/) |
| Handoff and task-index skeletons | [assets/](cohestra/assets/) |
| Install, update and tool boundaries | [references/installation.md](cohestra/references/installation.md) |
| Maintainer acceptance checklist | [tests/cohestra-scenarios.md](tests/cohestra-scenarios.md) |

## cadra

Cadra is task orchestration: it manages task preparation, queue, order, status, recovery and run reports, and advances queued tasks serially in unattended runs. It does not define the engineering stages — those belong to Cohestra; Cadra only declares a stage sequence (flow preset) and calls Cohestra stages, driven strictly by Cohestra's machine-readable state.

A task moves through **draft → ready → queued → running → completed / blocked / failed**; a run is serial (`parallelism = 1`) and ends as completed, stopped or interrupted, and `resume` continues unfinished runs from persisted state without repeating finished tasks or finished stages. A run is only created after the target passes the Git / `.cohestra` precondition check. Dependency chains advance one layer per run: a task passes the Ready Gate and enters the queue only after every dependency is completed, so a run never holds a task together with an unfinished dependency.

For a new task without any prior delivery or call, `run` starts at the first stage in its flow. To recover blocked or failed tasks, explicitly select them in a new `run`; the previous run keeps its recorded outcome. Editing the definition of a task that already reached a terminal state sends it back to draft and through the Ready Gate again, with the old and new definitions kept side by side. Requirement or flow changes restart at the new flow's first stage. Changes limited to dependencies or execution policy retry the verified pending stage for blocked/failed tasks, or close the revision without a stage call for completed tasks. Task definitions cannot be edited while their run is unfinished. Unattended execution is bounded by three limits: a per-stage failure retry budget (2 extra calls), a remediation-round cap (3 rounds) and a per-task call budget (16 calls); exhausting any of them records `failed` and adds the task to the human-intervention list. The no-progress check fires only when two consecutive calls of the same stage leave every structured field unchanged; the validate in-stage evidence backfill is exempt and bounded by the call budget instead. Enqueue and dequeue use a three-step write with an operation id, and `resume` idempotently completes a partially written enqueue or dequeue. An existing seven-column queue list is not migrated: a new eight-column block is appended and used from then on.

| To learn about | Read |
|---|---|
| Routing, execution rules, boundaries, version and provenance | [cadra/SKILL.md](cadra/SKILL.md) |
| Task/Run state machines, queue order, flow presets, Cohestra contract, unattended rules | [references/workflow.md](cadra/references/workflow.md) |
| Per-entry responsibilities (add / ready / list / run / resume / report) | [references/](cadra/references/) |
| Task and run skeletons, `.cadra` container template | [assets/](cadra/assets/) |
| Maintainer acceptance checklist | [tests/cadra-scenarios.md](tests/cadra-scenarios.md) |

## Install

Run from the root of the target project; the default scope is project-level:

```sh
npx skills add yuzio-ai/skills --skill cohestra
npx skills add yuzio-ai/skills --skill cadra
```

Add `-g` for a user-level install, or `-a <tool-a> <tool-b>` to target specific tools. If the source repository has not been pushed yet, use a local absolute path as the source instead. Installing does not initialize the project; if you would rather not use this CLI, you can also place the complete [cohestra](cohestra/) or [cadra](cadra/) directory where your tool looks for skills.

The full command set, how to update, and how to diagnose a local source that silently no-ops when updated by name are in the [installation guide](cohestra/references/installation.md).

## Invocation

The examples below are skill invocations typed into an agent, not terminal commands; other tools use their own entry points. When the target project has no `.cohestra`, the skill warns first and runs a minimal initialization, then starts from the stage you need, reading only the corresponding stage file each time.

```text
$cohestra init

$cohestra need
需求：<目标、范围、约束和参考>

$cohestra design
需求：<要探索的页面与目标>
参考：<截图、现状链接或设计规范>

$cohestra code
需求：<改动内容与范围>
参考：<相关文件、接口文档或截图>

$cohestra review
.cohestra/handoffs/<task-slug>/code-01.md

$cohestra fix
问题：<症状、预期行为、范围和参考>

$cohestra validate
.cohestra/handoffs/<task-slug>/review-01.md

$cohestra verify
被核对：.cohestra/handoffs/<task-slug>/design-01.md
上游依据：.cohestra/handoffs/<task-slug>/need-01.md
```

The argument labels in these examples (需求 / 参考 / 问题 / 被核对 / 上游依据) are Chinese because the skill's own prompts are written in Chinese; keep them as shown, only the placeholders change. A handoff path may also be replaced by the corresponding task directory, whose task README points to the valid inputs. Starting-point selection, stop rules and each stage's paired verify convention are in [cohestra/SKILL.md](cohestra/SKILL.md) and the [common flow](cohestra/references/workflow.md).

Cadra invocations manage the task queue around those stages; when the target project has no `.cadra`, the skill warns first and runs a minimal initialization:

```text
$cadra add
任务：<title>
需求：<目标、范围与验收条件>

$cadra ready
任务：<task-slug>

$cadra list

$cadra run
范围：<task-slug 列表，或“全部 ready”>
恢复：<blocked/failed task-slug 列表；可空，有值时必须包含在显式范围中>

$cadra resume
Run：<run-id>

$cadra report
Run：<run-id>
```

The labels are Chinese for the same reason as above. Task state lives in `.cadra`; the single-task flow and engineering evidence live in `.cohestra`, linked by reference and never copied across. The state machines, Ready Gate, Cohestra call contract and unattended rules are in [cadra/references/workflow.md](cadra/references/workflow.md).

## Maintenance

Release **0.9.0**, collaboration protocol **v0.8**; cadra is release **0.5.0**, task/run protocol **v0.5**. Release versions are maintained in [cohestra/release.json](cohestra/release.json) and [cadra/release.json](cadra/release.json). When the Cohestra collaboration protocol version changes, Cadra must ship a matching release that supports the new contract; until then Cadra runs stop at the contract-not-ready check. The skills are only Markdown, templates and metadata: no Python dependency and no installer of their own. This README has a Chinese counterpart at [README.zh-CN.md](README.zh-CN.md); keep both in sync when the content changes.

After any change, check routing, documentation links, temporary installation and the handoff flow against the [cohestra scenarios](tests/cohestra-scenarios.md), and the task-orchestration rules against the [cadra scenarios](tests/cadra-scenarios.md). File-integrity checks and real agent invocations are reported separately; without an independent agent run, a desktop walkthrough is not written up as a measured result. Flow-semantics changes update the protocol version separately. Commits, pushes and release tags still require explicit authorization. License: [MIT](LICENSE).

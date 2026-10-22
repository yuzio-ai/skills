# YUZIO Skills

**English** · [中文](README.zh-CN.md)

Reusable agent skills, maintained in one place. Installation is left to general-purpose tooling; task context stays in each project.

| Skill | Purpose | Entry |
|---|---|---|
| cohestra | Initializes project context; six stages can start from any stage; verify checks drift; report provides a read-only overview of tasks and outstanding findings | [SKILL.md](cohestra/SKILL.md) |
| cadra | Manages task preparation, queue, order, status, recovery and run reports; serial unattended execution; single-task engineering flow is delegated to Cohestra stages | [SKILL.md](cadra/SKILL.md) |
| relatra | Reports agent outcomes, execution efficiency, rework and observed usage across selected projects; daily through yearly, Codex first, with evidence and visible unknowns | [SKILL.md](relatra/SKILL.md) |
| vistra | Reviews, explores, compares and hands off mobile, desktop and brand visuals using project rules and traceable evidence | [SKILL.md](vistra/SKILL.md) |

## cohestra

One collaboration is split into six stages — **need → design → code → review → fix → validate** — plus `init`, which creates the project container, `verify`, which checks for drift between stages, and `report`, which provides a read-only overview of project tasks and outstanding findings. The six stages are a list of responsibilities, not a mandatory route: any stage can be the starting point, and the user decides where the work ends. When no stage is named, a clear task goal selects the starting stage automatically; each call still executes one stage. Verify runs on request and is suggested only for a concrete drift concern.

Every task README carries a machine-readable contract as YAML front matter — task status, stage result, candidate, blocking state, the next stage and whether continuing is allowed — so an external orchestrator can drive single-stage calls without parsing prose; the fields and enums are defined in the common flow, section 7. The Markdown body stays human-readable. Cohestra runs one stage per call, stops when the stage ends, and knows nothing about queues or schedulers: orchestration stays outside the skill.

`report` reads all tasks in the current project's `.yuzio/cohestra/handoffs/`, including completed tasks with open findings. It shows task and acceptance states, outstanding findings and state inconsistencies, with source links; missing values stay unknown. Output stays in the conversation: it does not initialize projects, write files, advance stages or change deferral and closure rules.

The rules and stage prompts live inside the skill package (currently documented in Chinese); this file is only a guide. The sources of truth are the files below.

| To learn about | Read |
|---|---|
| Routing, execution rules, version and provenance | [cohestra/SKILL.md](cohestra/SKILL.md) |
| Common flow, terminology, artifact and shared-write rules | [references/workflow.md](cohestra/references/workflow.md) |
| Per-stage responsibilities, with copy-pasteable invocation snippets | [references/](cohestra/references/) |
| Read-only task overview, outstanding findings and state inconsistencies | [references/report.md](cohestra/references/report.md) |
| Handoff and task-index skeletons | [assets/](cohestra/assets/) |
| Install, update and tool boundaries | [references/installation.md](cohestra/references/installation.md) |
| Maintainer acceptance checklist | [tests/cohestra-scenarios.md](tests/cohestra-scenarios.md) |

## cadra

Cadra prepares tasks and manages execution order, state, recovery and reports, calling Cohestra stages serially in unattended runs. Task files hold definitions, revisions, draft/ready preparation state and the Ready Gate. Run files hold the ordered task list, execution state, checkpoints and fixed results. `list` derives current task and queue views from explicit Run provenance; no separate queue file is maintained.

A flow accepts a preset or a nonempty stage list: its first entry is the start, and its distinct entries are the allowed stages. Intermediate order does not prescribe execution order. First execution starts there; subsequent calls follow Cohestra's legal `next`. Required follow-up outside the allowed set blocks the task. Dependencies must be completed for their current definitions before admission; dependency chains advance one layer per Run.

A project has at most one unfinished Run, whose tasks cannot be edited. `resume` continues that Run; explicit recovery of blocked/failed tasks starts a new Run without changing old outcomes. Definition changes affecting admission return preparation to draft. Definitions already included in a Run get a new revision, pass the Gate again, and restart or close by verification according to the changed fields. Historical reports use the original Run snapshots.

Execution has three limits: two extra failure retries per stage, three remediation rounds and sixteen total calls per task per Run. Identical summary fields do not cause early termination. Call intent, budget and result are stored in one Run file using validated temporary-file replacement and readback. Uncertain dispatch or delivery stops execution rather than triggering a blind retry. Only the current task/Run protocol is supported; old records are not automatically migrated.

| To learn about | Read |
|---|---|
| Routing, execution rules, boundaries, version and provenance | [cadra/SKILL.md](cadra/SKILL.md) |
| Task/Run state machines, queue order, flow presets, Cohestra contract, unattended rules | [references/workflow.md](cadra/references/workflow.md) |
| Per-entry responsibilities (add / ready / list / run / resume / report) | [references/](cadra/references/) |
| Task and run skeletons, `.yuzio/cadra` container template | [assets/](cadra/assets/) |
| Maintainer acceptance checklist | [tests/cadra-scenarios.md](tests/cadra-scenarios.md) |

## relatra

Relatra supports personal reviews: daily, weekly, monthly, quarterly, yearly and custom periods. It counts independent goals, separates delivery from acceptance, and preserves missing time/token data as unknown. Defaults are the previous complete calendar period and Asia/Shanghai. Configure a project set and report directory once; receive a chat summary, versioned Markdown, statistics JSON and provenance.

The adapter reads Codex active/archived logs and references existing Cadra/Cohestra evidence. The agent interprets goals and delivery proof; Python 3.9+ standard-library scripts deduplicate and aggregate. Reviewed ledgers are reused by default; only new activity, changed evidence and open goals need review. Basic mode produces a concise results report; explicit requests for efficiency, rework or intervention analysis use deep mode. Explicit baseline comparisons remain available. Corrections create a new full-ledger version with a reason and preserve old reports; patch-based corrections are removed. Relatra does not execute original tasks or create a scheduler.

```text
$relatra weekly
Projects: <explicit project set>
Report directory: <absolute path, reused later>

$relatra monthly
Date: 2026-09-15

$relatra
Range: 2026-10-01 through 2026-10-12
```

See [the skill](relatra/SKILL.md), [data and invocation](relatra/references/data.md), and [metrics](relatra/references/metrics.md). Offline tests: `python3 -B -m unittest discover -s tests -p 'test_relatra.py'`. These fixtures do not establish real agent usability or complete cloud-history coverage.

Current 0.2.0/schema v2 checks are recorded in [simplification validation](tests/relatra-simplification-validation.md). Old files remain readable without automatic migration; recomputation requires fresh configuration and collection. Historical plan coverage, review fixes, and native skill validation are recorded in [Relatra acceptance](tests/relatra-scenarios.md). Isolated installation, full invocation and minimum-runtime checks are recorded in [pre-push validation](tests/relatra-prepush.md).

## Local execution data and project documents

`.yuzio/` contains execution data local to the current project workspace. Before writing, the four skills maintain `/.yuzio/` in the project root `.gitignore`; installation and read-only entrypoints do not modify the project. Already tracked files are reported, not automatically untracked. Nested test fixtures remain outside this root-only rule.

- Task state, stage handoffs, queues, checkpoints, candidates, snapshots and reproducible ledgers stay local. Ignored data is neither disposable nor automatically backed up.
- Skills assess task goals, delivery purpose and applicable project rules, then automatically prepare or update the necessary formal documents without a separate request. Prefer existing project documents, falling back to `docs/` when no directory convention exists. Required conclusions and attachments must remain readable without `.yuzio`. Process records without a formal delivery need stay local; read-only entrypoints and explicit output limits remain unchanged.
- Execute and continue tasks in the current project workspace. Recover from existing task records and checkpoints, preserving rounds and budgets. Report missing data instead of guessing execution state.

Each standalone package carries its own contract: [Cohestra](cohestra/references/storage.md), [Cadra](cadra/references/storage.md), [Vistra](vistra/references/storage.md), [Relatra](relatra/references/storage.md).

## vistra

Vistra supports four independent modes: `review`, `explore`, `compare`, and `handoff` for static mobile, desktop, and brand visuals. It directly generates or edits images using the host's image capabilities, respects project and user UI/UX rules, and separates recommendations, selected directions, implementation authorization, and validation. It does not build HTML pages, interactive prototypes, or local rendering tools.

The package owns customized Taste-derived methods; Taste is not a runtime dependency. Local process records and exploratory images default to `.yuzio/vistra`; formal design deliveries belong in the project documentation directory. Cohestra, Cadra and Relatra project data uses `.yuzio/cohestra`, `.yuzio/cadra` and `.yuzio/relatra`, respectively. Storage path changes do not alter skill installation paths; protocols follow each skill’s version notes. The current storage convention provides no legacy-directory migration, fallback reads or dual writes; historical release and validation records retain their original version scope. Vistra does not modify production code or publish engineering acceptance.

```text
$vistra review
Object: <page, asset or source>
Scope: <questions to inspect>

$vistra explore
Goal: <visual directions and constraints>

$vistra compare
Candidates: <exact artifact revisions>

$vistra handoff
Selected: <candidate and selection source>
```

Current workspace version **0.1.2** keeps formal artifact contract **1**. Profile format **2** retains sources and defaults and is incompatible with v1 domain, target and import inheritance. Old profiles are not migrated automatically; only work independent of that configuration may continue. Everyday responses use concise mode-specific content; formal reports and cross-skill handoffs retain full traceability. Configuration details and provenance load only when needed. See the [entrypoint](vistra/SKILL.md), [development Spec](docs/vistra-v0.1-development-spec.md), [current validation](tests/workspace-review-validation.md), [historical 0.1.1 checks](tests/vistra-simplification-validation.md), and [historical 0.1.0 checks](tests/vistra-release-validation.md). This update does not install or publish the skill. Offline checks: `python3 -B -m unittest discover -s tests -p 'test_vistra*.py'`.

## Install

Run from the root of the target project; the default scope is project-level:

```sh
npx skills add yuzio-ai/skills --skill cohestra
npx skills add yuzio-ai/skills --skill cadra
npx skills add yuzio-ai/skills --skill relatra
npx skills add yuzio-ai/skills --skill vistra
```

Add `-g` for a user-level install, or `-a <tool-a> <tool-b>` to target specific tools. If the source repository has not been pushed yet, use a local absolute path as the source instead. Installing does not initialize the project; if you would rather not use this CLI, you can also place the complete [cohestra](cohestra/), [cadra](cadra/), [relatra](relatra/), or [vistra](vistra/) directory where your tool looks for skills.

The full command set, how to update, and how to diagnose a local source that silently no-ops when updated by name are in the [installation guide](cohestra/references/installation.md).

## Invocation

The examples below are skill invocations typed into an agent, not terminal commands; other tools use their own entry points. When the target project has no `.yuzio/cohestra`, stage calls warn first and run a minimal initialization, then start from the stage you need, reading only the corresponding stage file each time. `report` only reports the missing container and does not initialize it.

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
.yuzio/cohestra/handoffs/<task-slug>/code-01.md

$cohestra fix
问题：<症状、预期行为、范围和参考>

$cohestra validate
.yuzio/cohestra/handoffs/<task-slug>/review-01.md

$cohestra verify
被核对：.yuzio/cohestra/handoffs/<task-slug>/design-01.md
上游依据：.yuzio/cohestra/handoffs/<task-slug>/need-01.md

$cohestra report
```

The argument labels in these examples (需求 / 参考 / 问题 / 被核对 / 上游依据) are Chinese because the skill's own prompts are written in Chinese; keep them as shown, only the placeholders change. A handoff path may also be replaced by the corresponding task directory, whose task README points to the valid inputs. Automatic stage selection, stop rules and on-demand verify are in [cohestra/SKILL.md](cohestra/SKILL.md) and the [common flow](cohestra/references/workflow.md).

Cadra invocations manage the task queue around those stages; when the target project has no `.yuzio/cadra`, the skill warns first and runs a minimal initialization:

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

The labels are Chinese for the same reason as above. Task state lives in `.yuzio/cadra`; the single-task flow and engineering evidence live in `.yuzio/cohestra`, linked by reference and never copied across. The state machines, Ready Gate, Cohestra call contract and unattended rules are in [cadra/references/workflow.md](cadra/references/workflow.md).

## Maintenance

Release **0.10.1**, collaboration protocol **v0.8**; cadra is release **0.6.0**, task/run protocol **v0.6**; Relatra is **0.2.0**, report schema **v2**. Versions are maintained in [cohestra/release.json](cohestra/release.json), [cadra/release.json](cadra/release.json), and [relatra/release.json](relatra/release.json). Cohestra protocol changes require a compatible Cadra release. Cohestra/Cadra use Markdown, templates and metadata; Relatra additionally requires Python 3.9+ with no third-party runtime packages. None provides an installer. This README has a Chinese counterpart at [README.zh-CN.md](README.zh-CN.md); keep both in sync.

After any change, check routing, documentation links, temporary installation and the handoff flow against the [cohestra scenarios](tests/cohestra-scenarios.md), and the task-orchestration rules against the [cadra scenarios](tests/cadra-scenarios.md). File-integrity checks and real agent invocations are reported separately; without an independent agent run, a desktop walkthrough is not written up as a measured result. Flow-semantics changes update the protocol version separately. Commits, pushes and release tags still require explicit authorization. License: [MIT](LICENSE).

# YUZIO Skills

**English** · [中文](README.zh-CN.md)

Reusable agent skills maintained in one repository. Each skill directory is a complete installation unit; repository tests and maintenance documents are not runtime dependencies.

## Skills

| Skill | Purpose | Entry | Version and protocol |
|---|---|---|---|
| cohestra | Initializes project context and runs engineering stages, drift checks and read-only reports as needed | [SKILL.md](cohestra/SKILL.md) | [release.json](cohestra/release.json) |
| cadra | Prepares tasks, calls Cohestra serially, and manages execution state and recovery | [SKILL.md](cadra/SKILL.md) | [release.json](cadra/release.json) |
| relatra | Reports agent outcomes, outstanding work and observed usage across selected projects | [SKILL.md](relatra/SKILL.md) | [release.json](relatra/release.json) |
| vistra | Reviews, explores, compares and hands off static mobile, desktop and brand visuals | [SKILL.md](vistra/SKILL.md) | [release.json](vistra/release.json) |

Each package owns its execution rules. Cohestra executes one stage per call; Cadra requires an available Cohestra skill to execute engineering stages. Relatra requires Python 3.9+ and uses only the standard library. Vistra requires host image capabilities to generate or edit images.

## Install

Run the installation command for each skill you need from the target project's root:

```sh
npx skills add yuzio-ai/skills --skill cohestra
npx skills add yuzio-ai/skills --skill cadra
npx skills add yuzio-ai/skills --skill relatra
npx skills add yuzio-ai/skills --skill vistra
```

Installation defaults to project scope; add `-g` for user scope or `-a <tool-a> <tool-b>` to select tools. Use the source repository's absolute path for unpublished local content. Alternatively, copy the complete skill directory to a location supported by the host, including references, templates, scripts and hidden files. Installation does not initialize business projects.

See the [installation guide](cohestra/references/installation.md) for installation, updates and troubleshooting.

## Invocation

After installation, enter `$skill-name entry` in the agent chat, followed by the project, target, goal and constraints. The examples below are **chat prompts, not terminal commands**. Replace `<…>` with actual values; other hosts use their own skill invocation syntax. Examples retain the Chinese labels used in the skill prompts.

Cohestra and Cadra default to the current task's project. Relatra needs a defined project set; Vistra needs a clear design target. Discussing skill rules does not start execution.

### Cohestra

Advance one engineering task. Start at any stage; **each call executes one stage**. If no entry is specified, the skill selects one based on the goal.

| Entry | Purpose |
|---|---|
| `init` | Initialize or reuse project context without executing a task |
| `need` | Clarify requirements, scope and acceptance criteria |
| `design` | Define the approach, implementation plan and validation methods |
| `code` | Implement an established design |
| `review` | Review a fixed candidate and report findings |
| `fix` | Assess and fix review findings |
| `validate` | Gather validation evidence and assess acceptance |
| `verify` | Check a stage's output against its upstream basis for drift |
| `report` | Read-only overview of project tasks, outstanding work and state anomalies |

```text
$cohestra design
项目：<项目绝对路径>
需求：为搜索增加历史记录，最多保存 20 条，支持单条删除和清空。
```

To continue a task, attach the previous handoff file or task directory. Stage calls announce and minimally initialize missing project context; `report` neither initializes nor writes files. Execution data lives in `.yuzio/cohestra`; necessary formal documents follow project conventions.

Full rules: [Cohestra](cohestra/SKILL.md).

### Cadra

Prepare tasks, execute them serially and recover interrupted runs. Engineering stages require an available Cohestra skill.

| Entry | Purpose |
|---|---|
| `add` | Create or edit a task's requirements, priority, dependencies and flow |
| `ready` | Check whether goals, scope, acceptance criteria, inputs and dependencies permit execution |
| `list` | Read-only view of tasks, queues and runs |
| `run` | Create a run and execute tasks serially; defaults to all ready tasks |
| `resume` | Continue or finalize an unfinished run |
| `report` | Generate a summary file for a run and register its report link |

Send these calls separately. Use the task slug returned by `add`:

```text
$cadra add
项目：<项目绝对路径>
任务：搜索历史
需求：最多保存 20 条搜索记录，支持单条删除和清空；重启后仍保留。
流程：feature

$cadra ready
任务：<slug>

$cadra run
范围：<slug>
```

Flow presets: `full` starts at requirements, `feature` at design, `small-change` at implementation, `bugfix` at fixes, and `review-only` permits only review. Later stages follow actual handoff results.

`add` and `ready` do not execute engineering stages. A project can have at most one unfinished run. Dependencies must be completed before a task is admitted. Use `resume` for an interrupted run; failed tasks in a finished run require an explicit recovery selection and a new `run`. Definitions and execution records live in `.yuzio/cadra`.

Full rules: [Cadra](cadra/SKILL.md).

### Relatra

Review personal project outcomes through daily, weekly, monthly, quarterly, yearly or custom date-range reports.

```text
$relatra 周报
项目：<项目绝对路径，可明确列出多个项目>
报告目录：<报告目录绝对路径>
```

Defaults are the previous complete calendar period, Chinese and Asia/Shanghai time, with weeks running Monday through Sunday. Request “this week through now” for the current period, or specify another output language. Ask explicitly for rework, human intervention or waiting analysis when needed.

Basic mode covers outcomes, status, outstanding work, observable time and tokens. Efficiency diagnosis uses deep mode. A single project defaults to `<project>/.yuzio/relatra`; multiple projects need an explicit shared report directory. Historical reports can be corrected while preserving earlier versions.

Requires Python 3.9+. Relatra summarizes evidence without executing source tasks or changing their state. Missing observations are not treated as zero. Scheduling requires separate automation.

Full rules: [Relatra](relatra/SKILL.md).

### Vistra

Review and explore static mobile, desktop and brand visuals. Supply a screenshot, asset, source code or exact candidate, and specify what may change.

| Entry | Purpose |
|---|---|
| `review` | Inspect an existing screen or asset and provide findings and recommendations |
| `explore` | Generate or edit images to explore layouts, colors, logos and other directions |
| `compare` | Compare existing candidates and explain tradeoffs |
| `handoff` | Record the selected candidate and adoption scope, then prepare a design handoff |

```text
$vistra explore
对象：<页面截图或设计素材>
目标：探索 3 个视觉方向，突出主要操作。
约束：保留文案、功能和导航，仅调整布局、层级和配色。
```

Exploration of multiple directions defaults to 3 directions and at most one targeted revision round. You can specify another budget. Image generation and editing require host image capabilities.

With existing candidates in context, “use B” records the choice and starts handoff. Say so explicitly if you only want to record the choice. Handoffs remain drafts when key decisions or assets are missing. Vistra does not modify production code or create HTML or interactive prototypes. Static images do not establish engineering acceptance.

Full rules: [Vistra](vistra/SKILL.md).

### Combined usage

Use Cohestra for one engineering task, or Cadra to dispatch multiple prepared tasks serially through Cohestra. For visual work, use Vistra to explore and hand off a selected design, then explicitly request implementation. Use Relatra for periodic reviews of existing records.

For status reporting, `cohestra report` shows project tasks, `cadra report` generates a run summary, and `relatra` produces a period report of outcomes and observed usage.

#### Complete example

For a search-history feature: Cohestra clarifies requirements → Vistra explores and hands off the visual design → Cadra dispatches Cohestra for implementation and validation → Relatra reviews the outcomes.

Send the calls below in the same target project, waiting for each result before proceeding. Replace paths, candidate versions, slugs and run IDs with actual returned values. All 4 skills must be installed; the project must be a Git working tree with image capabilities and the required validation environment available.

1. Clarify requirements and resolve product decisions that affect implementation.

   ```text
   $cohestra need
   项目：<项目绝对路径>
   需求：为现有搜索页增加历史记录，最多 20 条，支持单条删除和清空，重启后仍保留。
   范围：不改搜索算法和其他页面；明确交互规则与验收条件。
   ```

2. Use the requirements handoff and existing screen to explore visual directions.

   ```text
   $vistra explore
   项目：<同一项目绝对路径>
   依据：<need 返回的需求交付文件绝对路径>
   对象：<现有搜索页截图或源码路径>
   目标：探索 3 个搜索历史区域的视觉方向。
   约束：沿用品牌、文案和导航，不增加需求以外的功能。
   ```

3. Inspect the candidates, choose one and request a formal handoff. Resolve missing key decisions or assets before proceeding.

   ```text
   $vistra handoff
   项目：<同一项目绝对路径>
   选择：<已查看并确定采用的候选及准确版本>
   要求：保存正式交接，明确采用范围、组件映射和未决项，供后续工程设计使用。
   ```

4. Create an engineering task using the requirements and visual handoff as inputs. The `feature` flow starts at engineering design without repeating requirements. To continue the same Cohestra task, provide its task directory and explicitly confirm the binding.

   ```text
   $cadra add
   项目：<同一项目绝对路径>
   任务：搜索历史功能
   需求：实现已确认的搜索历史需求和视觉方案；不改搜索算法和其他页面。
   输入：<需求交付文件绝对路径>、<Vistra 正式交接文件绝对路径>
   验收：最多 20 条，单条删除与清空有效，重启后保留；按需求交付中的完整验收条件验证。
   流程：feature
   ```

5. Send `ready`, `run` and `report` separately. Start `run` only after admission passes. Cadra invokes Cohestra design, implementation, review, fixes and validation as actual results require. Use `resume` first if the run is interrupted.

   ```text
   $cadra ready
   任务：<add 返回的 slug>

   $cadra run
   范围：<同一 slug>

   $cadra report
   Run：<run 返回的 run-id>
   ```

6. Review actual outcomes for the current week through now. Supply the visual handoff reference explicitly; do not assume Relatra automatically collects the Vistra directory. Incomplete work and outstanding acceptance remain visible.

   ```text
   $relatra 周报
   项目：<同一项目绝对路径>
   周期：本周截至现在
   补充证据：<Vistra 正式交接文件绝对路径>
   关注：搜索历史功能的实际交付、验收状态、遗留问题和可观测资源。
   ```

| Details | Entry |
|---|---|
| Cohestra stages, handoffs and contract | [Common flow](cohestra/references/workflow.md) |
| Cadra preparation, execution and recovery | [Common flow](cadra/references/workflow.md) |
| Relatra data calls and metrics | [Data and invocation](relatra/references/data.md) · [Metrics](relatra/references/metrics.md) |
| Vistra modes, project rules and configuration | [Modes](vistra/references/modes) · [Project adaptation](vistra/references/project-adapter.md) |

## Local execution data and project documents

`.yuzio/` stores execution data local to the current workspace and is excluded by `/.yuzio/` in the root `.gitignore`. Ignored data is neither disposable nor automatically backed up. Formal conclusions and attachments that need to be shared belong in project documentation and must remain readable without local execution data.

Each standalone package carries its own rules: [Cohestra](cohestra/references/storage.md) · [Cadra](cadra/references/storage.md) · [Relatra](relatra/references/storage.md) · [Vistra](vistra/references/storage.md).

## Maintenance and checks

Run all automated checks from the repository root:

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

See the [test guide](tests/README.md) for test layout, per-skill commands and acceptance scenarios. Checks cover package metadata, document links, resource integrity in isolated copies and offline regressions. Actual installer behavior, agent execution and visual acceptance are validated separately.

Versions and protocols are maintained in each package's `release.json`. See the [maintenance and versioning rules](AGENTS.md#版本管理) for bump criteria, compatibility and pre-commit checks. Keep both README languages in sync. Commits, pushes and release tags require explicit authorization. License: [MIT](LICENSE).

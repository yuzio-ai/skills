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

Enter these examples in an agent, not a terminal. Replace the placeholders with task details; other hosts use their own entry points. The examples retain the Chinese labels used in the skill prompts.

```text
$cohestra code
需求：<目标、范围、验收条件>

$cadra add
任务：<任务名称>
需求：<目标、范围、验收条件>

$relatra 周报
项目：<明确项目集合>
报告目录：<绝对路径>

$vistra review
对象：<页面、素材或源码>
范围：<评审问题>
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

Versions and protocols are maintained in each package's `release.json`; this README does not duplicate version values. Cohestra protocol changes require a Cadra compatibility check. Keep both README languages in sync; update protocols separately when flow semantics change. Commits, pushes and release tags require explicit authorization. License: [MIT](LICENSE).

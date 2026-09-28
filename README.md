# YUZIO Skills

**English** · [中文](README.zh-CN.md)

Reusable agent skills, maintained in one place. Installation is left to general-purpose tooling; task context stays in each project.

| Skill | Purpose | Entry |
|---|---|---|
| cohestra | Initializes project context; the six stages can start from any stage; initializes first when the container is missing; uses verify to check for drift between stages | [SKILL.md](cohestra/SKILL.md) |

## cohestra

One collaboration is split into six stages — **need → design → code → review → fix → validate** — plus `init`, which creates the project container, and `verify`, which checks for drift between stages. The six stages are a list of responsibilities, not a mandatory route: any stage can be the starting point, and the user decides where the work ends.

The rules and stage prompts live inside the skill package (currently documented in Chinese); this file is only a guide. The sources of truth are the files below.

| To learn about | Read |
|---|---|
| Routing, execution rules, version and provenance | [cohestra/SKILL.md](cohestra/SKILL.md) |
| Common flow, terminology, artifact and shared-write rules | [references/workflow.md](cohestra/references/workflow.md) |
| Per-stage responsibilities, with copy-pasteable invocation snippets | [references/](cohestra/references/) |
| Handoff and task-index skeletons | [assets/](cohestra/assets/) |
| Install, update and tool boundaries | [references/installation.md](cohestra/references/installation.md) |
| Maintainer acceptance checklist | [tests/cohestra-scenarios.md](tests/cohestra-scenarios.md) |

## Install

Run from the root of the target project; the default scope is project-level:

```sh
npx skills add yuzio-ai/skills --skill cohestra
```

Add `-g` for a user-level install, or `-a <tool-a> <tool-b>` to target specific tools. If the source repository has not been pushed yet, use a local absolute path as the source instead. Installing does not initialize the project; if you would rather not use this CLI, you can also place the complete [cohestra directory](cohestra/) where your tool looks for skills.

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

## Maintenance

Release **0.8.0**, collaboration protocol **v0.7**. The release version is maintained in [release.json](cohestra/release.json). The skill itself is only Markdown, templates and metadata: it has no Python dependency and ships no installer of its own. This README has a Chinese counterpart at [README.zh-CN.md](README.zh-CN.md); keep both in sync when the content changes.

After any change, check routing, documentation links, temporary installation and the handoff flow against the [validation scenarios](tests/cohestra-scenarios.md). File-integrity checks and real agent invocations are reported separately; without an independent agent run, a desktop walkthrough is not written up as a measured result. Flow-semantics changes update the protocol version separately. Commits, pushes and release tags still require explicit authorization. License: [MIT](LICENSE).

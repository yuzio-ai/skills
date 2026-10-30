---
protocol: "0.11"
slug: <stable-slug>
title: <任务名>
revision: 1
preparation: draft
ready_scope: null
priority: medium
dependencies: []
flow: code
execution_policy:
  stop_queue_on_failure: false
cohestra_task: .yuzio/cohestra/handoffs/<stable-slug>/
revision_base: null
changed_fields: []
---

# <任务名>

## Requirement

<目标、范围、排除项、验收条件与必要输入；缺口明确列出>

## 绑定与修订

- 绑定确认：<无既有交付；或已有 Cohestra 任务主题、来源与用户确认>
- 创建：<执行者、带时区时间、实际 Skill 发行版本>
- 修改记录：<追加时间、来源、变更字段与原因；旧定义引用 Run 快照>

revision_base 有值时为 `{run: <run-id>, revision: <整数>}`，指向分代前该 slug 的链尾；changed_fields 累计影响 Gate 的变更。首次定义未进 Run 时 revision_base=null。消费记录只在 Run。

## Ready Gate

- 当前结论：<revision、通过/未通过、时间与依据>
- 八项：<目标、范围、验收、人类决定、输入、依赖、起点、范围配置的逐项结论>
- 历史：<保留旧放行及失效记录，不覆盖>

本文件不保存 queued/running/终态、所属 Run、调用结果或预算；查询通过 Run 来源链解析。

ready 通过时填写 `ready_scope: {revision: <当前修订>, scope: {mode: parallel, files: [], dirs: []}, inputs: {<相关输入路径>: <SHA-256 或 null>}}`。这是准入结果，不是资源占用；Gate 失效或 revision、范围、输入语义变化时清空，由 ready 重新计算；不确定范围用 mode=exclusive。路径与失效规则见 [小组调度](../references/scheduling.md)。

---
protocol: "0.6"
slug: <stable-slug>
title: <任务名>
revision: 1
preparation: draft
priority: medium
dependencies: []
flow: full
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

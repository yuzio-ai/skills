---
protocol: "0.12"
slug: <stable-slug>
title: <任务名>
revision: 1
preparation: draft
ready_scope: null
origin: null
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

### 设计输入

<有相关资料时填写：用途、来源／版本、本地保存路径（相对项目根）、实际 SHA-256、采集时间及缺口；无设计输入则省略本小节>

### 已确认设计结论

<有相关决定时填写：具体结论、适用范围／状态、被确认的完整方案版本、用户原始答复及可核对来源；整体认可、单项决定、代决授权、参考方案和待决定项分开标明。消息标识／时间未知不编造，无则省略本小节>

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

`origin` 普通任务为 null；生成收尾任务为 `{run: <来源 run-id>, round: <正整数>}`，只描述不可变来源，不能手工改绑。其内部准备、排除普通选择与准入规则见 [收尾审查](../references/closeout.md)。

---
contract: "<契约版本，随协作协议，如 0.8>"
task: <task-slug>
status: <in_progress|completed|blocked|failed>
execution_mode: <attended|unattended>
stage_result:
  stage: <need|design|code|review|fix|validate>
  status: <completed|blocked|failed>
  round: <阶段轮次>
candidate:
  commit: <sha>
  snapshot: <可复核快照来源>
findings:            # review/fix 交付后维护，可省
  blocking: <未关闭必做数>
  non_blocking: <非必做数>
  unresolved: <待核实未裁决数，可省>
acceptance:          # validate 交付后维护，可省
  status: <passed|failed|pending|blocked>
next:
  stage: <六阶段名>
  allowed: <true|false>
  reason: <stage_completed|blocking_findings|acceptance_failed|stage_failed|task_completed|human_decision_required|blocked|other>
blocked:
  value: <true|false>
  reason: <human_decision_required|missing_input|missing_permission|dependency_unavailable|environment_blocked|candidate_unavailable|other>
---

# <任务名称>

Front Matter 是机器可读契约（Orchestrator Contract），只反映最近一次正式阶段交付的控制状态，字段、枚举与写入时机见 [公共流程](../references/workflow.md) 第 7 节；正文是人类/智能体任务索引。两部分共同构成单一任务索引，不另建状态文件。占位符 `<a|b|c>` 表示该字段只写其中一个实际值，无值的叶子写 `null`（如 `next.stage`、`blocked.reason`、`candidate` 两叶），写出的 YAML 必须可被外部系统解析。必填字段为 contract、task、status、execution_mode、stage_result、candidate、next、blocked；findings、acceptance 为可选，缺省等价 `null`。`candidate` 形状恒为映射，无候选时写 `commit: null`、`snapshot: null`。

- 任务目标：<一句话>
- 流程范围：<起始阶段> → <当前阶段>；从中间阶段起步时写明起点及其依据的原始材料
- 当前执行：<阶段/轮次/状态；并行时逐项列出>
- 索引维护者：<串行交接时为当前执行者；并行时指定唯一维护者>
- 工作项状态（实现 / 作者自审 / 独立审查与复审 / 验收 / 提交发布）：<分别记录；尚未发生写未开始，不要求独立审查时写不要求及依据；与阶段状态互相独立>
- 当前候选：<固定版本及清单来源；已提交时写实际 commit，不把新工作区内容纳入历史候选；与 Front Matter 的 candidate 一致>
- 有效决定与确认来源：<需求/设计及用户局部修订的有效覆盖关系>
- 交付物链接（需求 / 设计 / 审查与复审 / 验收 / 偏差核对）：<独立文件或合并文件的章节链接；用户跳过核对时写明跳过及理由；尚无则说明>
- 待确认或已被取代的版本：<链接及原因，不能悄然替换有效版本>
- 下一步及前提：<动作、剩余证据、缺失条件、负责人或待指派、输入文件；与 Front Matter 的 next 一致>
- 最近更新：<执行者、实际时间及时区>

两类状态互相独立：`阶段状态` 指阶段本身（进行中／已结束／受阻／跳过，记在交付骨架），`工作项状态` 指上列五项。`verify` 不是六阶段之一，其文件编号独立于阶段轮次编排，登记时在「阶段/轮次」列写 `verify-<轮次>`；verify 行只更新正文，不改 Front Matter 控制字段。旧任务无 Front Matter 时，verify 不添加本模板中的契约；仅在首次正式阶段交付成功同步索引时加入本次状态，不补造历史。README 的 Front Matter 与正文作为完整文件原子发布，失败处理与回读规则见公共流程第 5 节。

| 阶段/轮次 | 交付物及覆盖职责 | 阶段状态与结论 | 输入/目标候选 |
|---|---|---|---|

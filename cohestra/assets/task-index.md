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

Front Matter 是唯一可变的当前控制状态，字段与枚举见[公共流程第 7 节](../references/workflow.md#7-机器可读契约orchestrator-contract)。占位符 `<a|b|c>` 只填一个实际值；无值叶子写 `null`，无候选时保留 candidate 映射及两个 null 叶子。必填字段不省略；findings、acceptance 按适用阶段写入。

正文只补充上下文与历史，不另设当前阶段、当前候选或下一阶段字段；不适用的下列可选条目省略。

- 任务目标：<一句话；首轮说明起始阶段和原始材料>
- 有效决定与确认来源：<有效需求、设计、局部修订和授权的来源链接>
- 正式文档：<需要时记录项目文档路径与版本>
- 待确认或已被取代的版本：<存在时记录链接及原因>
- 工作项记录：<有实际结果、明确要求或影响下一步的缺口时，分别记录实现、自审、独立审查与复审、验收、提交发布及其证据；不填整套未开始/不适用>
- 下一步补充：<对应 Front Matter.next 的准确输入、剩余证据、必要前提与责任人；终点无待办时省略>
- 索引维护者：<当前唯一写入者>
- 最近更新：<执行者、实际时间及时区>

工作项分别判断，省略记录不代表通过或不要求。历史表只登记实际交付；verify 使用独立编号且不改 Front Matter，缺契约时不补写。发布前读取[索引发布与恢复](../references/publication.md)。

| 阶段/轮次 | 交付物及覆盖职责 | 阶段状态与结论 | 输入/目标候选 |
|---|---|---|---|

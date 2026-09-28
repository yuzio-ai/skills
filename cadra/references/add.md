# add

通过 $cadra add 调用；与 [公共流程](workflow.md) 一起执行。创建 Task，或编辑已有 Task。

## 调用

```text
$cadra add
任务：<title>
需求：<requirement 目标、范围与验收条件>
优先级：<high / medium / low，可空取 medium>
依赖：<task-slug 列表，可空>
流程：<flow preset 名或显式阶段序列，可空取 full>
执行策略：<stop_queue_on_failure: true/false，可空取 false>
```

编辑已有任务时在首行给出现有 slug，并只带需要修改的字段与本次补充。

## 职责与工作

1. 先核对 `.cadra/tasks/` 中没有同 slug 任务：不存在则创建，存在则按编辑处理。slug 使用稳定英文短横线名称，不按工具、会话或执行者重复建任务。
2. 创建按 [任务骨架](../assets/task.md) 落盘 `.cadra/tasks/<task-slug>.md`，至少记录 title、slug、requirement、priority、dependencies、flow、execution policy，默认 `status: draft`；同时记录 `cohestra_task: .cohestra/handoffs/<task-slug>/` 引用、Skill 发行版本与创建时间。
3. requirement 写清目标、范围与验收条件；内容不足以判断时如实记为缺口，不编造。验收条件是 Ready Gate 的检查对象，也是后续 Cohestra 阶段的输入。
4. priority 取 `high` / `medium` / `low`，缺省 `medium`；flow 缺省 `full`（preset 含义见 [公共流程](workflow.md) 第 5 节）；execution policy 缺省 `stop_queue_on_failure: false`。
5. dependencies 必须指向已存在的 task-slug：悬空引用或形成环时拒绝创建/修改并列出问题，不建立指向不存在任务的依赖。
6. 编辑只按用户明确指示修改字段，记录修改来源、时间与影响范围，不悄然替换已确认内容。影响目标、范围或验收条件的重大变更，建议回 `draft` 重新执行 Ready Gate，是否回退由用户决定。
7. 只写本 Task 文件；不执行任务、不建 Run、不入队、不动 `.cohestra`。

## 交付与停止

新增或更新 `tasks/<task-slug>.md`；骨架字段与落盘规则见 [公共流程](workflow.md)。

推荐下一步 `ready`，传递 slug 与需要补充的缺口。派发：`$cadra ready`，后附任务 slug 及本次补充。

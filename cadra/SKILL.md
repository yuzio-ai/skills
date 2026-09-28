---
name: cadra
description: 通过 add 创建或编辑任务、ready 执行准入门、list 查看状态、run 按既定顺序无人值守串行推进、resume 中断恢复、report 输出执行摘要；管理任务准备、队列、顺序、状态、恢复和执行报告，结果落到 .cadra。单任务工程流程由 Cohestra 阶段提供，Cadra 只声明阶段序列并按机器可读状态调用；不并行、不调度 DAG、不做运行时；仅讨论流程不触发执行。
license: MIT
---

# Cadra

一个任务编排技能：管理多个待执行任务，并在无人值守场景下按既定顺序串行推进。Cadra = Task Orchestration，负责任务准备、队列、顺序、状态、恢复和执行报告；单个任务内部的工程流程协议由 Cohestra 提供，Cadra 只声明阶段序列并调用其阶段。技能版本见 [release.json](release.json)，任务与 Run 协议为 v0.1。Task、Run、Ready Gate、checkpoint、结构化状态等术语见 [公共流程](references/workflow.md)。

## 路由

`$cadra <入口>` 表示技能调用意图，不是终端命令；其他工具采用其技能调用写法。调用后附任务描述、任务 slug、run-id 或本次补充。

| 入口 | 按需读取 | 职责 |
|---|---|---|
| add | [add](references/add.md) | 创建或编辑 Task，落盘为 draft |
| ready | [ready](references/ready.md) | 执行 Ready Gate，draft → ready |
| list | [list](references/list.md) | 只读展示任务与 Run 状态 |
| run | [run](references/run.md) | 建立 Run 并无人值守串行执行 |
| resume | [resume](references/resume.md) | 从持久化状态恢复未完成 Run |
| report | [report](references/report.md) | 生成本轮执行摘要 |

## 执行规则

以下规则适用于所有入口。

1. 先固定目标项目绝对路径并读取适用项目规则；目标不因技能安装位置或切换目录而改变。未给路径时使用当前任务项目，多个候选无法区分时再询问。
2. 进入任何入口前先确认目标项目已有 `.cadra`：缺失时报告目标绝对路径并说明将执行一次最小初始化（只建容器与项目入口、`tasks/`、`queue/`、`runs/` 与忽略规则，不生成任务、不建 Run、不暂存或提交），完成后继续本入口；容器存在则直接进入，不重复初始化。目标不明确、指向技能源仓库或无法安全写入时不初始化，先澄清或报告。
3. 每次只读取 [公共流程](references/workflow.md)、所选入口说明和 [release.json](release.json)，写交付时再读对应骨架。不预读其他入口、全部任务或全部 Run 记录。
4. Cadra 只写 `.cadra`，不写 `.cohestra`：单任务流程与工程证据归 Cohestra，Cadra 通过 `cohestra_task` 引用关联，不把 handoff 内容复制进 `.cadra`。阶段的业务语义、review 与 validate 标准、代码修改均不属于 Cadra。
5. 只执行指定的入口，不因入口相邻或任务仍在队列内而自动继续；`run` 内部的串行推进属该入口自身行为，不算跨入口继续。用户只讨论流程或调用含义时解释清楚即可，不隐式建任务、不隐式启动 Run。
6. 不做并行执行、DAG 并发调度、OS 定时器、Runtime/daemon 或 Agent 动态选择；V1 `parallelism = 1`，同一项目同时至多一个未完成 Run。

## 边界

Cadra 负责：创建与编辑任务、Ready Gate、优先级、依赖关系、Queue、串行执行、Blocked/Failed 处理、中断恢复、Run Report、调用 Cohestra 阶段。

Cadra 不负责：定义 need/design/code/review/fix/validate 的具体规则；自己实现代码修改；自己定义 review 或 validate 标准；并行执行与 DAG 调度；OS 定时器；Runtime/daemon；Agent 动态选择。Cohestra 若尚未提供 Cadra 所需的机器可读状态，只在 [公共流程](references/workflow.md) 的调用契约中声明接口要求，不替另一个技能实现。

## 来源与版本

- 从本次实际加载的技能目录读取规则和模板，不从工作目录猜测技能位置。
- 每轮落盘记录实际 Skill 发行版本与任务/Run 协议版本；技能升级不改写任务定义、已确认决定或历史 Run 记录。
- 同名技能存在多份时使用明确选择的入口；无法确定来源时报告位置并澄清。
- 不提供 `update` 入口；升级交给技能管理器，项目需要独立固定版本时用项目级安装并随 Git 管理。

## 交付

结果必须先落盘再汇报。最终回复给出交付物绝对路径、任务或 Run 的状态结论、必要待办、需要人工介入的事项，以及下一步入口调用（`$cadra <入口>` 加准确输入，可直接执行）；无需复述整份文档。

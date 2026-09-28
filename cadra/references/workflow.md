# 公共流程 · cadra v0.1

Cadra 管理多个待执行任务，并在无人值守场景下按既定顺序串行推进。本文件定义 Task 与 Run 的状态机、队列与顺序、Flow Preset、Cohestra 调用契约、unattended 规则和落盘规则；入口特有行为见各入口说明。先读本文件与所选入口说明，再按需读取任务或 Run 材料。

## 术语

- **Task**：待执行任务，落盘为 `.cadra/tasks/<task-slug>.md`，记录 title、slug、requirement、priority、dependencies、flow、execution policy 与状态。
- **Ready Gate**：Task 从 `draft` 进入 `ready` 的准入检查，八条全部满足才放行，见 [ready](ready.md)。
- **Queue**：待执行队列，清单落盘为 `.cadra/queue/order.md`，记录入队顺序、消费 Run 与出队结果。
- **Run**：一次串行执行，落盘为 `.cadra/runs/<run-id>.md`；run-id 形如 `run-<YYYYMMDD>-<NN>`，当日序号两位起、不截断。
- **flow preset**：候选阶段序列，只声明序列与 Cohestra 起始阶段，不拥有阶段业务语义，见第 5 节。
- **execution policy**：Task 级执行策略，V1 只含 `stop_queue_on_failure`，缺省 `false`。
- **checkpoint**：Run 文件中每个 Task 的执行进度记录（最后完成阶段、当前候选引用、最近结构化状态、闭合标志），是 resume 的唯一恢复依据。
- **结构化状态**：Cohestra 按第 6 节「Cohestra 调用契约」提供的机器可读状态；Cadra 只读这些字段决定流程。
- **unattended**：无人值守执行模式，run 启动时向下游声明 `execution_mode: unattended`。
- **串行**：`parallelism = 1`。同一 Run 同一时间至多一个 Task 处于 `running`；不做并行执行、DAG 调度、定时器或 daemon。

## 1. 项目存储

```text
.cadra/
├── README.md          # 容器入口
├── tasks/
│   └── <task-slug>.md # Task 定义、状态与运行记录
├── queue/
│   └── order.md       # 队列清单
└── runs/
    ├── <run-id>.md          # Run 记录与 checkpoint
    └── <run-id>-report-<轮次>.md   # 执行摘要（report 入口生成）
```

职责划分：`.cadra` 保存多任务执行和调度状态；`.cohestra` 保存单任务流程与工程证据。不得把 Cohestra handoff 内容复制进 `.cadra`，一律通过引用关联：

```yaml
cohestra_task: .cohestra/handoffs/<task-slug>/
```

报告中的 findings 摘要、validation 结果等只写短摘要并标注来源文件，不搬运正文。容器缺入口文件时按 [SKILL.md](../SKILL.md) 执行规则第 2 条最小初始化。

## 2. Task 状态机

```text
draft
  ↓
ready
  ↓
queued
  ↓
running
  ├── completed
  ├── blocked
  └── failed
```

| 状态 | 含义 | 进入方式 |
|---|---|---|
| draft | 已创建或编辑，尚未通过 Ready Gate | `add` 创建/编辑后 |
| ready | 已通过 Ready Gate，可被选入队列 | `ready` 放行 |
| queued | 已入队，等待串行执行 | `run` 选中入队 |
| running | 正在执行 Cohestra 阶段 | `run`/`resume` 开始执行 |
| completed | 执行完成，Cohestra 流程闭合 | 结构化状态显示无下一阶段 |
| blocked | 任务本身无法继续 | 见下方定义 |
| failed | 执行发生异常 | 见下方定义 |

**blocked**：任务本身无法继续，例如缺人工决定、缺权限、缺输入、依赖未满足、Cohestra 明确禁止继续（`blocked.value = true`）。

**failed**：执行发生异常，例如 Agent 执行异常、工具调用失败、无法读取必要状态、协议输出不合法、无法恢复执行状态。

默认处理：

```text
blocked → 记录 → 继续下一个 Task
failed  → 记录 → 继续下一个 Task
```

Task 可显式配置 `stop_queue_on_failure: true`：该 Task 到达 `blocked` 或 `failed` 终态时停止队列，Run 记 `stopped` 并给出停止原因，队列内未执行的任务在报告中记 `skipped`（Task 状态保持 `queued`，`skipped` 只是报告分类，不是 Task 状态）。

状态只由 Cadra 写入 Task 文件，Cohestra 不回写 Task 状态；转换必须即时落盘，保证中断后可恢复。`blocked` 与 `failed` 是终态，回到队列须经 [resume](resume.md) 的核对规则，不自动重试。

## 3. Run 状态机

```text
running
  ├── completed    # 队列内 Task 全部到达终态（completed/blocked/failed）
  ├── stopped      # stop_queue_on_failure 触发，或用户显式停止
  └── interrupted  # 会话或执行中断，checkpoint 未闭合
```

- `completed`、`stopped` 为本轮结束态；`interrupted` 与 `stopped` 中仍有未完成 Task 的 Run 由 `resume` 接管，接管后回到 `running`。
- Run 状态与 Task 状态独立记录，不由一方推导另一方。
- 同一项目同时至多一个未完成 Run；`run` 建立新 Run 前先核对，存在未完成 Run 时报告并请先 `resume` 或显式停止。
- 每个 Task 的 checkpoint 在阶段完成、进入终态或中断前必须写盘并回读；checkpoint 未闭合（最后阶段结果未记录）即视为中断点，`resume` 按 [resume](resume.md) 重新核对实际进度。
- `report` 可对未完成 Run 生成阶段性摘要，须标注 Run 当前状态。

## 4. 队列与顺序

1. **串行**：`parallelism = 1`。同一 Run 同一时间只能有一个 Task 处于 `running`。
2. **入队条件**：Task 状态为 `ready`，且依赖全部满足（所有 `dependencies` 中的 Task 状态为 `completed`）。
3. **顺序**：依赖优先于优先级——先保证依赖任务在前；在依赖已满足的任务中按 `priority` 排序（`high` > `medium` > `low`），同优先级按 slug 字典序稳定排序，结果可复现。
4. 依赖指向 `blocked`、`failed` 或本轮 `skipped` 的任务时，本任务记 `blocked`（依赖未满足）。
5. 入队即 `ready → queued`，开始执行即 `queued → running`，出队结果（终态与时间）回写 `.cadra/queue/order.md`。
6. 不提前设计 DAG scheduler；依赖只影响排序与入队判定，不产生并行分支。

## 5. Flow Preset

Cadra 只声明阶段序列。首版 preset：

```yaml
full:
  - need
  - design
  - code
  - review
  - fix
  - validate

feature:
  - design
  - code
  - review
  - fix
  - validate

small-change:
  - code
  - review
  - fix
  - validate

bugfix:
  - fix
  - review
  - validate

review-only:
  - review
```

- preset 序列的第一项是 Cohestra 起始阶段；Task 的 `flow` 可写 preset 名，也可写显式阶段序列，显式序列同样只是候选序列。
- **Cadra 不拥有这些阶段的业务语义**，也不得仅依据 preset 机械执行全部阶段。实际是否执行下一阶段由 Cohestra 的机器状态决定：仅当 `next.allowed = true` 且 `next.stage` 在本 Task 的 flow 序列内，才调用该阶段。
- `next.stage` 不在 flow 序列内、`next.allowed = false`，或结构化状态显示流程闭合（无下一阶段）时，按第 6 节与 [run](run.md) 的规则处理，不自行发明阶段。
- 阶段名与 Cohestra 入口一致：need、design、code、review、fix、validate。

## 6. Cohestra 调用契约

Cadra 只依赖以下逻辑字段决定流程，字段由 Cohestra 随阶段交付提供，状态源位于 `cohestra_task` 目录内，具体载体（状态文件或交付物元数据）由 Cohestra 决定：

```yaml
task:
status:

stage_result:
  stage:
  status:

next:
  stage:
  allowed:
  reason:

blocked:
  value:
  reason:
```

- **Cadra 不解析 Cohestra 自然语言正文来决定流程。** 例如禁止解析 README 中“建议下一步进行 fix”这类句子来选阶段；正文只可作为报告中的短摘要素材。
- 读取规则：`stage_result` 决定刚完成阶段的结果；`next.stage` + `next.allowed` 决定下一阶段；`blocked.value = true` 时本 Task 记 `blocked` 并记录 `blocked.reason`。
- 结构化状态缺失、无法读取或字段不合法时，本 Task 记 `failed`（无法读取必要状态／协议输出不合法），不猜测、不用正文倒推。
- `run` 启动前先探测契约是否就绪；无法确认时报告现状并请用户决定继续或中止，不静默逐个判 fail。

**接口现状声明**：Cohestra 当前版本尚未提供上述机器可读状态。Cadra 只在此声明接口要求，不替另一个技能实现，也不修改 Cohestra 的协议、阶段定义或 handoff 语义。接口就绪前，`run` 的无人值守驱动无法闭环，按上一条的探测规则交用户决定；手工逐任务推进仍按各入口规则记录状态。

## 7. Unattended 执行规则

`run` 启动自动执行时向下游声明：

```text
execution_mode: unattended
```

无人值守期间：

- 不等待交互式问题；
- 不替用户做产品决策；
- 不扩大任务范围；
- 不获得新的隐含授权。

遇到上述任一情况（需要人类决定、缺权限、缺输入、依赖未满足、Cohestra 明确禁止继续）时，本 Task 记 `blocked`，记录原因后按默认规则继续下一个 Task。`resume` 的续跑段沿用原 Run 的 `execution_mode` 与各 Task 的 execution policy。

## 8. 落盘与共享写入

1. 每份文件只有一个写入者。Task 文件由负责该 Task 的执行者写；Run 文件、`queue/order.md` 与 `<run-id>-report.md` 由 Run 的执行者串行维护。所有权不明或冲突时保留各自记录并报告“待同步”，不覆盖未知更新。
2. 状态变化、checkpoint 更新必须即时写盘并回读；中断后这些文件是唯一恢复依据，不凭文件修改时间或文件编号推断进度。
3. 不把 Cohestra handoff 内容复制进 `.cadra`：候选、findings、验收证据以引用加短摘要记录，标注来源文件。
4. 不反复改写 `.cadra/README.md`；普通入口只写本入口的交付物。写入失败如实报告“未完成”及错误与待写内容，不宣称事务回滚。
5. 交付物写入顺序：先 Task/Run/报告文件，再队列清单，逐份回读。更新前重读，避免覆盖并发写入。
6. 回复交付物绝对路径、状态结论、必要待办、需人工介入事项，以及 `$cadra <下一入口>` 加准确输入（可直接执行）；推荐下一步不等于执行授权。

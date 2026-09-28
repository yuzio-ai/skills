# run

通过 $cadra run 调用；与 [公共流程](workflow.md) 一起执行。建立一次 Run，并按既定顺序无人值守串行推进队列内的 Task。

## 调用

```text
$cadra run
范围：<task-slug 列表，或“全部 ready”；可空取全部 ready>
补充：<本次限定条件，可空>
```

## 建立 Run

1. 核对不存在未完成 Run：存在时报告其 run-id 与状态，请先 [resume](resume.md) 或显式停止，不并行开新 Run。
2. 按 [公共流程](workflow.md) 第 4 节选定入队任务（`ready` 且依赖满足），生成 run-id `run-<YYYYMMDD>-<NN>`，按 [Run 骨架](../assets/run.md) 落盘 `.cadra/runs/<run-id>.md`，并把入队顺序写入 `.cadra/queue/order.md`。用户指定 slug 列表时只取其中满足入队条件的任务，其余逐条说明原因。
3. 入队即 `ready → queued`。范围为空且无可入队任务时，报告现状并停止，不空建 Run。
4. 启动前探测 Cohestra 结构化状态契约是否就绪（见 [公共流程](workflow.md) 第 6 节）：无法确认时报告现状并请用户决定继续或中止；用户选择继续的，按契约规则逐任务判定。

## 串行执行

1. Run 以 `execution_mode: unattended` 向下游声明，随后逐个执行：同一时间至多一个 Task 处于 `running`（`parallelism = 1`）。
2. 对每个 Task：`queued → running`，依其 flow 候选序列与 Cohestra 结构化状态推进：
   - 调用 `$cohestra <阶段>`，后附 `cohestra_task` 目录引用与 `execution_mode: unattended` 声明；一次只调用一个阶段。
   - 读取结构化 `stage_result`、`next`、`blocked` 字段（只读这些字段，不解析自然语言正文决定流程），更新 checkpoint：最后完成阶段、当前候选引用、findings 摘要、validation 结果。
   - 仅当 `next.allowed = true` 且 `next.stage` 在本 Task flow 序列内才执行下一阶段；`next.stage` 不在序列内、`next.allowed = false` 或流程闭合（无下一阶段）时按下方终态规则处理，不机械执行 preset 的全部阶段，也不自行发明阶段。
3. 终态判定：
   - 流程闭合且验收完成 → `running → completed`；
   - `blocked.value = true`，或 unattended 期间遇到需人类决定、缺权限、缺输入、依赖未满足 → `running → blocked`，记录原因（见 [公共流程](workflow.md) 第 7 节）；
   - Agent 执行异常、工具调用失败、无法读取必要状态、协议输出不合法、无法恢复执行状态 → `running → failed`，记录错误与恢复条件。
4. 状态变化即时落盘并回读 checkpoint，保证中断后可从 [resume](resume.md) 恢复。
5. 默认 `blocked` / `failed` 记录后继续下一个 Task；该 Task 配置 `stop_queue_on_failure: true` 时停止队列：Run 记 `stopped` 并写明停止原因，队列内未执行任务记为报告口径的 `skipped`（Task 状态保持 `queued`）。
6. 队列走完（全部 Task 到达终态）→ Run 记 `completed`。更新 `queue/order.md` 出队结果，逐份回读。

## 边界

- 不替用户做产品决策、不扩大任务范围、不获得新的隐含授权；不修改 `.cohestra` 内容，不复制 handoff 正文进 `.cadra`。
- 不做并行执行、DAG 调度、定时器、daemon 或 Agent 动态选择；执行者就是本会话的编排者，阶段工作由 Cohestra 协议承担。
- 未闭合的执行（会话中断、checkpoint 未写完）不宣告成功，如实报告中断点。

## 交付与停止

更新 `runs/<run-id>.md`、`queue/order.md` 与各 Task 状态；落盘规则见 [公共流程](workflow.md)。

推荐下一步 `report`；队列未走完或 Run 非 `completed` 时推荐 `resume`。派发：`$cadra report` 或 `$cadra resume`，后附 run-id 及本次补充。

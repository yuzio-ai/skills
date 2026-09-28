# resume

通过 $cadra resume 调用；与 [公共流程](workflow.md) 一起执行。从持久化状态恢复未完成 Run，接着串行推进。

## 调用

```text
$cadra resume
Run：<run-id；可空>
补充：<本次人工决定、补充输入或权限，可空>
```

run-id 缺省时取唯一的未完成 Run；存在多个候选时列出并请用户指定，不凭创建时间或“最新”猜测。

## 职责与工作

1. **从持久化状态恢复**：读取 Run 文件、其 checkpoint、`queue/order.md` 与相关 Task 文件，重建执行顺序与进度；不依赖聊天记录，不新建 Run。
2. **不重复已完成 Task**：`completed`、`blocked`、`failed` 的 Task 不重跑，按原记录计入本轮结果。
3. **不重复已完成 Cohestra 阶段**：以 checkpoint 的最后完成阶段为准，并回读 `cohestra_task` 目录的结构化状态核对实际进度；两者一致才从下一阶段继续，不凭文件修改时间或文件编号推断。
4. **重新核对 blocked / failed / running 状态**：
   - `running` 且 checkpoint 未闭合（中断点）：回读结构化状态判定该阶段实际是否完成——已完成则补记 checkpoint 后继续下一阶段，未完成或无法判定则按 [run](run.md) 的终态规则处理，不假定成功。
   - `blocked`：核对原因是否已解除（如本次补充带来了人工决定、输入或权限，或依赖任务已 `completed`）。已解除的回到 `queued`，排入队列尾部继续；未解除的保持 `blocked` 并跳过。
   - `failed`：默认不自动重试；用户显式要求重试时回 `queued` 并记录重试轮次与原因，不隐式循环重试。
5. 续跑沿用原 Run 的 `execution_mode: unattended` 与各 Task 的 execution policy：仍是无人值守语义，遇需人类决定的事项照旧记 `blocked` 并按默认规则继续。
6. 恢复后的串行执行、终态判定、`stop_queue_on_failure` 与落盘规则与 [run](run.md) 相同。
7. Run 已 `completed` 时无可恢复内容：报告结论并指向 [report](report.md)，不重跑。
8. 恢复过程中无法读取必要状态或记录互相矛盾时，如实报告缺口并停止推进，不猜测进度、不覆盖既有记录。

## 交付与停止

更新 `runs/<run-id>.md` 的 checkpoint 与 Run 状态、`queue/order.md` 与相关 Task 状态；落盘规则见 [公共流程](workflow.md)。

推荐下一步 `report`；派发：`$cadra report`，后附 run-id 及本次补充。

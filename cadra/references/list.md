# list

通过 $cadra list 调用；与 [公共流程](workflow.md) 一起执行。只读展示任务与 Run 状态，不写任何文件。

## 调用

```text
$cadra list
范围：<task-slug 列表或状态过滤，可空取全部>
```

## 职责与工作

1. 只读 `.cadra/tasks/`、`.cadra/queue/order.md` 与 `.cadra/runs/`，汇总展示；不修改状态、不补记、不清理。
2. 每个 Task 展示：slug/title、status（`draft` / `ready` / `queued` / `running` / `blocked` / `failed` / `completed`）、priority、dependencies（含各自当前状态）、flow，以及当前执行状态（所属 Run、最后完成阶段、checkpoint 摘要或未执行）。
3. 附 Run 一览：run-id、Run 状态（`running` / `completed` / `stopped` / `interrupted`）、队列进度（总数/终态数/当前 running 项）。
4. 状态以落盘文件为准；文件缺失或互相矛盾时指出缺口，不猜测补齐。
5. 展示按稳定顺序：Task 依 slug 字典序，Run 依 run-id 倒序，结果可复现。

## 交付与停止

本入口不落盘交付物，结论直接回复用户。需要推进时给出派发命令，如 `$cadra ready`（后附 task-slug）、`$cadra run`、`$cadra resume` 或 `$cadra report`（后附 run-id）。

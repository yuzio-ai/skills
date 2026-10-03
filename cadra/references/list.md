# list

通过 $cadra list 调用；与 [公共流程](workflow.md) 一起执行。只读展示任务、队列与 Run 状态，不写任何文件、不触发初始化。

## 调用

```text
$cadra list
范围：<task-slug 列表或状态过滤，可空取全部>
```

## 职责与工作

1. 本入口纯只读，不写任何文件，也不触发最小初始化：`.cadra` 缺失时只报告“未初始化”与目标绝对路径，提示可由写入口补齐。
2. 只读 `.cadra/tasks/`、`.cadra/queue/order.md` 与 `.cadra/runs/`，汇总展示；不修改状态、不补记、不清理。`queue/order.md` 不存在表示尚无队列记录，不算缺口。
3. 每个 Task 展示：slug/title、status（`draft` / `ready` / `queued` / `running` / `blocked` / `failed` / `completed`）、priority、dependencies（含各自当前状态）、flow、修订标记（带未消费修订记录时列 `rev-<N>` 与原终态），以及当前执行状态（所属 Run、最后完成阶段、checkpoint 摘要或未执行）。
4. 队列视图展示 `queue/order.md` 的位次信息：序号、入队时间、消费 run-id、入队操作编号与出队操作编号及结论（含“回 ready”类回退记录）；旧版清单按表块合并读取，缺失列写 unknown，不迁移、不重排。出队状态**按各表块自身的结论列**判定（旧表块看「出队结论与时间」，新表块看「出队操作编号与结论」），旧行不因缺 `deq-` 编号被判为未出队。补齐部分写入留下的未完成状态只如实展示，不在本入口补写。
5. 附 Run 一览：run-id、Run 状态（`running` / `completed` / `stopped` / `interrupted`）、队列进度（总数/终态数/当前 running 项）。
6. 当前 Task 状态以 Task 落盘文件为准，各 Run 的进度与结论取其自身 checkpoint/结果快照，不因 Task 进入新 Run 而改写旧 Run 展示；任务文件缺失或记录互相矛盾时指出缺口，不猜测补齐。
7. 展示按稳定顺序：Task 依 slug 字典序，队列依序号，Run 依 run-id 倒序，结果可复现。

## 交付与停止

本入口不落盘交付物，结论直接回复用户。需要推进时给出派发命令，如 `$cadra ready`（后附 task-slug）、`$cadra run`、`$cadra resume` 或 `$cadra report`（后附 run-id）。

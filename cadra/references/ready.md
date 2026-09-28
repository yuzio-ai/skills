# ready

通过 $cadra ready 调用；与 [公共流程](workflow.md) 一起执行。执行 Ready Gate，把 Task 从 `draft` 放行到 `ready`。

## 调用

```text
$cadra ready
任务：<task-slug>
补充：<本次澄清或补充材料，可空>
```

## 职责与工作

Ready Gate 八条逐条检查，全部满足才放行：

| # | 检查项 | 判定口径 |
|---|---|---|
| 1 | 目标明确 | requirement 的目标可判定，不是待探索的方向 |
| 2 | 范围明确 | 做什么、不做什么清楚 |
| 3 | 验收条件明确 | 有可判定的验收条件，出现什么现象算完成说得清 |
| 4 | 无必须由人类决定的问题 | 无待用户裁决的产品决策、取舍或授权问题 |
| 5 | 必要输入完整 | 执行所需的输入、参考与环境前提齐备 |
| 6 | 依赖满足 | `dependencies` 中所有 Task 状态为 `completed` |
| 7 | Cohestra 起始阶段明确 | flow 序列首项是 need/design/code/review/fix/validate 之一 |
| 8 | 执行流程明确 | flow 已定义：preset 名或显式阶段序列，且规则一致 |

1. 通过：`status: draft → ready`，在任务文件记录 gate 结果、逐条结论与放行时间，随后停在 `ready`，不入队、不建 Run。
2. 不通过：保持 `draft`，逐条列出未满足项、缺口事实与补足建议，交用户补充或经 `add` 修改；不降级放行，不把假设当已决。
3. 检查只读取本 Task 文件、其依赖任务的状态和必要输入；不读其他任务正文、不动 `.cohestra`。
4. 依赖检查以任务文件落盘状态为准（见 [公共流程](workflow.md) 第 2 节状态机），不凭口头或 Run 记录推断。
5. 同一 Task 可重复执行 Ready Gate：已 `ready` 的任务重复调用时按现状复核并报告，不重复改写放行记录；已进入 `queued` 及以后状态的任务不适用本入口，状态回退按 [add](add.md) 的编辑规则由用户决定。

## 交付与停止

更新 `tasks/<task-slug>.md` 的状态与 gate 记录；落盘规则见 [公共流程](workflow.md)。

推荐下一步 `run`（或继续准备其他任务）；派发：`$cadra run`，后附范围或“全部 ready”及本次补充。

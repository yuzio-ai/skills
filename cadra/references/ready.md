# ready

通过 $cadra ready 调用；与 [公共流程](workflow.md) 一起执行。执行 Ready Gate，把 Task 从 `draft` 放行到 `ready`。

## 调用

```text
$cadra ready
任务：<task-slug>
补充：<本次澄清或补充材料，可空>
```

## 职责与工作

按 [公共流程](workflow.md) 第 2.1 节的 Ready Gate 八条逐条检查，全部满足才放行；本入口不重复定义 Gate。

1. 通过：`status: draft → ready`，在任务文件记录 gate 结果、逐条结论与放行时间，随后停在 `ready`，不入队、不建 Run。
2. 不通过：draft 保持 draft；ready 复核失败回 draft。追加本次逐条结论、缺口、时间与补足建议，保留旧放行事实；不降级放行，不把假设当已决。
3. 检查只读取本 Task 文件、其依赖任务的状态和必要输入；不读其他任务正文、不动 `.cohestra`。
4. 依赖检查以任务文件落盘状态为准（见 [公共流程](workflow.md) 第 2 节状态机），不凭口头或 Run 记录推断。
5. ready 重复检查通过时保留原放行记录；复核失败按上述第 2 条追加记录。queued/running/completed/blocked/failed 不适用本入口：未完成 Run 先 resume 收尾，定义编辑按 add，执行恢复按 run 的显式恢复规则，不直接改成 ready。终态任务经 add 修订回 `draft` 后仍由本入口放行，其重新执行按 [公共流程](workflow.md) 第 6.3 节的修订重启准入判定，不在本入口决定首个动作。

## 交付与停止

更新 `tasks/<task-slug>.md` 的状态与 gate 记录；落盘规则见 [公共流程](workflow.md)。

推荐下一步 `run`（或继续准备其他任务）；派发：`$cadra run`，后附范围或“全部 ready”及本次补充。

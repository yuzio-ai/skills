# report

通过 $cadra report 调用；与 [公共流程](workflow.md) 一起执行。生成本轮执行摘要，落盘为 `.cadra/runs/<run-id>-report-<轮次>.md`。

## 调用

```text
$cadra report
Run：<run-id；可空>
补充：<本次关注点，可空>
```

run-id 缺省时取最近一次或未完成的 Run；多个候选时列出并请用户指定。Run 未结束时生成阶段性摘要，并在文首标注 Run 当前状态（running / stopped / interrupted）。

## 职责与工作

1. 按 Run 文件、checkpoint、`queue/order.md` 与 Task 文件汇总，不重跑任务、不改写 Task 状态；只写报告文件，并在 Run 文件中登记报告链接。
2. 汇总四类计数与清单：`completed`、`blocked`、`failed`、`skipped`（skipped 指队列被停止后未执行的入队任务，Task 状态仍为 `queued`）。
3. 每个 Task 至少报告七项：
   - 最终状态；
   - 最后完成阶段；
   - 当前候选（引用 `cohestra_task` 中的候选记录，不复制正文）；
   - findings 摘要（短摘要加来源文件引用）；
   - validation 结果；
   - 是否需要人工介入（是/否，附原因）；
   - 下一步（动作、前提、负责人或待指派）。
4. findings 摘要与 validation 结果来自 Cohestra 结构化状态与短摘要素材；不解析自然语言正文决定流程，也不把 handoff 内容搬运进 `.cadra`。
5. 结构化状态缺失或不合法的 Task 按 [公共流程](workflow.md) 第 6 节如实记为 `failed` 原因之一，报告中注明契约缺口，不美化结论。
6. 人工介入清单单独成段：需要用户决定、补充授权、补输入或处理 blocked/failed 的事项集中列出。
7. Run 未完成时给出恢复建议（对应 `$cadra resume`）；已完成时给出收尾建议（新任务经 `$cadra add`）。

## 交付与停止

新增 `runs/<run-id>-report-<轮次>.md` 并同步 Run 文件中的报告链接（轮次两位起、不截断）；落盘规则见 [公共流程](workflow.md)。同一 Run 可多次报告，每次新增一轮文件并引用旧版，不覆盖历史。

推荐下一步 `resume`（Run 未完成时）或结束本轮；派发：`$cadra resume`，后附 run-id 及本次补充。

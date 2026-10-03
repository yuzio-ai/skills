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

1. 以所选 Run 的逐 Task 结果快照与调用记录汇总，按 run-id + slug 核对队列行；Task/README 当前状态不作为旧 Run 的结果。不重跑、不改 Task 或结束快照；只写报告并在该 Run 登记报告链接。新 Run 的成功不覆盖旧 Run 的失败；旧协议没有快照时只用可核实的历史记录，缺失项写 unknown 并注明缺口，不用当前状态补造历史。
2. 汇总四类计数与清单：`completed`、`blocked`、`failed`、`skipped`（skipped 指本轮未执行的入队任务，含队列停止与 Run 收尾两种来源；这些任务已出队回 `ready`，注明原因）。
3. 每个 Task 至少报告七项：
   - 最终状态（修订重启／修订收尾项附 `rev-<N>` 与原终态来源）；
   - 最后完成阶段；
   - 本 Run 的候选（引用结果快照固定的候选来源，不复制正文）；
   - findings 摘要（短摘要加来源文件引用）；
   - validation 结果；
   - 是否需要人工介入（是/否，附原因）；
   - 下一步（动作、前提、负责人或待指派）。
4. findings 与 validation 来自该 Run 保存的结构化摘要及固定来源；保留已知 passed/failed/pending/blocked，无结论才 unknown，flow 截断不抹去实际验收结论。必要后续超出 flow 时说明缺失阶段；正常边界收尾说明截断范围；恢复项注明来源 Run、调用方式与解除依据；修订重启与修订收尾项同时标注 `rev-<N>`、原终态与本次定义；收尾注明未调用阶段、候选与验收为沿用来源，旧 Run 的结论只作历史对比、不计入本次结果。当前状态如需展示，单列为其他轮次的补充，不混入本 Run 计数。
5. 本 Run 因结构化状态缺失或不合法而失败时如实说明该次 failed 原因；后来的索引损坏或修复不倒改原 Run 的成功/失败记录。报告缺历史材料时标注 unknown，不改写 Task 状态。
6. 人工介入清单单独成段：需要用户决定、补充授权、补输入或处理 blocked/failed 的事项集中列出，并包含 unattended 下“verify 跳过 + 理由”、执行模式核对失败、重试上限耗尽、整改轮上限耗尽、调用预算耗尽（[公共流程](workflow.md) 第 6、7 节），以及仍未补齐的入队／出队部分写入（第 4 节第 7–9 条）。
7. 未完成 Run 建议 resume；已结束且有 blocked/failed 时给出 run 的显式范围与恢复列表，并列恢复前提，不推荐重开旧 Run。新需求或定义有变时经 add 修订并由 ready 重新放行（修订重启，不写进恢复列表）；报告推荐不产生新授权。

## 交付与停止

新增 `runs/<run-id>-report-<轮次>.md` 并同步 Run 文件中的报告链接。**轮次**是同一 Run 的第几份报告，两位起、不截断，与 Cohestra 的阶段轮次无关；落盘规则见 [公共流程](workflow.md)。同一 Run 可多次报告，每次新增一轮文件并引用旧版，不覆盖历史。

推荐下一步 `resume`（Run 未完成时）或结束本轮；派发：`$cadra resume`，后附 run-id 及本次补充。

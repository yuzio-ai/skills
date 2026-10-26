# 定义修订与重启

## 修订分代

定义编辑及累计变更仅由 [任务定义的修订分代](task-definition.md#修订分代) 规定。add 读该节，本页只在 ready 核对修订首动作或 run/append/resume/recovery 核对重启准入时读取。

入队前按 [公共流程](workflow.md) 定位执行依据，累计其后各修订及当前修订的 changed_fields；首调用前 blocked/failed 与 skipped 均不能截断累计。链上尚未解除的受阻/失败原因仍须通过恢复准入，不能因跳过无调用条目而绕过。没有执行依据时按公共流程核对首次启动或既有交付。

## 重启准入

修订由 ready 重新 Gate 后进入 run 的普通范围，不写入 blocked/failed 恢复列表。旧验收不能被当作变更后 requirement 的验收。准入缺口保持当前定义与 preparation，不入队。

| 自最后执行依据起累计变更 | 原执行结论 | 首个动作 |
|---|---|---|
| requirement / 规范化 flow | completed | 新 flow start 一次 |
| requirement / 规范化 flow | blocked / failed | 先按 [恢复准入](recovery.md) 核实原因解除与交付，再从新 start 一次 |
| 仅 dependencies / execution_policy | blocked / failed | 按恢复准入选择原待调用、合法 next 或核对收尾 |
| 仅 dependencies / execution_policy | completed | 核实旧契约与来源，并通过 [完成前置核对与终态映射](contract.md#完成前置核对) 后才可修订收尾；否则报告受阻。收尾不调用阶段，明确候选与验收为沿用 |

仅已有 Cohestra 交付、尚无 Cadra 执行依据时：绑定确认与合法契约必需；requirement/flow 已变化时按该契约的实际完成/受阻情况套用上述准入，缺少恢复所需调用证据时停止，不补造历史。

调用向 Cohestra 传当前 requirement、修订依据、解除证据与上游材料，阶段轮次继续递增。首个调用意图或无需调用的结果快照写入 Run 即消费重启授权；尚未执行的 skipped 不消费。中断后核对同一调用，不重复给予重启起点。仅策略变更的沿用交付按其原模式核对，不用本 Run unattended 反判原本合法的 attended 结果。

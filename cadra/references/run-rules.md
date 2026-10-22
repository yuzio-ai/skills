# Run 与持久化

## Run 状态

running → completed / stopped / interrupted。completed 表示本轮所有项已结束，不表示所有任务成功；stopped 表示用户停止或执行策略停止；interrupted 表示中断、待恢复。

**未完成 Run**：状态 running/interrupted，或 stopped 但仍有 queued/running 条目。completed 却有未结束条目、终态条目缺结果、同一 Run 多个 running 或来源链矛盾，均为记录异常，不放行新 Run。closed 的 completed 或 stopped 不重开；resume 只报告其结束事实。

## 建立与执行

通过目标、协议、Gate、来源链与首个动作核对后，按 [Run 模板](../assets/run.md) 一次保存完整任务数组：每个 slug 唯一，固定顺序，definition 快照及 revision、previous_run、首个动作与授权依据齐全，初态 queued。这份文件回读成功即完成入队；不回写 Task，没有额外操作编号。

每项状态为 queued → running → completed/blocked/failed；尚未调用且无结果的 queued 项可在停止收尾时记 skipped。每项结果与其终态在同一次 Run 文件更新中写入。归属、顺序、执行事实均以 Run 为准；不保留另一张逐任务状态摘要表。

- 调用前：先确定需要哪个阶段，检查 [预算](contract.md#调用预算)，追加递增 call id、调用原因、拟调用阶段、调用前契约、execution_mode 和预算消费；记录 `dispatch: prepared`、`closed: false`。需要一次性恢复/修订授权时在同一更新中记已消费。
- 回读后发起该次 Cohestra 调用；在可记录时将 dispatch 记 dispatched。prepared/dispatched 均不是已交付证明；工具调用与文件更新不具备跨系统原子性。
- 调用后：核对索引同步、阶段/轮次和模式，再把实际契约与来源写进同一调用记录并闭合，更新 checkpoint。交付不能确认时按 [resume](resume.md) 处理，不盲目再调一次。
- 预算在调用意图落盘时预占。中断后仍未能确认是否发起时保留消费，不返还；确认未发起且可安全继续时沿用同一 call id 与预算。不能以新 id 绕过未闭合调用。
- 每项结束保存固定结果快照：状态、最后交付、候选、findings、acceptance、下一步、人工介入、来源与时间。所有项结束后更新 Run 状态；中间中断由 resume 补 Run 收尾，不重复阶段。

## 停止与恢复

默认 blocked/failed 后继续下一项。当前项 `stop_queue_on_failure=true` 时停止，未执行 queued 项记 skipped，展示为 ready，且下次重新核对原首个动作的准入。

用户明确停止：先核对 running 项。可确认终态时保留实际结果；仍可继续但要求停止时记 blocked（用户停止，保留 next）；无法确认本次结果时记 failed 并保留未闭合调用证据。queued 项记 skipped。全部结果落盘后 Run 记 stopped；未完成前不能新建 Run。仅收尾不要求 Cohestra 可用或目标为 Git，但来源、状态必须可核实且可安全写入。

恢复依据只在当前 Run；后续新 Run 的 previous_run 指向该 slug 的链尾，旧 Run 不变。跨 Run 的恢复和修订分别见 [恢复规则](recovery.md)、[修订规则](revision-rules.md)。单文件持久化与冲突处理遵循 [公共流程](workflow.md#共同写入)。

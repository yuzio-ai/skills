# append

向正在运行的 Run 尾部加入已准备任务。读 [公共流程](workflow.md)、[Task/Gate](task-rules.md)、[Flow](flow.md)、[Run 规则](run-rules.md)、[契约](contract.md)、[预检](preflight.md) 与 [执行归属](executor.md)。含旧记录时读 [版本边界](compatibility.md)。

```text
$cadra append
Run：<run-id；省略时选择唯一 running Run>
任务：<明确指定的 slug 列表>
```

只接受协议 0.10 的 running Run，不要求成为其执行 owner，也不因 owner 活跃而拒绝受限追加。interrupted 先按 resume 恢复；completed/stopped 不重开。缺失、多个未完成 Run 或状态矛盾时停止，不猜最新批次，不初始化替代。

1. 明确目标 Run 和非空任务集合。重复输入或 Run 中已有 slug 整批拒绝；不重开旧终态条目。append 不提供失败恢复列表，需恢复或业务修订先走原有 add/ready/run 准入。
2. 每项必须是当前可入队且与目标 Run 同协议的 ready 定义，并通过与 run 相同的协议、Gate、来源链、授权、输入、Cohestra 绑定及首个动作核对。混合协议整批拒绝，不自动迁移。依赖当前定义必须已 completed，不接受仅排在队列前面的未完成依赖。
3. 对本批次执行任务预检，并核实当前项目前提仍成立；保存可核查证据。任何任务不合格或全局检查失败，整批不写入，逐项报告缺口；不写 Task、不派发阶段。
4. 按 priority 高到低、同级 slug 字典序排列本批次，准备完整定义快照、revision、previous_run、start_action 和初始 queued 条目；agents/calls 为空、预算为零、checkpoint 与 result 为空。已有队列顺序不变。
5. 写入前重读 Task、授权与关键输入，有变化则重检。经 guard append 在同一原子写入中追加 tasks 后缀、仅对应新增 slug 的 task 预检记录和一条 append_history；其余字段及正文逐字保留。项目预检复核依据写入本批新增任务证据，不借 append 修改原项目记录。
6. guard 回读成功才报告已入队。摘要冲突时重读最新 Run 并重新核对批次准入，最多重试三次；Run 已结束、出现重复 slug 或任何新冲突则拒绝，不插队、不部分成功。

append_history 每条为 `{at: <带时区时间>, source: <本次明确追加请求及执行者来源>, tasks: [{slug, revision}, ...]}`；tasks 顺序与本次新增后缀一致。审计记录不冒充 executor 的执行进展。追加与收尾在同一锁下裁决：追加先成功则执行器需处理新条目；收尾先成功则追加拒绝。

追加不接管、不唤醒、不向执行聊天发送消息。执行器按 Run 规则重读最新队列。交付 Run 路径、新增 slug、追加后总项数与状态；未写入时明确整批未追加。

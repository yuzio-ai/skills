# Flow 执行：起点与允许范围

先读 [Flow 配置](flow-config.md)；本页只规定阶段推进，add 不读取。ready 在核对首动作时读取，run/append 及需要阶段判定的 resume 读取。

首次启动及改变 requirement/flow 的修订重启从 start 调用一次；其他入口的起点见 [恢复](recovery.md) 与 [修订](revision-rules.md)。后续仅按合法 `next.allowed`、`next.stage` 与 allowed 决定动作，不机械遍历列表。允许重复进入同一阶段，包括复审与补证，次数由 [预算](contract.md#调用预算) 约束。

Cadra 向 Cohestra 明确传递本任务独立评审安排：实施后必须 review，fix 后必须复审；无必做整改且覆盖齐备后才进入 validate。显式列表不能免除这些要求，缺必要 review 范围时受阻。review-only 不自动修复。

末项不声明终点。正常 next 超出 allowed 时按 [终态映射](contract.md#终态映射) 收尾；必做后续超出范围则 blocked。next 指向 need/design 一律 blocked 并交回人工，不能按正常范围边界收尾。是否要求 validate 结论以 allowed 是否含 validate 判定。Cohestra 单独调用的阶段范围与授权规则保持不变。

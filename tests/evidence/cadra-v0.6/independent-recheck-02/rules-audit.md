# Cadra 规则独立复核

范围：只读 cadra/SKILL.md、cadra/references/*.md 和 cadra/assets。未读 tests、evidence、此前结论、测试模型或历史版本；不判断发现是否由本次修复引入。

## P2：running 且首次调用意图尚未落盘的恢复没有分支

- cadra/references/run-rules.md:13 允许 queued → running → 终态；仅规定终态与结果同次写入。
- cadra/references/run-rules.md:15–18 规定调用意图、预算和特定授权同写，但没有要求 queued → running 与首次调用意图同写。
- cadra/references/workflow.md:53 的原子写入是单次文件更新原子，不把上述两次更新合并。
- cadra/references/resume.md:16–21 只覆盖 queued、running+未闭合调用、running+已闭合调用；未覆盖 running+calls=[]。

反例：新 Run 的任务拥有合法 start_action=首次启动 need，budget.calls=0，authorization_consumed=false，checkpoint.pending_call=null。执行器先把条目从 queued 写为 running 并回读，在首次调用意图写入前中断。记录符合已列明约束，且没有调用意图足以确认从未进入允许的派发路径。resume 不能按 queued 处理，也不存在可恢复的调用或可消费的 next。通用“不猜测”只能停止，失去本应可安全恢复的首个动作。

建议：规定 queued→running 必须与首调用意图/无需调用结果原子写入；或为 running+calls=[]+未消费 start_action 增加准入复核与继续分支。此为文本恢复覆盖缺口，未执行运行时复现。

## P2：flow 的列表排列例外错误涵盖 start 变化

- cadra/references/flow.md:3 明确列表首项决定 start。
- cadra/references/flow.md:13 又无条件写“只有列表排列或重复写法变化不使 Gate 失效”。
- cadra/references/task-rules.md:10 及 cadra/references/revision-rules.md:17–18 则要求规范化 flow 变化失效 Gate，并从新 start 重启。

反例：已执行任务将 [code, review] 改成 [review, code]。这是列表排列变化，但 start 由 code 变成 review。按 flow:13 可保留 Gate/修订；按 start 语义与修订规则必须重新 Gate、分代及重启。两者不能同时成立。

建议：把例外限定为“start 不变，且 allowed 相同，仅 allowed 中其余项目顺序/重复写法改变”。

## authorization_consumed 的独立判读

普通首次与正常 next 调用不要求 true。run-rules.md:15 只要求需要一次性恢复/修订授权时同写已消费；workflow.md:34 排除的是 calls 为空且 authorization_consumed=false，不能扩成所有 calls 非空都必须 true。

无需调用收尾的标志仍有文字空白：workflow.md:34 一方面把“已核实契约并保存无需调用收尾结果”列为执行依据，另一方面排除 calls=[] 且 flag=false；revision-rules.md:24 明确修订收尾消费，但普通已有交付核对收尾与恢复核对收尾没有同等明确的置 true 规定（recovery.md:12 只写首次调用意图消费）。可要求统一定义 flag 为“首个执行动作已消费”，或明确无需调用 result 自身构成依据、不依赖该 flag。这里列为协议澄清项，未单独确认错误行为。

## 其他已核对场景

- 首调用前 blocked/failed 与 skipped 不截断从最近执行依据起的变更累计。
- 首调用前受阻不能借新 revision 或 skipped 绕过原因解除核对。
- prepared/dispatched 不证明交付；派发不明不返还预算、不创建新 id。
- resume 沿用同一预算；已结束 Run 的显式恢复有新预算。
- 终态优先于预算上限，允许第 16 次调用刚完成的结果收尾。
- requirement/flow 改回仍按累计变更重启；只改变策略的已完成交付沿用原模式核对。

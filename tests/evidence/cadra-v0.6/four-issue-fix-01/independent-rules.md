# Cadra 当前规则独立复核

结论：本次未确认需要阻止合并的规则冲突。执行依据与授权消费已分离；首次调用意图前中断有独立分支；Flow 的起点与允许集合均参与修订判定；恢复预算明确按 Run 隔离。以下是规则静态推演，不代表执行器运行验证。

范围：仅阅读 `cadra/SKILL.md`、`cadra/references/`、`cadra/assets/`；按需核对 `cohestra/references/workflow.md` 的 0.8 契约。未读 tests、历史报告，未联网、修改源文件或执行工程阶段。

## 场景判读

| 场景 | 按当前规则应有结果 | 依据 |
|---|---|---|
| 普通调用已落盘，authorization_consumed=false | 该条目仍是执行依据。该字段不负责表示普通执行是否发生。 | workflow.md:34；run-rules.md:15 |
| 普通接续只核对已有完整交付后 completed，无调用，authorization_consumed=false | 有合法契约及固定收尾结果，仍是执行依据；预算为零。 | workflow.md:34；contract.md:42、91；assets/run.md:58 |
| 没有 calls、没有有效核对收尾，却 authorization_consumed=true | 记录矛盾，停止；不能跳过该记录推定没有执行。 | workflow.md:34 |
| prepared 意图已保存，派发不明，只有旧契约 | 意图仍是执行依据。停止该项并记 failed；保留未闭合 call 与预算，不盲目重试。 | workflow.md:34；resume.md:18-21；run-rules.md:18 |
| prepared 意图已保存，有明确未派发证据且无交付 | 同 Run resume 继续同一 call id，沿用预算及授权消费。 | resume.md:20；contract.md:93 |
| running、calls=[]、预算零、未消费、无 result/checkpoint 交付，start_action 完整，证实未派发 | 重核原首个动作。可调用或核对收尾；核对本身不消费预算或授权。 | resume.md:17 |
| 上述 running 无调用，但预算非零、授权已消费或派发不明 | 不执行“清零后重跑”；停止并记录失败。准入失败但记录可信则记录受阻。 | resume.md:17 |
| r1 已完成；r2 改 requirement，首调用前 blocked；r3 只改 execution_policy | r2 不构成执行依据，累计变更仍含 requirement；核对受阻原因解除后从当前 flow start 重启，不能沿用 r1 完成结果。 | revision-rules.md:7-9、17-20；recovery.md:7-8 |
| r1 普通调用已完成且授权字段 false；r2 只改 dependencies | r1 是有效执行依据；核实旧契约与来源后修订收尾，不调用阶段，沿用候选/验收。 | workflow.md:34；revision-rules.md:20、24 |
| small-change 改为 [code, validate, review, fix] 或加入重复项 | start 与 allowed 不变；语义等价，不使 Gate 失效或分代。 | flow.md:3、13；task-rules.md:11 |
| [review, fix] 改为 [fix, review] | allowed 相同但 start 改变；Gate 失效，已入 Run 的定义分代，按新起点重启。 | flow.md:13；task-rules.md:10 |
| 起点不变但增减 allowed，或 requirement/flow 改后又改回 | 仍属于需重新 Gate 的修订；已累计的 requirement/flow 变更不因改回而消失。 | flow.md:13；revision-rules.md:7 |
| 同 Run 在第 16 次交付后完成，然后 resume 补记 | 补同一调用结果并完成；不额外扣费，不因恰好达限改判 failed。 | contract.md:59、89-93；resume.md:19、22 |
| 已结束 Run 因预算耗尽失败，明确选择恢复且新准入通过 | 新 Run 有自身预算；只给一个恢复起点，后续按新契约消费预算。同 Run resume 不刷新额度。 | recovery.md:12；contract.md:93 |
| 旧 failed 阶段被授权恢复重试 | 该调用属于“失败结果后追加该阶段调用”，计总调用及对应阶段 retry；同一 Run 后续仍受逐阶段 2 次上限。 | recovery.md:9、12；contract.md:87-93 |
| status=completed 但 next.allowed=true、next.stage=null/未知，或布尔写为字符串 | 类型/枚举非法优先 failed，不能凭 completed 放行；若建 Run 前已发现，停止整个 run。 | contract.md:41、44、53、65；run.md:16 |
| acceptance 缺省，其他契约合法 | 可选字段缺失不是契约损坏；completed 且 allowed 含 validate 则 blocked，不含则 completed 并保留 unknown/人工介入。 | contract.md:23、71-72、79；Cohestra workflow.md:130-131 |

表中未加前缀的路径均相对于 `cadra/references/`；`assets/` 路径相对于 `cadra/`。

## 非阻塞建议

1. **明确同 call id 规则只约束同 Run。** `run-rules.md:18` 的“沿用同一 call id 与预算”未在句内标出范围；`recovery.md:8、12` 与 `contract.md:93` 则允许已结束 Run 在核实未派发后进入新 Run，并使用新 Run 预算。结合上下文可判定二者不矛盾，但补“同一 Run 内”能减少读者把旧 call id 跨 Run 复用的风险。
2. **对恢复首个失败重试加一个计费例子。** `contract.md:87` 的一般条件已覆盖恢复重试，未发现免计额度漏洞；`recovery.md:9` 的“恢复重试该阶段一次”可能被误读为预算外的额外次数。可明确该次仍计入新 Run 对应阶段 retry 与总调用。

没有把上述措辞改进列为确切缺陷，也没有从缺测试推断行为故障。

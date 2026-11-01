# Run 收尾一致性审查（协议 0.12）

run/resume 在普通队列处理完、小组均已 close 后读取本页；list/report 只读取记录和展示口径。收尾属于 run/resume 已授权的内部准备与派发，不是新入口或 Cohestra 第七阶段。主 agent 不亲自执行工程审查或整改。

## 范围与权限

- 检查本 Run 实际归属的增量、此前收尾整改及必要依赖：行为与文档是否同步；被替代的代码、入口、配置、测试和文档是否仍有用途；多个任务合并后是否存在冲突或重复实现。依据各任务的 before、精确差异和固定候选确定归属，不以共享工作区总 diff 代替。
- 历史问题、用户或其他任务修改不能自动纳入整改。可选整理单列位置、影响和建议；确定且范围内的缺陷进入既有 findings。缺少输入或需要新产品／授权决定时受阻，不猜测删除。
- 收尾任务的写范围仅继承本 Run 普通任务已获准整改的范围。使用 `closeout.writable` 汇总 flow 允许 fix 的普通任务 ready_scope 与已实际 grant 的 files/agent 运行时扩展；未授予、取消或仅待核查的申请不产生写权限，按规范路径去重；exclusive 只表示独占调度，不表示整个仓库均可修改。目录租约仍须按有效 requirement 限定实际整改。
- 有明确继承文件／目录时使用 `flow: review`；无此范围时使用 `[review]`。纯 `[review]` Run 只读收尾；混合 Run 不取得只读任务的整改权限。范围外问题保留 finding 和条件，不扩大范围。首次预计范围不完整时，应在普通任务阶段按既有资源与授权规则补齐，不在收尾凭空扩权。
- reviewer 必须与所有被审变更的实现／整改作者分离，包括历史候选的作者；不能仅凭角色名称或新建会话宣称独立。默认创建专用 reviewer；需要 fix 或 validate 时再创建 worker，均遵循原角色、快照、资源和预算规则。

## 准备、登记与执行

1. 重读 Run 并确认 owner／代次，状态 running、没有停止策略，所有现有条目已终态、小组均已 close。旧任务即使失败也保留原结果；收尾不自动重试失败功能或改写其验收。
2. 取 `N=len(closeout)+1`，固定 slug 为 `closeout-<run-id>-<N，两位起>`。先核对同名 Task／handoff：不存在才新建；准备中断留下的同源记录仅在 origin、revision、requirement、Gate 和候选依据完全可核实时复用。不覆盖同名异源资料，不因重试生成新 slug。
3. 以普通 Task 格式准备定义与 Ready Gate，增加 `origin: {run: <来源 run-id>, round: N}`。origin 是不可变的生成来源，不是执行状态或当前归属指针。revision=1、previous_run=null、cohestra_task 使用该 slug 的标准绑定；`execution_policy: {stop_queue_on_failure: true}`。本入口可准备新的内部任务，不得编辑任何已有 Run 条目或其 Task。
4. requirement 明确审查范围、各任务差异／候选、有效授权、继承写范围、文档与清理 AC、可选问题处理和最终候选核对。实际通过八项 Gate 和项目／任务预检后，原子保存 Task 并回读。缺口不能由脚本生成的 passed 代替；无法完成时保留 Run 恢复点，不报告收尾通过。
5. 固定整体候选，包含所有已覆盖路径和相关依赖；删除／不存在路径显式保存 null。需保留此前 ready_scope.inputs、明确修改文件、运行时请求范围／候选、grant before、group before 及各稳定候选中的路径；未获授予的请求路径仅作只读核查输入，不扩大整改写范围；目录范围按实际差异和依赖展开，不能只记录目录名。最后组输入必须仍匹配。
6. 调用包内 [closeout.py](../scripts/closeout.py) 的 `run_guard.closeout.prepare(data, definition, candidate, when, evidence, run_guard.scheduler, run_guard.normalize_flow)` 构造提案；它只接受调用者已核实的 Gate／预检证据，不执行检查。通过 guard **closeout** 操作，在相同文件锁、owner、代次及摘要比较下，原子追加新 Task、task 预检、append_history 和一条 closeout 引用；其余字段和正文不变。普通 append 无权登记生成任务。
7. 回读后进入现有分组流程。收尾范围为 exclusive，独占一个小组；实际首个 call 必须为 review；后续只消费已核实 next，候选刷新须引用真实 invalidate 依据。必要时 fix → 独立 review → validate，无问题也按 flow 到达合法终点。资源请求仍使用协议 0.12，运行时不能扩大继承写范围。16 次调用／3 次整改／每阶段 2 次失败重试照常计费，不另设免费循环。
8. 各 calls.result 明确保存 `{contract: <核实的完整 0.8 契约>, handoff: <准确交付引用>, index_sync: true}`，最后一项为实际回读核验结果，不得代填。最终 result.candidate 使用调度候选的 `{snapshot,sha256,inputs}`，与本收尾组 close 的 candidate 完全一致。review／最终验收必须针对同一 snapshot；fix 后必须有独立复审。完整 flow 需 validate passed；仅 `[review]` 保留无运行验收的边界，仍拒绝已知 acceptance=failed，不把失败验收标为通过。不能只写 PASS 或零 findings。

生成任务只能在 origin.run 内自动调度。run 的普通选择（包括全部 ready）、普通 append、恢复列表均排除生成任务；显式选中时说明应回来源 Run 的 resume，已经结束则不重开。失败后的新工作须由用户显式准备普通 Task，引用旧 finding 和停止条件，不自动换 slug 绕过预算。

## 记录与关闭门槛

Run 创建时必须有 `closeout: []`，该数组只经 owner closeout 操作追加；其他更新、append、takeover、报告登记均不能改写历史。

```json
{"slug":"closeout-run-20261101-01-01","covered":[{"slug":"feature-a","revision":1}],"candidate":{"snapshot":"<不可变材料引用>","sha256":"<真实清单摘要>","inputs":{"Sources/A.swift":"<SHA-256>","Sources/Old.swift":null}},"at":"<带时区时间>","generation":1,"event_count":12}
```

- covered 为该任务前面全部条目的 slug／revision，包含先前收尾任务；event_count 固定准备时的 scheduler.events 长度，指向已关闭的组边界。执行、预算、findings 和结果仅在普通 tasks/calls/result 中，不在这里另建控制状态。
- completed Run 的最后一项必须是当前有效且通过的收尾任务，最后一个小组必须仅包含该任务且已 close。原业务任务可有 blocked/failed；收尾通过不代表这些任务成功。
- 写入器核对覆盖、候选、独立角色与必要复审／验收，拒绝缺失、过期、无复审或候选不一致的结果；关闭转换还重核最终 inputs 对应的当前字节／不存在标记。脚本检查不证明授权、清单归属或 handoff 内容真实，主 agent 仍须核实。
- 合法 append 在收尾期间仍可增加普通任务后缀。先完成当前独占小组，再执行新增任务，最后创建覆盖扩展队列的新收尾任务。旧结果标为 outdated，不作最终放行依据；没有新增普通任务不能重复创建收尾任务。
- 新一轮收尾要求上一轮确已通过。blocked/failed／预算耗尽按停止策略处理，不因追加或重建收尾重置预算；所有在途角色与工具仍按既有停止规则核实。
- append、closeout 登记与关闭共享文件锁：追加先成功则旧关闭提案摘要失效；关闭先成功则追加拒绝。冲突后重新读取和核对，不覆盖较新队列。

## 中断、停止与报告

- 准备中断时复核同源 Task 后继续登记；登记后从 Run 引用恢复同一 Task。prepared／dispatched／资源等待／交付未同步的恢复沿用同一 call 与预算，不重复派发。
- 普通队列已结束但 closeout 尚未登记／尚未通过时，Run 仍未正常闭合；resume 必须继续本页，不能仅因普通任务已终态直接补 completed。仅补收尾报告仍遵循 report 原规则。
- 收尾 Task 已 completed 但 Run 关闭前，若 live inputs 漂移，保留原结果与差异，记录 interrupted 和恢复条件；不得重开终态或用同覆盖的新任务绕过门槛。先核对变化来源和授权：需要承接的本轮变更须由显式授权的普通 Task 重新 add/ready，再经 resume 恢复 running 后 append、执行和重新收尾；缺授权或无法安全承接时交付人工事项，也可按用户要求停止当前 Run。对纯暂时环境问题恢复原候选时须核实实际字节，不自动回滚用户修改。
- 用户停止或既有停止策略生效时，不创建／派发新审查；先处理在途事实并安全关闭为 stopped。收尾失败同样可按停止规则闭合并报告 failed/blocked，不冒充收尾通过。历史交付不因后续整改改写。
- list 从普通任务结果派生 not_started／queued／running／waiting／passed／outdated／blocked／failed／skipped，并显示轮数、任务引用、覆盖数量和只读边界。未执行不是 passed。
- report 汇总收尾是否通过、覆盖候选、findings、整改／复审／验证来源及遗留；用户停止未执行时明确注明。report 不补审、不修复、不从正文重判控制状态，仍在 Run 闭合后自动生成。

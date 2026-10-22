# Cohestra 调用契约与执行控制

## 契约字段

控制状态只读 `cohestra_task/README.md` 的 YAML Front Matter，字段与值采用 Cohestra 契约 0.8。Cadra 不修改契约、不解析自然语言正文来选择阶段。报告可以引用正文短摘要。

```yaml
contract: "0.8"  # 必填；当前支持的 Cohestra 契约版本
task:            # 任务标识，必须等于本 Task 的 slug
status:          # 任务状态：in_progress | completed | blocked | failed
execution_mode:  # attended | unattended；必填，核对本次声明
stage_result:    # 刚结束的阶段与其结果
  stage:         # need | design | code | review | fix | validate
  status:        # completed | blocked | failed
  round:         # 阶段轮次，整数；用于本次结果核对与中断恢复
candidate:       # 必填映射，报告与候选核对来源；无候选时两叶为 null
  commit:        # sha 或 null
  snapshot:      # 可复核快照来源（handoff 路径）或 null
findings:        # 未关闭问题计数（review/fix 交付后维护，可省）；报告素材
  blocking:      # 未关闭必做数，整数
  non_blocking:  # 非必做数，整数
  unresolved:    # 待核实未裁决数，整数，可省
acceptance:      # 验收结论（validate 交付后维护，可省）
  status:        # passed | failed | pending | blocked
next:            # 下一阶段与是否允许执行
  stage:         # 六阶段名 或 null
  allowed:       # true | false
  reason:        # stage_completed | blocking_findings | acceptance_failed | stage_failed | task_completed | human_decision_required | blocked | other
blocked:         # 受阻标志与原因
  value:         # true | false
  reason:        # human_decision_required | missing_input | missing_permission | dependency_unavailable | environment_blocked | candidate_unavailable | other | null
```

Cohestra 的 status 不含 Cadra 的 draft/ready/queued/running。stage_result 表示阶段交付，next 决定后续动作，candidate/findings 提供结果来源，acceptance 同时参与终态判定。协议版本升级需同步发布 Cadra 支持；实际加载版本不支持时停止，不以源仓库新文件代替。

## 前置检查与首个动作

建 Run 前确认目标为可安全写入的 Git 工作区、不是技能源仓库，实际 Cohestra 支持 0.8、unattended 与单阶段交付。缺 Cohestra 容器可由首次阶段最小初始化，Cadra 不代建。目标或协议前提不满足时不建 Run，不逐项制造失败结果。

- 首次启动：没有 README、没有六阶段正式 handoff，且 Run 来源链没有任何调用意图或核对收尾；仅有未执行 skipped 可以成立。核对后调用 flow start 一次，before=null；首次输出仍须通过完整契约与模式核对。
- 已有交付：检查 contract、task/slug、字段取值及绑定。绑定尚未确认时对照 README 目标与 requirement，用户明确确认对应关系后才能接续；明显不对应时请用户选择，不静默收养。此为身份检查，不用正文驱动阶段。
- 普通接续：合法旧契约按下表确定 next 或核对收尾；缺合法动作时说明缺口，不空建 Run。
- 显式恢复按 [恢复准入](recovery.md)，定义变更按 [修订准入](revision-rules.md)，不能将旧 blocked/failed 直接当作新的完成结论，也不能重新当首次启动。
- 已有正式交付或调用但缺 README、契约缺失/不支持/损坏时，停止整个 run 并报告路径；不允许忽略。索引修复归 Cohestra 或人工。

## 本次结果核对

调用前按 [Run 规则](run-rules.md) 保存拟调用阶段、execution_mode 与完整 before 契约。调用后先确认索引发布成功并回读，再核对 task、contract 与字段：

- stage_result.stage 必须等于拟调用阶段，round 为正整数。若 before 为同阶段，round 必须增加；跨阶段轮次不比较大小。
- execution_mode 必须等于本次声明 unattended；缺失、非法或 attended 均为 failed，不消费 next。
- index sync failed、同步无法确认、阶段不符或旧结果均不构成可用交付，即使文件看似新版也不能忽略失败信号。恢复需核对完整 README 与该轮 handoff 的阶段、轮次、候选和模式。
- 字段类型、枚举与 Cohestra 契约一致；next.allowed=true 时 next.stage 必须是六阶段名。协议不合法优先记 failed，不以表面 completed 放行。

已完整交付但 Cadra 未记结果时，resume 核实后补同一调用记录；无法确认派发/交付时保留证据并停止，不盲目重试。

## 终态映射

行序即优先级。先确定已完成、失败、受阻或正常范围边界；只有仍需调用时才检查预算，不能把第 16 次调用刚成立的完成结果改判失败。首次/恢复/修订的首个动作先按各自准入，不拿旧受阻结果提前结束新执行。

**必做后续**：next.reason 为 blocking_findings / acceptance_failed / stage_failed；或刚交付 fix/validate 且 next.stage=review；或刚交付 validate 且 acceptance.status=pending。正常后续超出 allowed 可收尾，必做后续超出则 blocked。下表“flow 内/含”均指规范化 allowed 集合。

| # | 结构化状态 | 判定 |
|---|---|---|
| 1 | 结构化状态缺失、无法解析、字段不合法（`next.allowed = true` 时 `next.stage` 必须是六阶段名，为空或非法即不合法）、`task` 与 slug 不一致，或本次结果核对失败（含索引同步失败、`execution_mode` 与本次声明不符） | `failed`（记录错误、调用前状态与恢复条件，不消费旧 `next`；执行模式不符时列入需人工介入） |
| 2 | Agent 执行异常、工具调用失败、无法恢复执行状态 | `failed`（记录错误与恢复条件） |
| 3 | `status = failed`，或 `next.reason = stage_failed` 且 `next.allowed = false` | `failed`（记录错误与恢复条件） |
| 4 | `status = blocked`，或 `blocked.value = true` | `blocked`（记录 `next.reason` / `blocked.reason`） |
| 5 | `status = completed` 且 `acceptance.status = passed` | `completed` |
| 6 | `status = completed` 且 `acceptance.status = failed` | `blocked`（验收未通过，缺人工决定后续处置） |
| 7 | `status = completed` 且验收非 passed／failed（缺失、`pending`、`blocked`），本 Task flow 序列含 validate | `blocked`（验收无结论，缺人工决定） |
| 8 | `status = completed` 且验收非 passed／failed，本 Task flow 序列不含 validate | `completed`；保留已知验收结论，无结论才标注 `unknown`，列入需人工介入 |
| 9 | `next.allowed = false` | `blocked`（含 Cohestra 明确禁止继续与需人类决定，不把禁止继续当作正常边界） |
| 10 | `next.allowed = true` 且 `next.stage` 在本 Task flow 内 | 非终态：执行下一阶段（含可重试的本阶段失败与 `blocking_findings` 触发的整改，受下文调用预算约束） |
| 11 | `next.allowed = true` 且 `next.stage` 是六阶段名但不在 flow 内，且属于上述必做后续 | `blocked`（必做阶段超出 flow，记录缺失阶段与实际验收结论，交用户调整 flow 或决定处置） |
| 12 | `next.allowed = true` 且 `next.stage` 是六阶段名但不在 flow 内，且不属于上述必做后续 | `completed`，以正常 flow 边界为终点；Run 与报告必须标注被截断及未执行阶段，保留已知验收结论、无结论才写 `unknown`，列入需人工介入 |


Cohestra 的 task_completed 也可能来自对话里的用户终点声明，Cadra 无法机器核对该声明；因此仍按 allowed 是否含 validate 要求验收。保留已知 acceptance 原值，缺失或 null 才记 unknown。正常边界与未验收的完成仍说明范围及人工介入，不冒称验收通过。

## 调用预算

每个 Task 在每个 Run 内独立累计三项上限：

| 上限 | 消费条件 | 达限行为 |
|---|---|---|
| 逐阶段失败重试 2 次 | stage_result.status=failed，或 next.reason=stage_failed 且 next.allowed=true 后追加该阶段调用 | 不再追加该阶段失败重试；穿插阶段或成功不返还额度 |
| 整改 3 轮 | 调用 fix，原因为 review 给出的 blocking_findings | 拦第 4 次此类 fix；第 3 次 fix 后仍可做必要复审 |
| 总调用 16 次 | 每次阶段调用意图 | 不再创建第 17 次调用；包含失败、补证和验收整改 |

只有需要继续调用时检查适用上限，任一不足则 failed 并列人工介入。acceptance_failed 引发的 fix 不计入 blocking_findings 整改轮，仍计入总调用；无需调用的核对收尾不计费。

预算与调用意图同次持久化，预算总额必须等于 calls 中 charged 的累计值；调用 id 在该 Run/slug 内唯一。resume 核对同一调用不重复计数、不清零、不返还不明派发的预占。来源缺失或计数矛盾时停止，不补造预算。已结束 Run 的显式恢复使用新 Run 的预算，但需重新通过授权与恢复准入。

连续相同结果不另作提前停止判断；是否可继续由契约与上述预算决定。

## Unattended

每次调用声明 execution_mode: unattended；Cohestra 应把需人类决定、权限/输入缺口等表达为 blocked 或 next.allowed=false，而不是等待交互。Cadra 不替用户做产品决策、不扩大范围、不获取新的隐含授权。默认记录 blocked/failed 后继续其他任务，策略停止按 Run 规则。

Cadra 不调用 verify，也不为其未执行生成跳过记录；review、复审与验收要求保留。resume 沿用原模式与策略，不切换执行模式。

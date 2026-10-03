# <run-id>

## Run 身份

- run-id：<run-YYYYMMDD-NN>
- 状态：running / completed / stopped / interrupted（附原因）
- execution_mode：unattended
- 建立：<执行者、实际时间及时区、Skill 发行版本、任务/Run 协议版本>
- 范围：<入队任务选择口径，如“全部 ready”或 slug 列表>
- 恢复选择：<本次显式恢复的 blocked/failed slug 列表，或无；必须包含在显式范围内>
- 修订重启：<本次按第 6.3 节重启的 slug 与 rev-序号、原终态、重启起点，或无>
- 队列顺序：<引用 queue/order.md；简列 slug 顺序>
- 技能依赖：<cohestra 技能可用性检查结论>
- 目标与初始化前提：<目标绝对路径、Git 工作区根、是否已有 .cohestra、本轮是否需先初始化；建 Run 前已通过>
- 契约探测：<本次加载的 Cohestra 路径/版本、契约支持；各候选首次启动、已有契约或修订重启的检查结论；建 Run 前已通过>

## 逐任务执行记录

| slug | 状态 | 已完成阶段 | 当前候选引用 | findings 摘要 | validation | 需人工介入 | 下一步 |
|---|---|---|---|---|---|---|---|

findings 摘要与 validation 只写短摘要并标注来源文件，不复制 Cohestra handoff 正文。

## 逐 Task Checkpoint 与结果快照

每个入队 Task 分别复制以下小节；全局只有一个当前 running，但不覆盖其他 Task 的记录。调用记录追加，结果快照绑定本 Run，不从后来更新的 Task/README 重建。

### <task-slug>

- 入队写入进度：<enq-<run-id>-<NN>；① run-written / ② task-queued / ③ complete；中断留下部分写入时按公共流程第 4 节第 7–9 条由 resume 幂等补齐，未补齐不调用阶段>
- 入队定义快照：<title、slug、requirement、flow、dependencies、priority、execution policy、cohestra_task 与 Gate 依据；补齐部分写入时以本快照为唯一比对依据>
- 来源 Run：<恢复任务的原 run-id、checkpoint/结果快照引用；修订重启的 rev-序号、旧定义快照与原终态；或首次入队>
- 恢复依据：<解除原因的事实、本次补充、授权来源、Gate 逐条核对；无则写无>
- 首个动作：<首次启动 / 正常接续 / 恢复重试 / 恢复核对收尾 / 修订重启 / 修订收尾；拟调用阶段或不调用的核对动作>
- 授权消费：<不适用 / 恢复授权或修订重启授权尚未消费·已消费；首个调用落盘前记已消费，各只允许一次；修订收尾在结果落盘回读后关闭修订记录>
- 最后交付：<阶段名、stage_result.status、round、handoff 与 README 来源；交付结束不等于通过>
- 待调用/本次调用：<调用原因、拟调用阶段、本次声明的 execution_mode、调用前完整控制状态及 stage_result.stage/status/round（无则写无）；调用前落盘并回读>
- 索引核对：<同步成功 / 失败 / 尚未确认；阶段/轮次与 execution_mode 核对、恢复确认依据>
- 调用预算与整改轮：<本 Run 内该 Task 已消费的阶段调用总数（上限 16，按已发起调用计、不含不调用阶段的收尾）、由 blocking_findings 触发的 fix 整改轮数（上限 3）、按阶段保存的已追加失败重试次数（0–2）、上次核实结果与无进展判定、已计入的调用标识（run-id + slug + 调用序号及阶段/轮次）；resume 不返还、不重置、不重复计数；无则写无（第 6 节三项上限）>
- 出队回写：<deq-<run-id>-<NN>；① Run 结果快照与出队结论已写 / ② Task 终态（或 skipped 回退 ready）已写 / ③ 队列行已回写；中断后按公共流程第 4 节第 8、9 条补齐；尚未结束写无>
- 最近结构化状态：<status、stage_result、candidate、findings、acceptance、next、blocked 与来源>
- 闭合标志：<已闭合 / 未闭合；恢复核对收尾记核实依据，尚未调用注明未执行>
- 中断与恢复记录：<时间、原因、resume 或新 Run 恢复核对结论>

| 调用序号 | 原因与授权来源 | 拟调用阶段 | 调用前阶段/结果/轮次 | 本次阶段/结果/轮次 | 同步与模式核对 | 预算消费（累计调用/整改轮） | 闭合与时间 |
|---|---|---|---|---|---|---|---|

- 本 Run 结果快照：<本轮状态或尚未结束；结束时保存 completed/blocked/failed/skipped、最后交付、候选、findings、acceptance、人工介入、下一步、来源文件/阶段/轮次与时间；后续 Run 不改此快照。**本字段写入即表示该 Task 进入出队阶段**，补齐阶段判定以此为准（公共流程第 4 节第 9 条）>

## 执行摘要

- 报告链接：<runs/<run-id>-report-<轮次>.md 列表；尚无则说明>
- 汇总：<completed / blocked / failed / skipped 计数>
- 剩余任务处置：<出队回 ready 清单及原因，或无>
- verify 跳过汇总：<unattended 跳过清单，或无>
- 停止原因与人工介入清单：<无则写无>

- 最近更新：<执行者、实际时间及时区>

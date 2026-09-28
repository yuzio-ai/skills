# <run-id>

## Run 身份

- run-id：<run-YYYYMMDD-NN>
- 状态：running / completed / stopped / interrupted（附原因）
- execution_mode：unattended
- 建立：<执行者、实际时间及时区、Skill 发行版本、任务/Run 协议版本>
- 范围：<入队任务选择口径，如“全部 ready”或 slug 列表>
- 队列顺序：<引用 queue/order.md；简列 slug 顺序>
- 契约探测：<Cohestra 结构化状态是否就绪、探测结论、用户选择>

## 逐任务执行记录

| slug | 状态 | 已完成阶段 | 当前候选引用 | findings 摘要 | validation | 需人工介入 | 下一步 |
|---|---|---|---|---|---|---|---|

findings 摘要与 validation 只写短摘要并标注来源文件，不复制 Cohestra handoff 正文。

## Checkpoint

- 当前 running：<slug 或无>
- 最后完成阶段：<阶段名及对应结构化状态来源>
- 闭合标志：<已闭合 / 未闭合；未闭合即中断点，resume 须重新核对>
- 中断与恢复记录：<时间、原因、resume 核对结论>

## 执行摘要

- 报告链接：<runs/<run-id>-report-<轮次>.md 列表；尚无则说明>
- 汇总：<completed / blocked / failed / skipped 计数>
- 停止原因与人工介入清单：<无则写无>

- 最近更新：<执行者、实际时间及时区>

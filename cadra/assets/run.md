---
protocol: "0.6"
run_id: <run-YYYYMMDD-NN>
status: running
execution_mode: unattended
created_at: <ISO-8601 带时区时间>
skill_version: "0.6.0"
tasks:
  - slug: <task-slug>
    revision: 1
    previous_run: null
    state: queued
    definition: <完整 Task 定义、requirement、修订依据与 Gate 快照；使用 YAML 映射>
    start_action: <首次启动/正常接续/恢复重试/恢复核对收尾/修订重启/修订收尾，阶段或核对动作及来源依据>
    authorization_consumed: false
    budget:
      calls: 0
      remediation: 0
      retries: {}
    checkpoint:
      pending_call: null
      last_delivery: null
    calls: []
    result: null
reports: []
---

# <run-id>

## 建立依据

- 范围与恢复选择：<显式 slug 或全部 ready；恢复列表与本次授权依据>
- 目标与前提：<目标绝对路径、Git 根、可写检查、Cohestra 容器是否待初始化>
- 契约探测：<实际加载的 Cohestra 路径/版本、契约 0.8 与 unattended 支持>
- 准入：<逐项 Gate、绑定、来源链与首个动作核对；仅来源与短摘要>

## 记录约定

tasks 数组顺序是执行顺序，slug 唯一；条目状态、预算与记录只维护在 Front Matter，不另建重复状态表。previous_run 引用该 slug 的上一个 Run，首次为 null。definition 是固定快照，正文只补建立依据与恢复说明。

每次调用向 calls 追加：

```yaml
id: 1                       # 该 Run/slug 内递增，不因 resume 重建
reason: <调用原因与授权来源>
stage: <拟调用阶段>
execution_mode: unattended
before: <调用前完整契约或 null>
dispatch: prepared          # prepared / dispatched；都不是交付证明
closed: false
result: null                # 成功核对后的完整契约、handoff 引用与同步证据
charged: {calls: 1, remediation: 0, retry_stage: null}
prepared_at: <ISO-8601 时间>
```

调用意图与累计 budget 在同次更新中落盘；checkpoint.pending_call 指向未闭合调用 id，last_delivery 记录最近核实的阶段、结果、轮次与来源。closed=true 时必须已有核实 result；无法核实的 failed 保留 closed=false 和恢复证据。累计 budget 必须与 calls.charged 一致。

条目 result 与终态同时写入，包含 state、最后交付、candidate、findings、acceptance、人工介入、下一步、来源文件/阶段/轮次和带时区时间。skipped 写明未调用与原因；核对收尾说明未调用及沿用来源。非终态 result=null；终态不得缺 result。

## 中断与恢复说明

<追加实际时间、派发/同步证据、无法确认的事实与后续核对；不覆盖调用记录>

## 收尾

- 停止原因：<如适用>
- 正式总结：<如需共享交付，登记路径>
- 最近更新：<执行者、带时区时间>

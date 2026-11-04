# Cohestra closeout 跨会话并发实测

日期：2026-11-04（Asia/Shanghai）。实际执行 Cohestra 0.16.0 / 协议 0.8；两组冻结技能均与最终仓库包逐文件摘要一致。原技能规则未改，本轮新增隔离探针、回归与验证记录。

## 结果

| 场景 | 实际观察与核对 |
|---|---|
| 同项目已有未完成 Cadra Run，两个任务范围独立 | alpha、beta 两个真实执行会话分别完成 review-01 → validate-01，无空 fix；两项最终均 completed / passed。未因 Run.status=running 整体受阻，Cadra 记录原字节保持不变 |
| 两个 validate 共用验证器 | 两个实际子进程同时排队，持锁者仍运行时没有任何验证进程进入临界区。释放后两进程先后执行并各自退出 0；没有旁路、重放或把排队当作测试失败 |
| 两项任务修改同一个 shared.py | 后启动的 beta 根据真实活动会话的占用信息在入口停止：正式阶段 0、reviewer 0、业务写入 0。它指出 shared.py 冲突，未归因为不相干的 Cadra Run |
| 冲突解除后明确接续 beta | alpha 实际完成并停止后，controller 核实新候选、释放事实及历史摘要，再明确接续 beta。beta 采用包含 alpha 改动的新快照完成 review → fix → 独立复审 → validate；alpha 函数、文件、全部任务记录和回复保持原字节，首次 beta 停止回复也保留 |
| 最终合并候选 | controller 独立执行全部 8 项单元测试与 12 个直接调用用例，均通过；最终审计再次绑定相同 shared.py 摘要 |

共享验证器的实际临界区（同一宿主 monotonic_ns）：

| 进程 | 开始 | 结束 |
|---|---:|---:|
| alpha / PID 84009 | 610390631997000 | 610391640949541 |
| beta / PID 85576 | 610391650306666 | 610392660474791 |

两区间不重叠。alpha、beta 实际等待分别为 408.533 秒、50.302 秒；等待由 controller 故意持锁触发，不是 closeout 性能基准。

共享源码观察到的变化依次为「两项待修」→「仅 alpha 已修」→「两项已修」。最终 shared.py SHA-256：`39e13677c11df3c5e9d27fc8110c72e40f991aa5b5f01a7f52c6c41662de2055`。两项冲突任务各实际执行 4 个阶段、1 轮 fix，分别关闭 F-ALPHA-001 与 F-BETA-001；没有改写对方的历史契约或验收事实。

## 实际会话与来源

- 执行会话：`/root/parallel_alpha`、`/root/parallel_beta`，相互隔离上下文，共享实际项目文件系统。
- 独立 reviewer：首组为各自的 alpha_reviewer / beta_reviewer，第二组另建 overlap_alpha_reviewer / overlap_beta_reviewer；均由宿主实际创建，未代替作者身份。
- 宿主只有一个额外 reviewer 容量槽，controller 串行授予该槽；主 closeout 会话及两个排队的验证进程确实同时活跃。此容量安排未改动 Cadra 队列或 Run。
- Cadra 记录是明确标记的协议 0.12 夹具，由生产 guard 接受并判为未完成；owner 活性和验证资源占用使用真实受控进程。没有运行真实 Cadra 工程派发。
- 文件重叠测试没有用文件锁替 agent 阻止写入。它提供实际宿主占用事实和必要来源，由 beta 自行按技能停止冲突部分；controller 在初审后设置观察暂停，确认 beta 已停止后才继续 alpha。

[机器可读证据](2026-11-04-closeout-concurrency.json)包含冻结技能摘要、Run 摘要、实际角色、阶段及回复摘要、完整资源事件、候选变化、控制边界与合并检查输出。完整临时项目位于 `/private/tmp/cohestra-concurrent-disjoint-20261104` 和 `/private/tmp/cohestra-concurrent-overlap-20261104`，可能被系统清理；保存的证据不等同于完整工作区备份。

所有 controller 创建的 owner、holder 和被动文件观察进程均已确认退出 0；实际执行会话报告其 reviewer、工作进程和验证工具均已停止。观察器在 alpha 完成、beta 尚未接续的边界续开一次，续开前后文件摘要相同。

## 验证与结论边界

- `python3 -B -m unittest discover -s tests -p 'test_*.py'`：500 项通过，包含完整 Git 历史版本检查，无跳过。
- 新增的 2 项探针回归实际运行两个进程验证等待与互斥，并确认审计器能拒绝重叠临界区；它们不模拟 agent 的阶段决定。
- 本次证明：在范围、占用信息与项目验证锁可核实时，不同任务可独立 closeout；Cadra 单一 Run 不是项目级全局门禁，已知文件冲突能够停止后安全接续，共享验证可遵守项目互斥规则。
- 本次不证明：无占用信息时自动发现或防止任意并发抢写、Cohestra 自带跨会话全局锁／资源调度，或其他宿主上的同等行为。共享验证的互斥由项目提供的实际 OS 进程锁保证。

未同步全局安装副本、提交、推送或发布；没有修改真实业务项目或真实 Cadra 运行记录。

# 进程崩溃与半写入恢复补测 · 2026-10-22

结论：5 个故障场景的安全性断言全部通过。3 个现场恢复完成，2 个证据不完整的现场安全停止。未发现重复执行 code、重复扣减原调用预算或恢复过程覆盖旧交付。

## 场景与结果

| 故障现场 | 恢复行为 | 本轮新增阶段 | 调用预算 |
|---|---|---|---|
| Run 临时文件写到一半 | 忽略并保留残片，核实交付后闭合原 call 1 | review-01、validate-01 | 1 → 3 |
| Run 已原子替换，回读确认前退出 | 识别 call 1 已闭合，原调用逐字段保持 | review-01、validate-01 | 1 → 3 |
| 首次 code handoff 写到一半 | 保留半份交付及未闭合 call 1，任务 failed，Run 结束 | 无 | 保持 1 |
| 首次索引临时文件写到一半 | 核实完整 handoff 后恢复索引，闭合同一 call 1 | review-01、validate-01 | 1 → 3 |
| Run 正式文件截断 | 记录完整性不成立，保留原始字节并停止 | 无 | unknown，不重建 |

每个场景另执行一次 resume；前后文件哈希映射一致。对可恢复场景，call id 保持 1、2、3，原 code 计费不变，新增预算仅对应实际 review/validate；没有 code-02 或恢复重试。这里的预算指 Cadra 调用账本，不是模型服务账单。

## 方法与证据

基础现场取自上一轮真实工程的 code-01 已交付、call 1 未闭合检查点。建立五份隔离 Git 项目，先重定位绝对路径及相关哈希，再注入故障。原检查点不变，复制的 code 历史不算本轮执行。

[注入脚本](inject.py)启动实际文件写入子进程，写入并 flush/fsync 后阻塞；主进程发送 SIGKILL，五次退出码均为 `-9`。临时文件场景保留正式文件；替换场景执行 `os.replace` 后、回读确认前终止。Run 正式文件截断是主动模拟存储损坏/非规范写入，不声称正常原子替换会产生半份正式文件。[注入核对](injection-checks.json)和[会话参数](session.json)保存 PID、字节数、边界与来源哈希。

三名空上下文执行者仅读取各自项目现场和源技能，按实际规则恢复；不读取旧模型、报告或预期结论。恢复中的 review/validate 实际执行，共新增 6 次阶段调用。索引修复先在独立工具调用中校验，再于后续调用原子发布。首次校验曾因相对/绝对路径比较不一致失败，修正校验辅助后重新通过才发布，未绕过失败关口。

主会话对归档重新核对：

- [可执行断言](verify.py)与[结果](parent-checks.json)：五组前后文件字节、旧 Run/Task/交付/候选、调用编号与计费、失败保留、重复 resume 均通过。
- 三个成功现场分别重新运行相同的 5 项 unittest 和 8 组独立业务输入输出，均通过；不将它们计作不同的测试案例。[业务结果](parent-business-results.json)
- [源文件前](source-before.json) / [源文件后](source-after.json)：45 个 Cadra/Cohestra 文件不变。本轮只增加验证资料，未修改技能或测试模型。
- 原故障、恢复前后项目、哈希清单分别保存在五个场景目录；原始路径保持为实际测试路径，归档不再重写。

各执行者结果：

- [Run 临时半写](run_temp_partial/after/verification/recovery-result.json)
- [替换后确认丢失](run_replace_ack_lost/after/verification/recovery-result.json)
- [handoff 半写](handoff_partial/after/verification/recovery-result.json)
- [索引临时半写](index_temp_partial/after/verification/recovery-result.json)
- [Run 正式文件损坏](run_primary_partial/after/verification/recovery-result.json)

可从仓库运行 `python3 -B tests/evidence/cadra-v0.6/crash-recovery-01/verify.py` 只读复核。注入脚本拒绝覆盖已有测试证据。

## 恢复边界

这是实际文件写入进程 SIGKILL 加独立技能恢复，尚不等于整个 Codex 进程崩溃、断电、磁盘故障、远端请求或并发写入测试；也不构成任意环境的 exactly-once 保证。

半份 handoff 需要可信完整原交付或可核实的恢复证据，再按 Cohestra 发布规则修复，并由新 Run 显式恢复。正式 Run 损坏需要可信完整备份和调用来源；不能把临时文件或预算可见片段直接当成完整状态。保留现场停止是预期保护，不标为业务恢复完成。

索引临时半写场景恢复的是经核实的完整索引语义；原丢失正文不能逐字还原，报告没有宣称字节级恢复。未安装、提交或发布技能。

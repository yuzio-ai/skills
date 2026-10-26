# Cadra 真实跨会话接管验证 · 2026-10-25

结论：三个场景通过。使用 7 个真实临时 Codex 会话，其中 2 个由宿主实际中断，另外 5 个正常结束。不是脚本伪造观察或单元测试替代执行。

| 场景 | 实际操作 | 核验结果 |
|---|---|---|
| 交付后中断 | 会话 A 实际执行 Cohestra code、通过两个 unittest 并发布交付；宿主在 Cadra 闭合调用前中断 A；会话 B 接管 | generation 1 → 2；复用 call 1，预算仍为 1；原 Cohestra 文件摘要完全不变，没有重跑阶段 |
| 派发前中断 | A 保存 prepared 意图后，宿主在调用 Cohestra 前中断；B 接管并真正执行代码阶段 | 沿用 call 1 和已消费预算；只有一轮 code 交付，Run 完成 |
| 重复 resume | 两个恢复场景各由第三个新会话再次请求 resume | 已结束 Run 保持只读；整个 `.yuzio` 的文件集合与摘要完全不变 |
| 旧协议拒绝 | 新会话读取隔离的 0.6 running Run 并请求 resume；随后另测写入器 takeover 边界 | 会话拒绝接管，记录不变；guard 非零退出并明确 legacy is read-only。guard 可创建短时锁文件，但未改 Run |

## 环境与可复核证据

- CLI 0.154.0；沿用用户已配置的模型；每个测试会话为 ephemeral、workspace-write，额外审批策略为 never。
- 明确加载临时副本 Cadra 0.7.0 / 协议 0.7、Cohestra 0.12.0 / 协议 0.8。副本与本轮源文件逐项哈希一致；已安装技能保持原样。
- 原始项目、驱动、RPC 事件、宿主中断证据及完整 Run 保留在 `/private/tmp/cadra-live-handoff-vaYJY1`。SQLite 和日志也位于该临时目录；未复制登录凭据。
- 真实身份、thread/turn ID、前后预算、Run/交付哈希和原始证据摘要见 [机器可读证据](2026-10-25-live-handoff.json)。临时目录可能被系统清理；本报告及摘要保留在仓库。
- 宿主依据：实际 `turn/completed(status=interrupted)`，随后 `thread/backgroundTerminals/list` 确认为空；需要时仅终止本测试的暂停进程。不把 idle 或时间过久当作停止证据。接口依据为 [官方 App Server 文档](https://learn.chatgpt.com/docs/app-server)。
- 连接发生 28 次自动重试通知，随后真实工具调用成功；没有把超时重试算作接管成功。
- Mewoo `.yuzio` 的 4227 个文件前后哈希和文件集合完全一致。所有实际任务与中断均限于临时项目。

## 范围边界

重复 resume 验证的是完成后的串行重入。两个真实恢复会话同时竞争、操作系统崩溃或断电中的原子替换不在本次实测范围；并发写入仍由现有进程竞争回归覆盖。

旧协议使用专门构造的最小拒绝夹具，缺少 Task 和预算等执行前提；会话首先按协议边界拒绝，guard 也在旧头部读取阶段明确拒写。本项不证明完整旧版流程可运行，没有执行旧版阶段或迁移真实记录。业务 fixture 的既定 flow 仅含 code；review/validate 未执行，不能将 Run completed 解释为完整产品验收。未使用 Simulator、未提交、未推送、未更新用户级安装；三个临时 Git 项目的提交数均为 0。

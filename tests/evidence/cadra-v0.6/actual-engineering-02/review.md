# 修复后实际工程验证 · 2026-10-22

结论：本轮中断恢复与连续修订场景通过，未发现遗漏或新增执行问题。完成 2 个业务任务、6 个 Run、9 次真实 Cohestra 阶段调用；不是测试模型重放。

## 执行与恢复

使用源仓库 Cadra 0.6.0 / 协议 0.6、Cohestra 0.10.1 / 契约 0.8，在独立临时 Git 项目实现 Python 问候服务。五名空上下文执行者按检查点顺序接力，只读取项目现场及源技能，未读取旧测试模型或复核结论。辅助脚本只写入、校验、发布和保存证据，不替代阶段判断或任务调度。

| Run | 任务与修订 | 实际结果 | 阶段调用数 |
|---|---|---|---:|
| 01 | prefix-source r1 | code-01 → review-01 → validate-01，passed | 3 |
| 02 | greeting-service r1 | 两次恢复后 code-01 → review-01 → validate-01，passed | 3 |
| 03 | greeting-service r2 | 开始前发现依赖当前修订 draft，条目 blocked | 0 |
| 04 | prefix-source r2 | 策略修订，核对并沿用旧候选与验收 | 0 |
| 05 | greeting-service r3 | 当前仅改策略，累计 r2 的需求变更；code-02 → review-02 → validate-02，passed | 3 |
| 06 | greeting-service r4 | 纯策略修订，沿用 code-02 / validate-02 | 0 |

Run 03 已结束但其条目仍为 blocked；后续修订不改写该事实。最终没有未结束 Run，两个任务的当前修订均 completed。

- [检查点 01](checkpoint-01/snapshot.json)：主任务 running，但首次意图尚未写入，调用与预算均零。新执行者重新准入后正常派发。
- [检查点 02](checkpoint-02/snapshot.json)：真实 code-01 与索引已完成，Cadra call 1 尚未闭合。下一执行者核实后闭合同一调用，再执行 review / validate；原调用编号、prepared_at、调用前记录及计费保持。
- [检查点 03](checkpoint-03/snapshot.json)与[检查点 04](checkpoint-04/snapshot.json)：需求 r2 已入 Run，依赖经正常 add 变为 draft。开始前依赖重核阻止执行，预算零、修订授权未消费。
- 依赖恢复后，只改主任务策略形成 r3。来源仍连接链尾 Run 03，执行依据追溯 Run 02，未执行的 strip 需求得到保留并落实。
- 两次已结束 Run 的 resume 均无写入，分别核对 56 个 `.yuzio` 文件和 119 个项目文件；纯策略收尾无新增阶段。

## 独立核对与业务验证

主会话另行检查原始 Run、Task、契约、候选、调用计费和哈希，并在最终归档上重新运行业务测试。核对脚本只断言已发生事实，不解释技能协议或生成执行结果。

- [最终业务 unittest](final-unittest.log)：5 项通过，含空白、Unicode、内部空白及动态前缀子案例。
- [额外最终输入输出](final-business-acceptance.json)：8 组通过；与[初版 8 组验收](initial-business-acceptance.json)对照，证明行为实际从保留首尾空白变为裁剪。
- 阶段执行者另验 10 个边界案例及动态前缀调用，原始日志保存在最终项目 scratch；[执行者审计](final/project/verification/final-engineering-audit.json)记录路径和结果。
- [主会话检查](parent-checks.json)：122 个归档文件哈希通过；检查点 04 的 82 个既有文件中，77 个不变，5 个变化均为当前 Task、当前索引及新业务实现/测试。旧 Run、正式 handoff、候选和历史测试证据保持。
- [技能前](source-before.json) / [技能后](source-after.json)：45 个源文件哈希一致，本轮没有修改技能。
- [可复核脚本](verify_final.py)及[检查退出码](parent-validation-results.json)；[完整最终归档](final/snapshot.json)保存文件清单和哈希。

## 边界

两次中断均为预设边界停点，不是进程崩溃或断电。该验证覆盖首次意图前中断、完整交付后未闭合调用，以及需求受阻后连续策略修订；不覆盖任意半写入、并发写入或所有异常契约。Flow 起点变更、非法枚举和 candidate 类型仍由前轮规则与模型回归覆盖，不计作本轮工程实测。

初版 code 与后续 review 由不同执行者完成；新候选 code-02 / review-02 为同一执行者的作者审查，未标为独立代码审查。主会话另做证据与业务输出核对。

所有检查点保留原绝对路径与实际时间，归档不重写原交付。可在本仓库运行 `python3 -B tests/evidence/cadra-v0.6/actual-engineering-02/verify_final.py` 核对。未安装源技能到本机副本，未提交或发布业务。

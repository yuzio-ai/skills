# Cohestra report 实际调用验证

时间：2026-10-15，Asia/Shanghai。Skill 0.10.0，协议 0.8。

## 调用与证据

- 执行者：独立子智能体 `/root/report_actual_call`，新上下文（`fork_turns: none`），未传入作者历史、期望答案或判定清单。
- 实际请求：使用本仓库 `cohestra/SKILL.md` 执行 `$cohestra report`，项目为 `/private/tmp/cohestra-report-validation-20261015-01/project`。
- 原始输入：由 [夹具脚本](cohestra-report-fixture.py) 创建 5 个任务、22 个文件。脚本只建立输入和采集文件系统快照，不生成报告、不实现 finding 合并逻辑。
- [实际报告](cohestra-report-actual-output.md) 保存子智能体最终回复正文，原保存时仅移除两行行尾空格；2026-10-21 将失效链接改指向按当前 `.yuzio/cohestra` 布局重建的[测试输入](fixtures/cohestra-report/project/.yuzio/cohestra/)，结论未重跑。由父智能体在调用结束、快照核对之后保存；保存证据不是 report 的文件写入行为。
- 调用前快照完成于 16:06:58，调用后快照完成于 16:09:09；报告记录时间为 16:08:02。
- [文件系统对比](cohestra-report-filesystem-check.json) 保存快照摘要、覆盖范围与逐项比较结果。完整前后快照也保存在上述隔离目录的 `before.json` / `after.json`；仓库中的夹具脚本、实际输出与摘要共同保留复现依据，不依赖临时目录作为唯一证据。

## 行为核对结果

以下逐项由父智能体比对原始输入与实际报告，不是报告生成器的单元测试。

| 检查 | 实际观察 | 结果 |
|---|---|---|
| 全部任务覆盖 | 总览包含 5 个任务；结构化进行中 1、已完成 3，旧正文已完成 1 分开统计 | 通过 |
| 已完成任务的延期项 | alpha F-102、beta F-102、旧任务无 ID 项均保留 | 通过 |
| 已完成且声明计数零 | epsilon 的 F-501 仍展示，保留索引 0 与明细 1 的冲突，未改计数或状态 | 通过 |
| 跨轮去重 | alpha F-102 跨 review-01 / fix-01 / review-02 仅列一项，来源链完整 | 通过 |
| 已关闭项不复活 | alpha F-101 经修复复审关闭后未列入遗留表 | 通过 |
| 不接受裁决不复活 | alpha F-103 裁决终结后未列入遗留表 | 通过 |
| 不同任务同名 ID | alpha 与 beta 的 F-102 分别展示，没有跨任务合并 | 通过 |
| 最新修复不等于关闭 | gamma F-301 经两轮整改与一次复审失败后只列一项，保持第二轮修改后待复审状态 | 通过 |
| 未知值保留 | beta / gamma 未推导验收通过；旧任务计数、验收保持未知，负责人待指派 | 通过 |
| 文件状态不变 | 项目 30 个、技能包 26 个条目的前后快照逐项完全相同 | 通过 |

## 只读验证范围

快照覆盖目标项目和本次加载的完整技能目录，包括隐藏文件及全部子目录。比较目录清单、文件 SHA-256、大小、权限、inode、mtime_ns 和 ctime_ns；读取可能改变的 atime 不纳入写入判定。前后条目均为 56 个，新增、删除、内容或写入元数据变化均为 0。

本结论是该次调用的项目与技能包文件状态证据，不是全系统文件写入追踪；不包含平台自身会话日志，也不保证所有其他输入与环境都会有相同行为。本轮未验证 CLI 安装/更新、缺容器入口、不可读文件或并发修改等其他场景。

## 复现

在本仓库根目录执行，使用一个尚不存在的隔离路径；前后快照存放在被测项目之外：

```sh
python3 -B tests/cohestra-report-fixture.py prepare /private/tmp/cohestra-report-new-run/project
python3 -B tests/cohestra-report-fixture.py snapshot /private/tmp/cohestra-report-new-run/project cohestra > /private/tmp/cohestra-report-new-run/before.json
```

在新上下文智能体中明确加载本仓库的 `cohestra/SKILL.md`，实际调用：

```text
$cohestra report
项目：/private/tmp/cohestra-report-new-run/project
```

调用结束后采集并比较快照，再按上表比对实际输出；不能用自行编写的汇总脚本代替 report 调用：

```sh
python3 -B tests/cohestra-report-fixture.py snapshot /private/tmp/cohestra-report-new-run/project cohestra > /private/tmp/cohestra-report-new-run/after.json
diff -u /private/tmp/cohestra-report-new-run/before.json /private/tmp/cohestra-report-new-run/after.json
```

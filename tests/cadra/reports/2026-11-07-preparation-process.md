# 人工确认交接与逐任务过程实测

本次候选：Cohestra 0.19.0／契约 0.8，Cadra 0.18.0／协议 0.12。三个独立执行会话在临时 Git 项目中实际调用技能；主会话回读控制状态、交付和文件摘要。冻结的两包共 71 个文件与最终源码逐文件一致，未升级实际安装副本。

以上冻结摘要及下方 517 项回归、12 组行为核对记录对应最初交付候选。后续独立审查及提交前复审发现的契约校验 P2 已分别修复，见末两节及 JSON 的 `post_review_fix`／`final_review_fix`；保留旧候选摘要，不将其改写成后续修复证据。

## 确认交接

文档练习的完整目标为：仅整理 notes.md，将一级标题改为 Notes、保留原文、末尾依次增加三项既定无序列表；准备阶段不实施。各例使用该目标及表中明确的决定／故障输入。

| 检查 | 实际结果 |
|---|---|
| 正常 need → 认可 → design → 认可 → add → ready | need-02、design-02 完成交接；Task ready；没有重复索取已有确认 |
| 已有明确认可，直接 add → ready | add 登记来源，ready 进入 Cohestra 受限准备，新增 design-02 并同步合法 next=code；Task ready |
| 对同一任务重复 ready | 复用 design-02，无新增轮次或等价 Gate 通过历史 |
| 缺少整体认可 | draft；未调用 Cohestra，原 blocked 保留 |
| 原方案已认可，但当前标题已改为 Notes v2 | draft；未调用 Cohestra，修订需重新收敛 |
| 保留或覆盖原文仍未裁决 | draft；未把局部认可当作整体认可 |
| 用户明确仅设计终点 | draft；保留 completed／task_completed，不自动开放 code |
| need 已获认可但没有 design 交付 | 新增 need-02、next=design；Task 仍 draft，未代做 design |
| 完成 handoff 已有、索引置回旧版 | 仅恢复 design-02 索引；Task ready，无 design-03，原 handoff 和恢复材料摘要不变 |
| 明确选择缺少受限交接能力的 Cohestra 0.18.0 隔离副本 | 认可项通过、起点不通过；draft，无 Cohestra 调用，不用新源码冒充旧副本能力 |
| design-02 写出后，外部操作者原子修改 Task 为新标题 Unreviewed | 新需求保留；旧方案交接没有放行新定义，Task draft、ready_scope=null |

上述所有准备项目的 notes.md 摘要保持不变，没有创建 Run 或执行工程阶段。索引恢复例是受控地恢复旧 README 的故障输入，不声称实际触发了文件系统发布故障；并发例则由独立监视进程在真实 handoff 创建后原子修改 Task，再核对该变更未被覆盖。

## 历史报告

使用 Mewoo 的 run-20261107-01 隔离副本，执行实际 `$cadra report`。只复制冻结 Run、原 report-01 和阶段 Markdown；没有复制底层工程快照、源码或原始运行日志。

- 还原 9 个任务（含收尾）、34 次调用、255 个调度事件；38 次验证完成中保留 6 failed／32 passed。
- 普通任务保留 4 completed／4 blocked，收尾 passed。没有用当前 Cohestra 状态覆盖旧结果。
- 原报告与旧报告链接保留；已有 report-02 链接但隔离文件缺失，报告明确 unknown，新增 report-03，未复用旧轮次。
- 登记后 Run 仅 reports 数组追加一项；其他结构化内容及正文与原 Run 一致，report-01 字节不变。过程读取前后 Run 字节不变。

“每月回顾”的实际展示保留完整整改链：

| 阶段 | 过程 |
|---|---|
| code-01 | 实现完成；已登记工程检查通过 |
| review-01 | MRPC-R1：首次照片读取失败缺少提示与重试入口 |
| fix-01 | 作者补充失败提示和整月重读，声明整改完成 |
| review-02 | 问题仍未关闭：无预览照片被误判为可重试错误 |
| fix-02 | 按 eligiblePhotos 与失败集交集分类，补生产 checker 回归 |
| review-03 | 独立复审明确关闭 MRPC-R1 |
| validate-01 | 工程和复审完成；必要原生证据缺失，保持 blocked |

完整实测报告还保留 DAS-R002、CO-R001 的整改／复审，以及编译失败且零测试、后续重验通过和历史 unknown。以上仅核对历史事实的还原和报告登记，不重新证明底层工程或设备验收。

## 检查与证据

- `python3 -B -m unittest discover -s tests -p 'test_*.py'`：517 项通过，无跳过，完整 Git 历史版本检查通过。
- 两包 skill-creator quick_validate 通过。校验器所需 PyYAML 仅安装在临时虚拟环境，未添加包内依赖。
- [过程工具回归](../test_process_view.py)新增 9 项：多轮整改、未闭合调用、同步未知／失败、验证先失败后通过、恢复来源、读取变化、只读文件、独立包 CLI 与精简候选。
- [结构化核对记录](2026-11-07-preparation-process.json)保存逐文件技能摘要、真实控制状态、交付摘要、并发注入摘要和历史过程结果。未打包完整会话转录、临时项目或底层工程证据。

未修改 Mewoo 业务文件、实际安装副本；未提交、推送或发布。

## 独立审查后的 P2 修复

- 原反例：交付的 acceptance.status=approved、负数／字符串 findings、非映射 candidate 或非法 next，曾返回 exit0、recorded、gaps=[]，部分类型错误被静默投影为 null。
- 现在在投影前核对被声明保存的契约必填字段、类型、枚举与基础一致性；损坏输入明确失败，错误带任务／call，stdout 为空。没有契约和合法可选缺省／null 仍保持未知，不新增字段或改变协议。
- 专项回归由 9 项增加至 13 项。独立审查者重放 4 个原 CLI 反例，均退出1，输入字节不变；直接／wrapper、可选字段缺省／null 及无交付兼容核对通过，原 P2 关闭，未发现新问题。
- 修复后全量 unittest：521 项通过，无跳过（33.322秒），完整 Git 历史版本检查通过；Cadra quick_validate 通过。
- 只读检查 8 份真实 0.12 Run 的副本，共23项任务／70次已登记调用；全部通过，副本字节不变。仅核对记录读取，不重验底层工程／设备证据，不重演原全部确认链路。
- 两包版本尚未提交；此次修复与原改动共用 Cadra 0.18.0，符合仓库未提交修改共用新版本的规则。Cohestra 0.19.0 与两包协议未变。

## 提交前复审补充

- 再次独立审查发现：validate 的 acceptance=passed 曾可与阶段blocked、任务blocked、next.reason=blocked同时进入正常视图。该组合违反既有0.8的validate完成联合约束，不涉及重新判断验收证据。
- 现要求本轮validate passed同时具有阶段／任务completed、next=null/false/task_completed和blocked=false/null；不将其他阶段保留的旧passed字段当作本轮validate完成。
- 原CLI反例现退出1、stdout为空、错误带任务／call，输入字节不变。独立复核确认该P2关闭，未发现新缺陷或合法历史记录误拒；专项15项通过，9份真实0.12 Run副本（27项任务／72次调用）兼容检查通过。
- 最终全量 unittest：523项通过，无跳过（36.153秒），完整Git历史版本检查通过；Cadra quick_validate通过。规则终审及修复后代码复核均无遗留可行动问题。
- JSON的 `final_review_fix` 保存本轮最终候选摘要与检查结果；此前的521项及初始冻结摘要仅代表各自记录时的候选。

# Cadra 完整审查

审查对象：当前工作区 Cadra 0.10.0 / 协议 0.10。Git HEAD 为 `c8e860a63b1a919c5a69190440a47c77342ebd07`；审查包括原有未提交修改，不等同于仅审查该提交。

结论：确认 **2 项 P2 写入保护缺陷**，另记录 **1 项测试覆盖缺口**。本次未修改技能包、现有测试、安装副本或项目执行资料，未提交或推送。

## 发现

### F1 · P2 · 已派发且未闭合的任务可以被发布为 skipped

- 位置：[run_guard.py:153](../../cadra/scripts/run_guard.py#L153)、[run_guard.py:328](../../cadra/scripts/run_guard.py#L328)。
- 既定规则：[run-rules.md:15](../../cadra/references/run-rules.md#L15) 仅允许尚未调用的 queued 项进入 skipped；已运行项停止时应核实后记录 blocked/failed 或实际结果。
- 当前 `validate()` 只禁止 queued 含 calls，并仅对 completed 禁止未闭合调用。`validate_update()` 对 running 的限制只有不得返回 queued，没有拒绝转为 skipped。
- 隔离复现：创建 Run → 登记 worker → 保存 prepared → 保存 dispatched 与派发证据 → 将该项改为 skipped、Run 改为 stopped。`guard.publish()` 接受；call 仍为 `closed=false`、`pending_call=1`；`unfinished()` 返回 false；随后 `create` 接受另一个 Run。
- 影响：停止分支一旦误标，写入器会把含未确认调用的批次判为已结束。list 按 skipped 展示准备状态，resume 又保留终态项，恢复入口与未完成批次门禁因此失真。复现未启动真实工具，不证明已有真实 Run 发生过这种误标。
- 建议：校验 skipped 必须没有 calls、预算、已消费授权及交付 checkpoint；转换只能来自符合条件的 queued。保留 failed 携带未闭合调用的合法恢复语义。
- 必要回归：prepared/dispatched/已闭合调用的 running → skipped 均拒绝且原文件字节不变；queued → skipped 正常通过；非法历史不得放行新 Run。

### F2 · P2 · 预算仅核对自报计数，未核对计费分类

- 位置：[run_guard.py:144](../../cadra/scripts/run_guard.py#L144)。
- 既定规则：[contract.md:95](../../cadra/references/contract.md#L95) 规定 review 的 blocking_findings 引发 fix 消费整改轮次；失败重试按实际阶段累计。
- 当前校验只检查 `charged.remediation` 是 0/1、计数相加一致和上限；`retry_stage` 非空就直接作为字典键，没有合法阶段及与 call.stage 一致性检查。
- 隔离复现一：按独立 reviewer/worker 绑定顺序保存 `review → fix` 四轮，完整记录每次 review 的 `next.reason=blocking_findings`，但每次 fix 自报 `remediation=0`。全部八次调用均被发布，累计整改仍为 0，第 4 次整改没有被拦截。
- 隔离复现二：code 调用填写 `retry_stage=made-up-stage`，预算字典填写相同键。发布成功。
- 影响：计费分类写错后，算术一致性检查无法保护“整改最多 3 轮”和“每阶段重试最多 2 次”；总调用 16 次的上限仍有效。完整契约与来源核验仍由调用者负责，因此这些结果证明写入器的保护不足，不证明遵守文字规则的执行器必然超限。
- 建议：至少将 retry_stage 限定为 null 或本次 call.stage；根据已保存 before、调用原因及 start_action 核对适用计费。首次/显式恢复等例外需明确判定，不能一律给所有 fix 收费。
- 必要回归：非法/错阶段 retry_stage 拒绝；blocking_findings 的 fix 少收费拒绝；第 4 轮整改拒绝；acceptance_failed 的 fix 不错误计入整改预算；第三轮整改后的必要复审仍可进行。

## 测试覆盖缺口

### G1 · 跨阶段复审的旧轮次没有被现有 oracle 排除

[model.py:167](../../tests/cadra/model.py#L167) 的 `result_valid()` 仅在紧邻 before 与本次同阶段时比较轮次。已有 review-01，经过 fix-01 后，再将 review-01 作为 review 结果传入，会返回 true。当前模型仍被 `model_current.py` 复用。

这说明“相邻同阶段轮次递增”和“各阶段独立编号”测试尚未覆盖复审循环的新交付识别。正式规则还要求核对旧结果、候选、实际执行者、派发来源与 handoff；本次没有证明实际 agent 会忽略这些要求，故不另列生产缺陷。

建议增加 `review-01 → fix-01 → 旧 review-01` 的拒绝用例及 `review-02` 的合法用例，并覆盖验收失败后的复验、跨 Run 接续和 pending 调用恢复。记录调用前目标阶段已有最高轮次或精确 handoff 指纹；不能拿 fix 的轮次与 review 的轮次直接比较。

## 审查范围与验证

| 范围 | 核查内容 |
|---|---|
| 七入口、SKILL 与全部 references | 定义/准入、来源链、修订、flow、状态、停止、恢复、追加、报告及读取边界 |
| Run guard | JSON 解析、结构约束、预算、角色绑定、停止观察、CAS、文件锁、原子替换与受限写入 |
| 模板与包边界 | Task/Run/项目模板、隐藏文件、版本、链接、独立包资源与运行依赖 |
| Cohestra 消费关系 | 契约 0.8、单阶段调用、角色隔离、复审及验收前提、发布与恢复接口 |
| 当前及历史回归模型 | 区分模型断言、真实 guard 文件/进程测试和历史宿主证据 |
| 一次性切换工具 | 旧记录闭合检查、来源链、归档、链接、安装替换、journal 与回滚路径 |
| 仓库说明 | 中英文 Cadra 入口、流程、恢复与版本采用说明 |

- 完整测试：`python3 -B -m unittest discover -s tests -p 'test_*.py'`，299 项通过，无跳过；含完整 Git 历史版本检查，仓库不是浅克隆。
- `git diff --check` 通过。
- 新增隔离探针：[reproduce.py](reproduce.py)，结果：[probes.json](probes.json)。Run 写入只发生在 TemporaryDirectory 中，未访问真实项目 Run。
- 审查输入：[Cadra 32 个包文件的 SHA-256](cadra-source-sha256.json)，包含隐藏模板文件，用于识别后续内容变化。
- 切换故障/回滚证据来自当前测试及源码核查；本次未对实际项目执行切换或回滚。
- 历史 live-smoke/接管证据只作覆盖边界参考；本次未重新执行宿主多 agent 派发、真实跨聊天接管、安装器验收或 OS 崩溃测试。

## 处理建议

先修复 F1，再补齐 F2 的机械校验及上述回归。G1 单独补测试和目标阶段新交付识别规则。修复后重跑完整套件，并针对停止后恢复及整改预算做一次隔离的实际技能验收。

上述建议恢复已有契约，不需要仅为缺陷修复升级协议。是否升级包版本应以修复时的 Git 历史为准；当前 0.10.0 尚未提交时可与同一未提交交付共用，提交后继续修改必须使用新包版本。

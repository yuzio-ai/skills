# Cadra 修复后独立复核 · 2026-10-22

结论：**未通过。原需求变更遗漏已修复，但发现 1 项新增模型回归，以及 3 项既有规则/模型缺口。** 本轮只复核和归档，未修改技能或测试模型。

## P2 · 新增：普通调用被误判为授权消费矛盾

位置：`tests/cadra_v06_model.py:104–106`，相关规则 `cadra/references/run-rules.md:15`。

真实组合：`new_item()` → `prepare(..., authorization=False)`（默认值）→ `recover_call(..., evidence='unknown')` → 保存 failed 条目的已结束 Run → 下一修订仅改策略 → `revision_action()` 抛出 `ValueError('inconsistent consumption evidence')`。

普通首次/正常 next 调用无需消费一次性恢复或修订授权。模型的 prepare 正确保留 false，但新 execution_basis 把 calls 非空且该标记 false 判为异常。规则审查者独立确认普通调用允许 false；主会话和模型审查者分别执行组合反例得到相同结果。现有来源链测试夹具对 completed/failed/blocked 统一设置 true，未覆盖这个合法组合。

建议：调用意图自身构成执行依据，不能以特殊授权消费标记作为所有调用的前提。补普通默认调用、失败恢复、后续策略修订的组合测试。无需调用收尾的依据也应与普通/恢复/修订三种授权语义一致。

证据：[主会话组合复现](parent-model-reproduction.json)、[独立模型复现及修正结论](model-audit.json)。这是测试模型回归，不是已证明的真实智能体执行故障。

## P2 · 既有：running 且尚无首次调用意图的恢复分支不明确

位置：`cadra/references/run-rules.md:13–18`、`cadra/references/resume.md:16–21`。

规则允许先保存 running，再保存首次意图；没有要求两者同次更新。若中间中断，可能留下 running、calls=[]、未消费 start_action。resume 只明确 queued、未闭合调用、已闭合调用三类处理；此时没有原调用或已核实 next 可用。

建议：将进入 running 与首次意图原子写入，或明确补充无调用时重核 start_action 的恢复分支。该项是文本覆盖缺口，未声称运行时必然失败。

## P2 · 既有：Flow 排列例外未排除起点改变

位置：`cadra/references/flow.md:3,13`。

列表首项决定 start，但第 13 行笼统豁免“列表排列”引起的 Gate 失效。`[code, review]` 改为 `[review, code]` 同时符合“排列变化”和“start 变化”，会得到相反的准入解释。

建议：仅在 start 和 allowed 都不变时豁免；首项改变仍应使 Gate 失效并进入修订。此项是规则表述冲突，未证明实际智能体选错。

上述两个规则文件及 run-rules 与修复前归档哈希一致，故不归因于此次修改。[核对记录](checks.json)

## P2 · 既有：测试模型未拒绝非法枚举

位置：`tests/cadra_v06_model.py:141–157`，对应 `cadra/references/contract.md` 的字段枚举和非法字段优先 failed 规则。

给 `next.reason` 或 `acceptance.status` 传入非法字符串时，result_valid 仍为 true，特定 review-only 场景 decision 返回 completed。主会话复算独立输入，得到相同输出。两段函数本次修复未改，因此为既有模型覆盖缺口。

建议：补全实际消费的枚举校验并增加非法字段回归。该项只影响测试模型对规则的验证可信度，不是技能运行时漏洞。

## 反证与范围

模型审查者曾认为 `next.allowed=false` 时保留阶段名也合法。交叉核对 Cohestra 0.8 `cohestra/references/workflow.md:132` 后撤销：该契约明确要求 next.stage=null，模型此处正确。原观察与撤销说明均保留在 model-audit.json，撤销项不计入发现。

两名独立智能体以空上下文启动；一名只读技能规则与模板，一名检查模型并自建边界输入。未向其提供原评审结论。首轮独立发现后，主会话提供组合反例和 Cohestra 反证开展交叉复核，因此组合回归属于双重复现，不标为双方各自独立发现。

现有全仓 168 项测试、其中 Cadra 61 项全部通过；静态检查 21 份文档、161 条链接无断链。独立模型审查运行 16 个额外案例；其中 2 项暴露旧枚举缺口，1 项预期经反证撤销，其余涵盖连续修订、prepared、合法无调用收尾、来源链拒绝及同 call id/预算恢复。之后新增普通调用组合反例，确认上述回归。

25 个 Cadra/模型/测试文件前后哈希一致：[前清单](source-before.json)、[后清单](source-after.json)。仅保存报告与证据；未安装、提交或发布。本次没有重新执行工程阶段，结论不能替代端到端行为验证。

完整材料：[规则审查](rules-audit.md)、[模型输入输出](model-audit.json)、[独立复现脚本](model-audit.py)、[检查记录](checks.json)。

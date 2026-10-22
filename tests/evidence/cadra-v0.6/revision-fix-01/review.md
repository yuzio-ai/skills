# 首调用前受阻的修订继承修复 · 2026-10-22

原独立复核的 P2 已完成规则与模型修复。未增加协议字段或运行时，发行版仍为尚未发布的 0.6.0。

## 修改

- 公共流程按调用意图或有效的无需调用收尾确定执行依据。无调用且未消费授权的 blocked/failed/skipped 不截断累计变更。
- 修订规则累计未执行的 requirement/flow，同时保留受阻原因的解除检查。
- 恢复规则明确首调用前受阻的 start_action 判定。prepared 或派发不明的调用必须先核实，不能重新赋予起点。
- 测试模型同步修正依据选择；测试夹具补足消费和调用证据。缺证据不推定未启动。

## 验证

新增 6 项回归测试。修复前 61 项 Cadra 测试中 4 项失败；修复后全部通过。全仓 unittest 168 项通过；包静态检查 21 份文档、161 条相对链接、0 断链；差异格式检查通过。[检查记录](checks.json)

沿用原复现输入，补齐 R1 已有调用和消费标记，原历史证据未改写。修复后依据为 revision 1，累计 `requirement + execution_policy`；原因解除时返回 start，未解除时 reject。[输入](input.json)、[模型结果](model-result.json)

独立智能体以空上下文读取技能及原始场景摘要，未读取测试模型、历史结论或预期答案。其判读如下：

| 场景 | 独立决定 |
|---|---|
| R2 requirement 修改但首调用前 blocked；R3 仅策略修改；原因已解除 | 以 R1 为执行依据，累计 requirement 与 execution_policy；完成 Gate/契约核对后从 code 起步；不能沿用 R1 验收收尾 |
| 同场景但原因未解除 | 不入队、不调用；保留当前定义和 preparation |
| R2 已保存 prepared 调用、授权已消费、派发与交付不明 | 以 R2 为依据；停止准入，先核实原调用；不得跳回 R1 收尾或重新给予 code 起点 |

独立判读还确认，新 Run 的 previous_run 仍指向链尾 R2，不因执行依据为 R1 而跳过 R2。输入是摘要，未包含完整 Gate 和契约证据；本次是规则判读验证，不是新的工程执行或真实准入验证。此前实际恢复实测仍保留在 [前轮报告](../independent-recheck-01/review.md)。

skill-creator 原生 quick_validate 仍因系统 Python 缺少 PyYAML 无法启动，未计为通过；[失败日志](quick-validate.log)。本轮未改变 YAML 元数据或模板，包静态检查通过。

[修改文件哈希](source-manifest.json)。未安装、提交或发布。

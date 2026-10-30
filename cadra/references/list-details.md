# list 详情与完整结果

仅在单 slug、指定 Run、角色详情或完整结果查询时读取。普通列表及仅历史 Run 一览不加载本页。入口及状态核对仍见 [list](list.md)，本页不授权写入或执行。

## 身份与历史结果

- `role_details[run-id]` 每个 Run 保存一次 protocol、source、executor，以及 `agents[slug]` 的完整实际绑定。单任务详情或队列通过 `roles_ref` 引用，再按 slug 取角色；不会因历史或 completed 折叠而遗漏身份。指定 Run 仅列该批身份，不混入后继 Run。
- 指定 Run 时，队列的 state、标题、revision、checkpoint、result、状态过滤和 counts 均取原批次。current_state/current_counts 单独表示当前 Task 状态。来源链矛盾仍显式报告，旧结果不因此被覆盖或改写。
- 单 slug 默认补充当前 revision、priority、flow、依赖状态/源协议、当前 Run 与 checkpoint 摘要；跨协议依赖不作为完成证据。角色引用按上项解析。

## 摘要与原文

- 默认 `result_mode: summary`。result 保留原 state、reason、candidate 引用、findings、acceptance、next、人工介入、来源与时间；最后交付保留阶段/轮次、handoff、同步与实际作者/工具停止证据。checkpoint 保留 pending_call 和最后交付摘要。
- 完整契约、额外原始载荷及 candidate.inputs 的省略以 `omitted_fields` / `inputs_count` 标明。摘要不是完整交付契约，不能替代执行前的原文核验。
- 用户要求完整字段时，用同一范围加 `--full-results`，得到 `result_mode: full`：指定 Run 的 result，或单 slug 的 checkpoint/result，按已保存原文解析值原样返回。该参数不扩大查询范围，也不迁移、重跑阶段或写入记录。亦可按返回的 Run 绝对路径及 slug 精确读取相应条目。
- 不批量展开无关记录补充省略内容；完整身份、原始结果和全量任务明细仍随实际返回量增长。千级/万级验证不表示这些明细会自动限制在模型上下文预算内。

# ready 的确认交接补齐

仅 ready 在起点项发现当前 need/design 的确认交接尚未发布时读取。普通 run/append/resume、内部生成收尾任务和 add 不调用此路径；它不改变唯一的八项 Ready Gate。

## 适用条件

先完成本 Task 的身份、修订、Run 归属和 Gate 只读检查。以下条件必须同时成立：

- 展示状态为 draft/ready，不属于任何未完成 Run，且不是 origin 非 null 的生成任务；没有待核对的工程调用、恢复或修订重启缺口。
- Cohestra 身份、契约 0.8 和当前输入有效，最近需收敛的正式阶段为 need/design；现存阻塞仅为待确认的 human_decision_required，或已有完成 handoff 但本轮索引待同步。
- 当前完整汇总已有明确整体认可或明确免除指令，必要关键决定齐备；确认对象、原始答复及来源可核对，且与当前内容和任务范围一致。不以 Task 中“已确认”、旧 completed、普通代决、add/ready 调用本身代替确认。
- 除该交接导致的起点缺口外，其他 Gate 项均满足。不得借补齐修需求定义、补设计、消除环境／权限缺口或推翻用户明确的仅设计终点。

不满足时保持 draft、清空 ready_scope，列出具体缺口和对应入口。确认已有但来源暂不可核实时要求补来源，不让用户重新认可同一方案。

## 调用与回读

1. 核对本次实际选择的 Cohestra 目录、release.json 及“确认后的阶段交接”规则确实支持本路径；不只比较版本号，不用源仓库替换旧安装副本。不支持时报告实际路径及升级／独立阶段交接的下一步。
2. 重读 Task、归属、当前索引和确认对象，保存其摘要。由当前主会话调用该目录的 `$cohestra need` 或 `$cohestra design`，传任务目录、当前完整汇总、原始认可／免除来源；限定“仅收敛当前阶段和索引，不改定义／业务文件，不执行后续阶段”。按 Cohestra 的 attended 准备规则执行，不建 Run、不派发工程 worker，不计 Run 预算。
3. Cohestra 是其 handoff／索引的唯一写入者。Cadra 不根据聊天构造 next，不自行改索引；已有完成交付只恢复同步，已有有效交接直接复用，不重复新增轮次。
4. 成功后回读交付及完整索引，核对同一任务、当前阶段／轮次和实际同步结果；重核 Task、归属及输入，变化则停止旧检查并按新事实重新判断，不覆盖未知更新。随后重做受影响的 Gate 和 ready_scope 指纹，不沿用补齐前的索引摘要。
5. need 若仅开放 design，明确建议 `$cohestra design`，不标为 code 已 ready。用户明确的仅设计终点不在本路径重开。最终仍需八项 Gate 全部通过才能写 preparation=ready；失败不创建 Run，按真实缺口交付。

在现有 Gate 正文记录确认对象／来源、实际 Cohestra 路径与版本、调用或复用／恢复的交付、同步结果及重核结论；不新增 Task/Run 字段，不将其写成工程执行历史。

例：用户已认可 design-01，索引仍为 design/blocked。ready 核实同一方案和认可后，由 Cohestra 新增 design-02 并同步，再重核 Gate。再次 ready 复用 design-02；如果 design-02 已落盘但同步失败，只恢复该轮索引。以上均不启动 code。

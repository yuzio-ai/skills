# Task 定义与 Ready Gate

## 定义与编辑

[Task 模板](../assets/task.md) 保存协议、slug、title、revision、preparation、requirement、priority、dependencies、flow、execution_policy、cohestra_task、修订依据与 Gate 历史。`revision` 为正整数，初始为 1；不要在 Task 保存执行状态、候选、调用记录或所属 Run 指针。

- priority 为 high / medium / low，缺省 medium；execution_policy 只含 `stop_queue_on_failure`，缺省 false；flow 缺省 full。
- dependencies 只能引用已存在 slug；悬空、自依赖或成环时拒绝该次修改。入队排序按 priority 高到低，同级按 slug 字典序；依赖未完成的任务不进入同一 Run，依赖链逐层推进。
- 定义编辑前按 [状态解析](workflow.md#状态解析) 核对 Run 归属；属于未完成 Run 或归属矛盾时拒绝修改。
- requirement、dependencies、规范化 flow 或 execution_policy 改变使 preparation 回 draft，并使当前 Gate 失效，追加来源、时间与变更字段。已入过 Run 的定义修订按 [修订规则](revision-rules.md) 分代，不覆盖旧快照。
- 只改 title/priority 不使 Gate 失效、不改变修订或执行结论。slug 与 cohestra_task 不可编辑。仅做语义等价的 flow 规范化不算定义变更。
- 同名 Cohestra 目录已有正式交付时记录主题与绑定确认；主题明显不对应或绑定未确认时不接续，请用户明确选择接续或更换 slug。后续检查见 [前置检查](contract.md#前置检查与首个动作)。

## Ready Gate

以下八项是唯一准入定义。ready 逐项记录结论和依据；run 的普通、恢复、修订候选均复核，开始/续跑前另重核依赖。复核不是隐式调用 ready，也不修改 Task。

| 检查 | 通过条件 |
|---|---|
| 目标 | 可判定的目标，不是待探索的方向 |
| 范围 | 做什么、不做什么清楚 |
| 验收 | 完成现象与验收条件可判定 |
| 人类决定 | 无待裁决的产品取舍或缺失授权 |
| 输入 | 必要输入、参考与环境前提齐备 |
| 依赖 | 所有依赖的当前定义展示状态均为 completed |
| 起点 | flow start 合法；接续/恢复/修订的首个动作可核对 |
| 范围配置 | flow 按起点与允许集合解释，配置有效 |

ready 只适用于展示状态 draft/ready：通过时 preparation=ready；未通过时 preparation=draft。旧 Gate 记录保留；同一定义重复通过不重复追加等价放行记录。其他状态先按恢复或修订入口处理，不靠 ready 重开终态。只有该修订已通过 Gate 且此次复核通过，才可进入 Run。

# Task 定义与修订

add 读取本页；其他入口核对定义时按需读取。准入见 [Ready Gate](task-rules.md#ready-gate)，本页不判定能否执行。

## 定义与编辑

[Task 模板](../assets/task.md) 保存协议、slug、title、revision、preparation、requirement、priority、dependencies、flow、execution_policy、cohestra_task、修订依据与 Gate 历史；不保存执行状态、候选、调用记录或所属 Run 指针。

- slug/title 为非空字符串，revision 为正整数，preparation 仅 draft/ready；priority 为 high/medium/low，缺省 medium。dependencies 为 slug 列表，execution_policy 只含布尔值 stop_queue_on_failure，缺省 false；flow 按 Task.protocol 和 [配置](flow-config.md) 校验，缺省 code。新建及编辑只接受协议 0.10；旧记录停止操作并提示先完成容器切换。
- dependencies 只能引用已存在任务；只展开可达定义图，以本次拟保存定义检查悬空、自依赖及环，失败拒绝修改。依赖是否完成由 ready 检查，不在 add 求执行状态。
- 编辑前按 [身份与归属](workflow.md#身份与归属) 核对 Run 来源；属于未完成 Run 或归属矛盾时拒绝修改。只改用户指定字段；cohestra_task 固定为 `.yuzio/cohestra/handoffs/<slug>/`，slug 与该绑定路径不可编辑或改绑。
- requirement、dependencies、规范化 flow 或 execution_policy 改变使 preparation 回 draft，使当前 Gate 失效并追加时间、来源与变更字段。只改 title/priority 不使 Gate 失效、不改变修订或执行结论；语义等价的 flow 规范化不算变更。
- 同名目录已有 Cohestra 交付时，按 [身份绑定](binding.md) 处理；遇旧协议时加载 [版本边界](compatibility.md)，未知或缺协议停止相关操作。

## 修订分代

初始 revision=1。影响 Gate 的编辑发生时：当前 revision 尚未进入任何 Run，则继续编辑该修订；已进入过 Run，则 revision 加一，revision_base 指向该 slug 的链尾 Run 和旧 revision，旧定义只引用 Run 快照，不复制可编辑历史。

同一尚未入 Run 的修订继续编辑时，保留最初 revision_base，累计 changed_fields、编辑原因与时间。requirement/flow 曾改变，即使改回也保留变更依据；后续按 [重启准入](revision-rules.md) 处理，add 不选择执行动作。恢复/修订授权消费只记在 Run。

# ready

读[公共流程的身份、状态、写入规则](workflow.md#身份与归属)、[Ready Gate](task-rules.md#ready-gate)、[Flow 配置](flow-config.md)和[准备入口](prepare.md)。普通路径必须按准备入口三批完成。先读取目标及归属，再核验依据和预检，最后写前复核、原子保存并回读。仅加载本任务命中的条件规则。

```text
$cadra ready
任务：<slug>
补充：<澄清或输入，可空>
```

仅接受协议 0.12；旧协议按 [版本边界](compatibility.md) 停止操作并提示先完成归档切换，本入口不迁移。

解析当前展示状态及 Run 归属，仅接受 draft/ready 且不属于未完成 Run 的任务。读取本 Task、依赖当前状态和必要输入，按唯一 Ready Gate 逐项核对；不修改需求定义；在既有范围／输入项计算 ready_scope，见 [小组调度](scheduling.md)。补充改变定义时先指向 add。

附件摘要匹配且确认对象和来源可核对时，使用 Task 已记录的决定核对 Gate。只有缺件、摘要不符或确认结论冲突才进一步查对应资料。不重做产品方案调查。按[预检](preflight.md)运行本任务需要的已知检查。每项对相同输入只执行一次。写前检查输入变化，变化时只重检受影响的项。分别列预计写范围和有明确依据的输入路径，独占任务也不递归给写入目录做指纹。

起点项遇到已有交付、Run 执行依据或定义修订时，按 [Flow](flow.md) 与 Task 规则加载适用的完整契约／重启准入。add 已记录的身份确认可沿用，执行材料缺口不能据此豁免。工程交付终点按 [Flow 对应章节](flow.md#工程交付终点)核对。

当前 need/design 唯一缺口是已有确认尚未正式交接时，读取并按 [准备交接补齐](preparation-handoff.md) 处理，再重核 Gate。仅此路径可调用 Cohestra 收敛当前人工阶段；其他失败仍只列缺口，不开展新需求、设计或工程阶段。

通过写 preparation=ready 和当前 revision 的 ready_scope；失败写 draft、清空 ready_scope 并列缺口。Gate 记录绑定 revision，保留旧历史，不重复追加同一修订的等价通过记录。回读后，无未完成 Run 时推荐 `$cadra run` 加范围；已有 running Run 时推荐 `$cadra append` 加明确 slug；其他情况按恢复边界说明，或继续准备任务。不建立 Run、不调用工程阶段。

普通 ready 不为 origin 非 null 的生成任务单独授权执行；其 Gate 由来源 Run 的内部 [收尾准备](closeout.md) 复用本页检查，执行前仍须全部满足。

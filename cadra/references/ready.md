# ready

读 [公共流程](workflow.md)、[Task 与 Ready Gate](task-rules.md)、[Flow](flow.md)。

```text
$cadra ready
任务：<slug>
补充：<澄清或输入，可空>
```

旧 0.6/0.7 Task 先按 [版本边界](compatibility.md) 由明确 add 升级，本入口不迁移。

解析当前展示状态及 Run 归属，仅接受 draft/ready 且不属于未完成 Run 的任务。读取本 Task、依赖当前状态和必要输入，按唯一 Ready Gate 逐项核对；不修改定义。补充改变定义时先指向 add。

起点项遇到已有交付、Run 执行依据或定义修订时，按 Task 规则加载完整契约/重启准入；add 已记录的身份确认可沿用，执行材料缺口不能据此豁免。

通过写 preparation=ready；失败写 draft 并列缺口。Gate 记录绑定 revision，保留旧历史，不重复追加同一修订的等价通过记录。回读后，无未完成 Run 时推荐 `$cadra run` 加范围；已有 running Run 时推荐 `$cadra append` 加明确 slug；其他情况按恢复边界说明，或继续准备任务。不建立 Run、不调用阶段。

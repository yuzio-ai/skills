# ready

读 [公共流程](workflow.md)、[Task 与 Ready Gate](task-rules.md)、[Flow](flow.md)。

```text
$cadra ready
任务：<slug>
补充：<澄清或输入，可空>
```

解析当前展示状态及 Run 归属，仅接受 draft/ready 且不属于未完成 Run 的任务。读取本 Task、依赖当前状态和必要输入，按唯一 Ready Gate 逐项核对；不修改定义。补充改变定义时先指向 add。

通过写 preparation=ready；失败写 draft 并列缺口。Gate 记录绑定 revision，保留旧历史，不重复追加同一修订的等价通过记录。回读后推荐 `$cadra run` 加范围，或继续准备其他任务。不建立 Run、不调用阶段。

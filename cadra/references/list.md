# list

只读查询。读 [公共流程](workflow.md) 与本页；仅在状态异常时查 [Run 规则](run-rules.md)。

```text
$cadra list
范围：<slug 列表或展示状态过滤；缺省全部>
```

容器不存在时报告“未初始化”与目标路径，不写文件。按状态解析读取 Task 定义与关联 Run，展示：slug/title、当前 revision 与展示状态、priority、依赖状态、flow、当前 Run 与 checkpoint 摘要。

队列视图直接取所选 Run 的 tasks 顺序、每项状态及结果；Run 一览列 running/completed/stopped/interrupted、总项数、结束项数和当前执行项。Task 按 slug 排序，Run 展示可按 run-id 倒序，但不能据此决定执行来源。旧 Run 的条目始终展示旧结果。

协议不支持、缺来源或结果矛盾时标 unknown 与具体缺口，不补写、不创建队列文件。根据实际缺口推荐 ready/run/resume/report 的准确调用。

# add

通过 $cadra add 调用；与 [公共流程](workflow.md) 一起执行。创建 Task，或编辑已有 Task。

## 调用

```text
$cadra add
任务：<title>
需求：<requirement 目标、范围与验收条件>
优先级：<high / medium / low，可空取 medium>
依赖：<task-slug 列表，可空>
流程：<flow preset 名或显式阶段序列，可空取 full>
执行策略：<stop_queue_on_failure: true/false，可空取 false>
```

编辑已有任务时在首行给出现有 slug，并只带需要修改的字段与本次补充。

## 职责与工作

1. 同 slug 不存在则创建，存在则按编辑处理。任何定义修改前按 [公共流程](workflow.md) 第 2.1 节核对 Run 归属：属于未完成 Run 或归属矛盾时拒绝编辑，不写文件，提示先 resume 收尾。slug 使用稳定英文短横线名称，不按工具、会话或执行者重复建任务。
2. 创建按 [任务骨架](../assets/task.md) 落盘 `.cadra/tasks/<task-slug>.md`，至少记录 title、slug、requirement、priority、dependencies、flow、execution policy，默认 `status: draft`；同时记录 `cohestra_task: .cohestra/handoffs/<task-slug>/` 引用（任务目录名必须等于 slug，见 [公共流程](workflow.md) 第 1 节）、Skill 发行版本与创建时间。`cohestra_task` 目录已存在且含正式交付时，在 Task 文件记录「绑定时已有交付（主题摘要）」并请用户明确确认对应关系，确认记录落盘；同名目录内容与 requirement 明显不对应时如实报告，不静默绑定（`run` 的收养核对见 [公共流程](workflow.md) 第 6.1 节）。
3. requirement 写清目标、范围与验收条件；内容不足以判断时如实记为缺口，不编造。验收条件是 Ready Gate 的检查对象，也是后续 Cohestra 阶段的输入。
4. priority 取 `high` / `medium` / `low`，缺省 `medium`；flow 缺省 `full`（preset 含义见 [公共流程](workflow.md) 第 5 节）；flow 为显式序列时按第 5 节校验——须为 `need → design → code → review → fix → review → validate` 的非空子序列（`review` 至多两次、第二次在 `fix` 之后，其余阶段各至多一次），即 `[fix, review, validate]` 与 preset `bugfix` 等价，`[review, fix, review]` 与 `[need, design, code, review, fix, review, validate]` 合法，此外的逆序、乱序或重复一律拒绝；execution policy 缺省 `stop_queue_on_failure: false`。
5. dependencies 必须指向已存在的 task-slug：悬空引用或形成环时拒绝创建/修改并列出问题，不建立指向不存在任务的依赖。
6. 编辑只按用户明确指示修改字段，记录来源、时间与影响范围；Gate 失效与身份绑定按公共流程第 2.1 节执行，保留旧 Gate 和执行历史，不覆盖旧 Run 的定义/结果快照。已结束任务的新修改不是旧候选的新验收结论。终态（completed/blocked/failed）任务改变 requirement、dependencies、flow 或 execution policy 时，按第 2.2 节记回 `draft` 并追加修订记录（`rev-<N>`、变更字段与原因、当前新定义快照、旧定义快照引用、原 Run 与原终态），由 `ready` 重新 Gate 后交 `run` 按第 6.3 节重启；draft/ready 上未消费修订的继续编辑累计字段、保留原终态来源，不按最后一次编辑替换整份修订；只改 title/priority 不回退、不改写旧结论。
7. 只写本 Task 文件；不执行任务、不建 Run、不入队、不动 `.cohestra`。

## 交付与停止

新增或更新 `tasks/<task-slug>.md`；骨架字段与落盘规则见 [公共流程](workflow.md)。

推荐下一步 `ready`，传递 slug 与需要补充的缺口。派发：`$cadra ready`，后附任务 slug 及本次补充。

---
name: cadra
description: 通过 add、ready 准备任务，list 查询，run 按既定顺序无人值守串行调用 Cohestra，resume 恢复中断，report 汇总结果。Task 保存定义与准入，Run 保存执行事实，资料位于 .yuzio/cadra。仅讨论流程不触发执行。
license: MIT
---

# Cadra

任务编排技能。任务准备、顺序、执行状态与恢复归 Cadra；单任务工程阶段和证据归 Cohestra。发行版与任务/Run 协议见 [release.json](release.json)。

## 入口与读取

`$cadra <入口>` 是技能调用意图，不是终端命令。先读 [公共流程](references/workflow.md)、本次入口和 release.json，再按入口条件加载规则；不要预读其他入口、全部任务或全部 Run 正文。

| 入口 | 职责 |
|---|---|
| [add](references/add.md) | 创建或编辑任务定义 |
| [ready](references/ready.md) | 检查 Ready Gate |
| [list](references/list.md) | 只读展示任务、队列和 Run |
| [run](references/run.md) | 建立并串行执行新 Run |
| [resume](references/resume.md) | 续跑或收尾未完成 Run |
| [report](references/report.md) | 生成指定 Run 的执行摘要 |

## 共同边界

- 固定目标项目绝对路径，读取适用项目规则及 [存储约定](references/storage.md)。未指定时使用当前任务项目；候选无法区分时澄清。技能来源使用本次选定的实际安装目录，不用源仓库规则代替旧安装副本。
- 只执行指定入口；run 内的串行推进属于该入口。只讨论规则时不创建资料、不启动执行。list 不写文件、不初始化。
- 写入口缺容器时先报告路径，再按 [容器模板](assets/project/) 最小建立 README、tasks、runs 与忽略规则；已有缺项仅补齐。接续指定任务或 Run 却找不到记录时报告缺口，不能用空初始化代替恢复。目标不明确、指向技能源仓库或不可安全写入时停止。
- Task 只保存定义与准入；Run 是执行状态的唯一来源。实际工程阶段通过 Cohestra 调用，Cadra 不写 `.yuzio/cohestra`，不复制 handoff 正文。正式执行总结按存储约定处理。
- 同一项目至多一个未完成 Run，同一时刻至多一个执行中的 Task。不做并行、DAG 调度、定时器、daemon 或 Agent 动态选择。
- 新版不迁移旧协议或双写。读取到不支持的项目协议时报告路径与版本，停止相关操作，不改旧记录；缺版本视为协议不明。技能升级不重写历史。

## 交付

写入口先落盘回读再汇报。回复交付物绝对路径、状态结论、必要待办与需人工介入事项，附准确的下一入口调用。推荐下一步不等于执行授权。安装、提交和发布不属于普通入口。

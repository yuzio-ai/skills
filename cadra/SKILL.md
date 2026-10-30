---
name: cadra
description: 通过 add、ready 准备任务，list 查询，run 默认从 code 开始，以独立 worker/reviewer 按固定两任务小组调用 Cohestra，append 运行中追加，resume 恢复中断，report 汇总结果。Task 保存定义与准入，Run 保存执行事实，资料位于 .yuzio/cadra。仅讨论流程不触发执行。
license: MIT
---

# Cadra

任务编排技能。任务准备、顺序、执行状态与恢复归 Cadra；单任务工程阶段和证据归 Cohestra。发行版与任务/Run 协议见 [release.json](release.json)。

## 入口与读取

`$cadra <入口>` 是技能调用意图，不是终端命令。先读本次入口和 release.json，再按入口指定范围加载 [公共流程](references/workflow.md) 及条件规则；指定章节时只读该节，不递归展开其中的其他入口链接。同次调用复用已读规则，不重复整文件加载；不要预读其他入口、全部任务或全部 Run 正文。

| 入口 | 职责 |
|---|---|
| [add](references/add.md) | 创建或编辑任务定义 |
| [ready](references/ready.md) | 检查 Ready Gate |
| [list](references/list.md) | 用包内脚本只读核对并汇总任务、队列和 Run |
| [run](references/run.md) | 建立并按固定两任务小组执行新 Run，收尾后自动生成报告 |
| [append](references/append.md) | 向 running Run 尾部原子追加已准入任务 |
| [resume](references/resume.md) | 续跑或收尾未完成 Run，收尾后自动生成报告 |
| [report](references/report.md) | 生成指定 Run 的执行摘要 |

## 共同边界

- 固定目标项目绝对路径，读取适用项目规则及 [存储约定](references/storage.md) 中本入口适用部分。未指定时使用当前任务项目；候选无法区分时澄清。技能来源使用本次选定的实际安装目录，不用源仓库规则代替旧安装副本。
- 只执行指定入口；run 内的分组推进，以及 run/resume 按 [report](references/report.md) 生成收尾报告，均属于该入口已授权范围。只讨论规则时不创建资料、不启动执行。list 不写文件、不初始化。
- 写入口缺容器时先报告路径，再按 [容器模板](assets/project/) 最小建立 README、tasks、runs 与忽略规则；已有缺项仅补齐。接续指定任务或 Run 却找不到记录时报告缺口，不能用空初始化代替恢复。目标不明确、指向技能源仓库或不可安全写入时停止。
- Task 只保存定义与准入；Run 是执行状态的唯一来源。实际工程阶段通过 Cohestra 调用，Cadra 不写 `.yuzio/cohestra`，不复制 handoff 正文。正式执行总结按存储约定处理。
- 同一项目至多一个未完成 Run、一个队列。每组固定一至两个 Task，每项最多一个阶段执行，全组最多两个阶段并行；各项使用独立 worker/reviewer，按需创建并在任务内复用。等待仍占组内名额，不补位；不做 DAG 调度、定时器或 daemon。默认 code；need/design 在外部人工参与准备。
- 写入、准入与执行入口仅接受协议 0.11；仅 list 可按原协议只读查询 0.10。缺版本、其他旧版与未知版停止相关操作；查询不迁移、不授权旧记录执行。本地切换先闭合原 Run、备份并归档，再重新准备待办，见 [版本边界](references/compatibility.md)。
- run/resume 的角色隔离与派发遵循 [任务执行者](references/agents.md)；run/resume 写入和 list 后续建议遵循 [执行者识别](references/executor.md)；建 Run 前完成 [执行预检](references/preflight.md)。执行中与活性未知均不得自动接管。

run/resume/append/ready 的并行准入、文件占用、阶段内等待和串行验证统一读取 [小组调度](references/scheduling.md)；确定性规则由包内 [scheduler.py](scripts/scheduler.py) 提供，仍由主 agent 派发与核验证据。

## 交付

写入口先落盘回读再汇报。回复交付物绝对路径、状态结论、必要待办与需人工介入事项，附准确的下一入口调用。推荐下一步不等于执行授权。安装、提交和发布不属于普通入口。

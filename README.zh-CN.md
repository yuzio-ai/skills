# YUZIO Skills

[English](README.md) · **中文**

集中维护可复用的智能体技能。安装方式交给通用工具，任务上下文保留在各项目中。

| Skill | 用途 | 入口 |
|---|---|---|
| cohestra | 初始化项目上下文，六阶段可从任意阶段起步；verify 核对偏差，report 只读汇总任务与遗留问题 | [SKILL.md](cohestra/SKILL.md) |
| cadra | 管理任务准备、队列、顺序、状态、恢复和执行报告，无人值守串行推进；单任务工程流程交由 Cohestra 阶段 | [SKILL.md](cadra/SKILL.md) |
| relatra | 汇总指定项目的 agent 成果、执行效率、返工与资源，生成日报至年报；Codex 优先，保留证据与未知 | [SKILL.md](relatra/SKILL.md) |

## cohestra

把一次协作拆成六个阶段 **need → design → code → review → fix → validate**，另有 `init` 建立项目容器、`verify` 在阶段之间核对偏差、`report` 只读汇总项目任务与遗留问题。六阶段是职责清单而非必经路线：任何阶段都可以是起点，终点由用户决定。

每个任务 README 的 YAML Front Matter 提供机器可读契约——任务状态、阶段结果、候选、受阻状态、下一阶段与是否允许继续——外部编排系统无需解析正文即可驱动单阶段调用；字段与枚举定义在公共流程第 7 节。Markdown 正文保持人类可读。Cohestra 一次调用只执行一个阶段、阶段结束即停止，不感知队列与调度：编排留在技能之外。

`report` 读取当前项目 `.cohestra/handoffs/` 下全部任务，包括已完成但仍有未关闭项的任务。展示任务与验收状态、遗留问题和状态异常，并链接来源；缺项保持未知。报告直接在对话中输出，不初始化项目、不写文件、不推进阶段，也不改变延期和关闭规则。

规则与阶段提示词保存在技能包内，本文件只做导读；规则真源是下列文件。

| 想了解 | 读 |
|---|---|
| 路由、执行规则、版本与来源 | [cohestra/SKILL.md](cohestra/SKILL.md) |
| 公共流程、术语、落盘与共享写入规则 | [references/workflow.md](cohestra/references/workflow.md) |
| 各阶段职责与可直接粘贴的调用片段 | [references/](cohestra/references/) |
| 只读任务总览、遗留问题与状态异常 | [references/report.md](cohestra/references/report.md) |
| 交付骨架与任务索引骨架 | [assets/](cohestra/assets/) |
| 安装、更新与工具边界 | [references/installation.md](cohestra/references/installation.md) |
| 维护者验收清单 | [tests/cohestra-scenarios.md](tests/cohestra-scenarios.md) |

## cadra

Cadra 是任务编排：管理任务准备、队列、顺序、状态、恢复和执行报告，在无人值守 Run 中按既定顺序串行推进。它不定义单任务内部的工程流程——那归 Cohestra；Cadra 只声明阶段序列（flow preset）并调用 Cohestra 阶段，且只依据 Cohestra 的机器可读状态驱动。

Task 走 **draft → ready → queued → running → completed / blocked / failed**；Run 串行执行（`parallelism = 1`），终态为 completed、stopped 或 interrupted，`resume` 从持久化状态恢复未完成 Run，不重复已完成任务与已完成阶段。建 Run 前先检查目标与 Cohestra 初始化前提（Git 工作区）。依赖链按层级逐 Run 推进：一层全部 completed 后，下一层才能通过 Ready Gate 入队，同一 Run 不含任务与其未完成依赖。

新任务没有既往交付或调用时，run 从 flow 首项启动。blocked/failed 通过新 run 的显式恢复选择重新执行，旧 Run 保留本轮结果。已到终态的任务修改定义会回到 draft、重新过 Ready Gate，旧定义与旧结论并列保留。requirement 或 flow 变更从新 flow 首项重启；仅 dependencies 或 execution policy 变更时，blocked/failed 重试核实后的待调用阶段，completed 不调用阶段、只作修订收尾。所属 Run 未完成时不允许编辑任务定义。无人值守推进受三项上限约束：逐阶段失败重试预算（2 次）、整改轮上限（3 轮）与任务调用预算（16 次），任一耗尽即记 failed 并列入需人工介入；无进展判定只在同阶段连续两次结构化状态全未变时成立，validate 的本阶段补证出口除外，由调用预算兜底。入队与出队按三步写入并带操作编号，中断留下部分写入时由 resume 按同一编号幂等补齐；旧版七列队列清单不迁移历史行，改为追加八列表块后继续使用。

| 想了解 | 读 |
|---|---|
| 路由、执行规则、边界、版本与来源 | [cadra/SKILL.md](cadra/SKILL.md) |
| Task/Run 状态机、队列顺序、Flow Preset、Cohestra 调用契约、unattended 规则 | [references/workflow.md](cadra/references/workflow.md) |
| 各入口职责（add / ready / list / run / resume / report） | [references/](cadra/references/) |
| 任务与 Run 骨架、`.cadra` 容器模板 | [assets/](cadra/assets/) |
| 维护者验收清单 | [tests/cadra-scenarios.md](tests/cadra-scenarios.md) |

## relatra

Relatra 面向个人复盘，按独立目标统计，不把聊天结束或文件数当成果。支持日报、周报、月报、季报、年报和自定义范围，默认上一完整自然周期、Asia/Shanghai。首次固定项目集合和报告目录，生成简报、版本化 Markdown、统计 JSON 与来源清单。

Codex 活动/归档日志只读采集，Cadra Run 与 Cohestra 交付物补充证据。agent 识别目标及完成证据，Python 3.9+ 标准库脚本计算去重统计；交付与验收分开，缺失时间/token 为未知。支持显式前期比较和用户更正，不执行原任务或创建定时服务。

```text
$relatra 周报
项目：<明确项目集合>
报告目录：<绝对路径；后续复用>

$relatra 月报
日期：2026-09-15

$relatra
起止：2026-10-01 至 2026-10-12
```

入口见 [relatra/SKILL.md](relatra/SKILL.md)，调用契约见 [数据与调用](relatra/references/data.md)，统计规则见 [统计口径](relatra/references/metrics.md)。离线测试：`python3 -B -m unittest discover -s tests -p 'test_relatra.py'`，不等于真实 agent 使用或云端历史覆盖验收。

计划覆盖、审查修复及原生技能校验见 [Relatra 验收记录](tests/relatra-scenarios.md)。隔离安装、完整调用及最低运行版本验证见 [推送前验收](tests/relatra-prepush.md)。

## 安装

在目标项目根目录执行，默认项目级安装：

```sh
npx skills add yuzio-ai/skills --skill cohestra
npx skills add yuzio-ai/skills --skill cadra
npx skills add yuzio-ai/skills --skill relatra
```

用户级安装加 `-g`；指定工具加 `-a <tool-a> <tool-b>`。源仓库尚未推送时，把来源换成本地绝对路径。安装不自动初始化项目；不想使用该 CLI 时，也可将完整 [cohestra](cohestra/)、[cadra](cadra/) 或 [relatra](relatra/) 目录放入工具支持的技能位置。

命令全集、更新方式，以及本地来源按名称更新会静默空转的排查，见 [安装说明](cohestra/references/installation.md)。

## 调用

以下是在智能体中输入的技能调用示例，不是终端命令；其他工具使用各自入口。阶段调用遇到目标项目没有 `.cohestra` 时会先提醒并执行一次最小初始化，再从需要的阶段开始，每次只读取对应说明。`report` 只报告容器缺失，不初始化。

```text
$cohestra init

$cohestra need
需求：<目标、范围、约束和参考>

$cohestra design
需求：<要探索的页面与目标>
参考：<截图、现状链接或设计规范>

$cohestra code
需求：<改动内容与范围>
参考：<相关文件、接口文档或截图>

$cohestra review
.cohestra/handoffs/<task-slug>/code-01.md

$cohestra fix
问题：<症状、预期行为、范围和参考>

$cohestra validate
.cohestra/handoffs/<task-slug>/review-01.md

$cohestra verify
被核对：.cohestra/handoffs/<task-slug>/design-01.md
上游依据：.cohestra/handoffs/<task-slug>/need-01.md

$cohestra report
```

handoff 也可替换为对应任务目录，由任务 README 定位有效输入。起步选择、停止规则与各阶段的对口 verify 约定见 [cohestra/SKILL.md](cohestra/SKILL.md) 与 [公共流程](cohestra/references/workflow.md)。

Cadra 调用管理这些阶段外围的任务队列；目标项目没有 `.cadra` 时会先提醒并执行一次最小初始化：

```text
$cadra add
任务：<title>
需求：<目标、范围与验收条件>

$cadra ready
任务：<task-slug>

$cadra list

$cadra run
范围：<task-slug 列表，或“全部 ready”>
恢复：<blocked/failed task-slug 列表；可空，有值时必须包含在显式范围中>

$cadra resume
Run：<run-id>

$cadra report
Run：<run-id>
```

参数标签保持中文，原因同上。任务与调度状态保存在 `.cadra`；单任务流程与工程证据保存在 `.cohestra`，两者只通过引用关联，不互相复制内容。状态机、Ready Gate、Cohestra 调用契约与 unattended 规则见 [cadra/references/workflow.md](cadra/references/workflow.md)。

## 维护

发行版 **0.10.0**，协作协议 **v0.8**；cadra 发行版 **0.5.0**，任务/Run 协议 **v0.5**；Relatra 版本 **0.1.0**，报告结构 **v1**。版本在 [cohestra/release.json](cohestra/release.json)、[cadra/release.json](cadra/release.json)、[relatra/release.json](relatra/release.json) 维护。Cohestra 协议变更时，Cadra 须发布兼容版本。Cohestra/Cadra 使用 Markdown、模板和元数据；Relatra 另需 Python 3.9+，无第三方运行依赖。均不提供自研安装器。本文件与英文 [README.md](README.md) 同步。

修改后按 [cohestra 验证场景](tests/cohestra-scenarios.md) 检查路由、文档链接、临时安装及交接流程，按 [cadra 验证场景](tests/cadra-scenarios.md) 检查任务编排规则。文件完整性检查和实际智能体调用分别报告；无独立智能体验证时，不把桌面推演写成实测。流程语义变化时另行更新协议版本。提交、推送和发布标签仍需明确授权。许可证：[MIT](LICENSE)。

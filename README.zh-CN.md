# YUZIO Skills

[English](README.md) · **中文**

集中维护可复用的智能体技能。安装方式交给通用工具，任务上下文保留在各项目中。

| Skill | 用途 | 入口 |
|---|---|---|
| cohestra | 初始化项目上下文，六阶段可从任意阶段起步；verify 核对偏差，report 只读汇总任务与遗留问题 | [SKILL.md](cohestra/SKILL.md) |
| cadra | 管理任务准备、队列、顺序、状态、恢复和执行报告，无人值守串行推进；单任务工程流程交由 Cohestra 阶段 | [SKILL.md](cadra/SKILL.md) |
| relatra | 汇总指定项目的 agent 成果、执行效率、返工与资源，生成日报至年报；Codex 优先，保留证据与未知 | [SKILL.md](relatra/SKILL.md) |
| vistra | 依据项目规范与可追溯证据，评审、探索、比较和交接移动端、桌面端及品牌视觉 | [SKILL.md](vistra/SKILL.md) |

## cohestra

把一次协作拆成六个阶段 **need → design → code → review → fix → validate**，另有 `init` 建立项目容器、`verify` 在阶段之间核对偏差、`report` 只读汇总项目任务与遗留问题。六阶段是职责清单而非必经路线：任何阶段都可以是起点，终点由用户决定。未指定阶段时按明确任务目标自动选择一个起点，不因缺少阶段名称而询问；一次调用仍只执行一个阶段。verify 仅按请求执行，发现具体偏差时才建议。

每个任务 README 的 YAML Front Matter 提供机器可读契约——任务状态、阶段结果、候选、受阻状态、下一阶段与是否允许继续——外部编排系统无需解析正文即可驱动单阶段调用；字段与枚举定义在公共流程第 7 节。Markdown 正文保持人类可读。Cohestra 一次调用只执行一个阶段、阶段结束即停止，不感知队列与调度：编排留在技能之外。

`report` 读取当前项目 `.yuzio/cohestra/handoffs/` 下全部任务，包括已完成但仍有未关闭项的任务。展示任务与验收状态、遗留问题和状态异常，并链接来源；缺项保持未知。报告直接在对话中输出，不初始化项目、不写文件、不推进阶段，也不改变延期和关闭规则。

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

Cadra 管理任务准备、执行顺序、状态、恢复和报告，在无人值守 Run 中串行调用 Cohestra。Task 保存定义修订、draft/ready 准备状态与 Ready Gate；Run 保存固定任务顺序、执行状态、checkpoint 和结果快照。list 根据 Run 来源链展示当前状态与队列，不创建独立队列文件。

flow 接受 preset 或非空阶段列表：首项是起点，所有项去重后是允许范围，中间排列不规定执行顺序。首次启动从起点进入，之后只消费 Cohestra 的合法 next；必做后续超出范围时受阻。任务只在依赖当前定义已 completed 后通过 Gate 并进入 Run，依赖链逐层推进。

同一项目至多一个未完成 Run，所属任务不能编辑。resume 续跑原 Run；blocked/failed 的显式恢复进入新 Run，不改旧结果。影响准入的定义修改回 draft；已入 Run 的定义分代，重新 Gate 后按变化字段选择重启或核对收尾。历史报告始终取原 Run 快照。

执行受逐阶段失败重试 2 次、整改 3 轮、总调用 16 次约束；不以摘要字段相同提前停止。调用意图、预算和结果写入同一个 Run 文件，采用临时文件检查、替换与回读；派发或交付无法确认时停止，不盲目重跑。仅支持当前任务/Run 协议，不自动迁移旧记录。

| 想了解 | 读 |
|---|---|
| 路由、执行规则、边界、版本与来源 | [cadra/SKILL.md](cadra/SKILL.md) |
| Task/Run 状态机、队列顺序、Flow Preset、Cohestra 调用契约、unattended 规则 | [references/workflow.md](cadra/references/workflow.md) |
| 各入口职责（add / ready / list / run / resume / report） | [references/](cadra/references/) |
| 任务与 Run 骨架、`.yuzio/cadra` 容器模板 | [assets/](cadra/assets/) |
| 维护者验收清单 | [tests/cadra-scenarios.md](tests/cadra-scenarios.md) |

## relatra

Relatra 面向个人复盘，按独立目标统计，不把聊天结束或文件数当成果。支持日报、周报、月报、季报、年报和自定义范围，默认上一完整自然周期、Asia/Shanghai。首次固定项目集合和报告目录，生成简报、版本化 Markdown、统计 JSON 与来源清单。

Codex 活动/归档日志只读采集，Cadra Run 与 Cohestra 交付物补充证据。agent 识别目标及完成证据，Python 3.9+ 标准库脚本计算去重统计；交付与验收分开，缺失时间/token 为未知。默认复用已审定账本，仅审阅新增活动、证据变化和遗留目标。普通模式生成简洁成果报告；明确要求效率、返工或人工介入分析时采用深度模式。支持显式前期比较；更正通过完整账本生成新版并记录原因，不再使用 patch 接口。不执行原任务或创建定时服务。

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

0.2.0/schema v2 的当前检查见 [精简验证](tests/relatra-simplification-validation.md)。旧格式保留可读，不自动迁移，复算需重新配置和采集。历史计划覆盖、审查修复及原生技能校验见 [Relatra 验收记录](tests/relatra-scenarios.md)。隔离安装、完整调用及最低运行版本验证见 [推送前验收](tests/relatra-prepush.md)。

## 本机资料与正式文档

`.yuzio/` 统一定义为当前工作区的本机执行资料。四个 skill 在写入时维护项目根 `.gitignore` 的 `/.yuzio/` 规则；安装和纯只读入口不修改项目，已有跟踪文件只报告，不自动取消跟踪。规则不覆盖嵌套测试夹具。

- 本机保存任务状态、阶段交接、队列、checkpoint、候选、快照和可复算账本。忽略不等于可丢弃，也不等于已有备份。
- skill 根据任务目标、交付用途和适用项目规范自动判断并整理必要的正式文档，无需另行要求。优先更新项目已有文档；无目录约定时用 `docs/`。必要结论与附件必须脱离 `.yuzio` 仍可读取；无正式交付需要的过程记录留在本机，纯只读入口及用户的明确输出限制保持不变。
- 在当前项目工作区执行和接续任务。中断恢复读取已有任务记录与 checkpoint，保留轮次和预算；资料缺失时报告缺口，不猜测执行状态。

各包独立携带约定：[Cohestra](cohestra/references/storage.md)、[Cadra](cadra/references/storage.md)、[Vistra](vistra/references/storage.md)、[Relatra](relatra/references/storage.md)。

## vistra

Vistra 支持 `review`、`explore`、`compare`、`handoff` 四种独立模式，按需加载移动端、桌面端和品牌静态视觉方法，配合项目级、用户级 UI/UX 规范使用。通过宿主图像能力直接生成或编辑图片，不制作 HTML、交互原型或本地渲染工具。推荐、方向选择、实现授权与验证分别记录。

Taste 方法已在包内定制，不是运行依赖。本机过程资料与探索产物默认写入 `.yuzio/vistra`，正式设计交付进入项目文档目录。Cohestra、Cadra、Relatra 的项目资料分别使用 `.yuzio/cohestra`、`.yuzio/cadra`、`.yuzio/relatra`；本机资料路径调整不改变技能安装路径，各技能协议以版本说明为准。当前路径约定不提供旧目录迁移、回退读取或双写逻辑；历史发布及验证记录保留各自的版本边界。Vistra 不修改生产代码或发布工程验收结论。

```text
$vistra review
对象：<页面、素材或源码>
范围：<评审问题>

$vistra explore
目标：<视觉方向与约束>

$vistra compare
候选：<准确产物与修订>

$vistra handoff
采用：<候选与选择来源>
```

当前工作区版本 **0.1.2**，正式报告与跨 Skill 产物契约保持 **1**。profile 格式升级为 **2**，只保留来源和默认值，不兼容 v1 的领域、目标和导入继承；旧配置不自动迁移，仅继续不依赖该配置的工作。普通答复按模式简短交付，正式报告保留完整追溯；配置细则和开发来源按需加载。入口见 [vistra/SKILL.md](vistra/SKILL.md)，设计依据见 [开发 Spec](docs/vistra-v0.1-development-spec.md)，当前检查见 [提交前验证](tests/workspace-review-validation.md)；[0.1.1 精简验证](tests/vistra-simplification-validation.md) 保留当时边界，[0.1.0 首版记录](tests/vistra-release-validation.md) 保留历史结果。本轮不安装或发布。离线检查：`python3 -B -m unittest discover -s tests -p 'test_vistra*.py'`。

## 安装

在目标项目根目录执行，默认项目级安装：

```sh
npx skills add yuzio-ai/skills --skill cohestra
npx skills add yuzio-ai/skills --skill cadra
npx skills add yuzio-ai/skills --skill relatra
npx skills add yuzio-ai/skills --skill vistra
```

用户级安装加 `-g`；指定工具加 `-a <tool-a> <tool-b>`。源仓库尚未推送时，把来源换成本地绝对路径。安装不自动初始化项目；不想使用该 CLI 时，也可将完整 [cohestra](cohestra/)、[cadra](cadra/)、[relatra](relatra/) 或 [vistra](vistra/) 目录放入工具支持的技能位置。

命令全集、更新方式，以及本地来源按名称更新会静默空转的排查，见 [安装说明](cohestra/references/installation.md)。

## 调用

以下是在智能体中输入的技能调用示例，不是终端命令；其他工具使用各自入口。阶段调用遇到目标项目没有 `.yuzio/cohestra` 时会先提醒并执行一次最小初始化，再从需要的阶段开始，每次只读取对应说明。`report` 只报告容器缺失，不初始化。

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
.yuzio/cohestra/handoffs/<task-slug>/code-01.md

$cohestra fix
问题：<症状、预期行为、范围和参考>

$cohestra validate
.yuzio/cohestra/handoffs/<task-slug>/review-01.md

$cohestra verify
被核对：.yuzio/cohestra/handoffs/<task-slug>/design-01.md
上游依据：.yuzio/cohestra/handoffs/<task-slug>/need-01.md

$cohestra report
```

handoff 也可替换为对应任务目录，由任务 README 定位有效输入。阶段自动选择、停止规则与按需 verify 约定见 [cohestra/SKILL.md](cohestra/SKILL.md) 与 [公共流程](cohestra/references/workflow.md)。

Cadra 调用管理这些阶段外围的任务队列；目标项目没有 `.yuzio/cadra` 时会先提醒并执行一次最小初始化：

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

参数标签保持中文，原因同上。任务与调度状态保存在 `.yuzio/cadra`；单任务流程与工程证据保存在 `.yuzio/cohestra`，两者只通过引用关联，不互相复制内容。状态机、Ready Gate、Cohestra 调用契约与 unattended 规则见 [cadra/references/workflow.md](cadra/references/workflow.md)。

## 维护

发行版 **0.10.1**，协作协议 **v0.8**；cadra 发行版 **0.6.0**，任务/Run 协议 **v0.6**；Relatra 版本 **0.2.0**，报告结构 **v2**。版本在 [cohestra/release.json](cohestra/release.json)、[cadra/release.json](cadra/release.json)、[relatra/release.json](relatra/release.json) 维护。Cohestra 协议变更时，Cadra 须发布兼容版本。Cohestra/Cadra 使用 Markdown、模板和元数据；Relatra 另需 Python 3.9+，无第三方运行依赖。均不提供自研安装器。本文件与英文 [README.md](README.md) 同步。

修改后按 [cohestra 验证场景](tests/cohestra-scenarios.md) 检查路由、文档链接、临时安装及交接流程，按 [cadra 验证场景](tests/cadra-scenarios.md) 检查任务编排规则。文件完整性检查和实际智能体调用分别报告；无独立智能体验证时，不把桌面推演写成实测。流程语义变化时另行更新协议版本。提交、推送和发布标签仍需明确授权。许可证：[MIT](LICENSE)。

# YUZIO Skills

[English](README.md) · **中文**

集中维护可复用的智能体技能。各技能目录是完整安装单元；仓库中的测试与维护文档不随技能运行。

## 技能概览

| Skill | 用途 | 入口 | 版本与协议 |
|---|---|---|---|
| cohestra | 初始化项目上下文，按需执行工程阶段、偏差核对和只读报告 | [SKILL.md](cohestra/SKILL.md) | [release.json](cohestra/release.json) |
| cadra | 准备任务、串行调用 Cohestra，并管理执行状态与恢复 | [SKILL.md](cadra/SKILL.md) | [release.json](cadra/release.json) |
| relatra | 汇总指定项目的 agent 成果、遗留与已观测资源 | [SKILL.md](relatra/SKILL.md) | [release.json](relatra/release.json) |
| vistra | 评审、探索、比较和交接移动端、桌面端及品牌静态视觉 | [SKILL.md](vistra/SKILL.md) | [release.json](vistra/release.json) |

执行规则以各包内文档为准。Cohestra 每次调用执行一个阶段；Cadra 的工程阶段执行需要可用的 Cohestra。Relatra 需要 Python 3.9+，仅使用标准库；Vistra 生成或编辑图片需要宿主提供图像能力。

## 安装

在目标项目根目录执行所需技能的安装命令：

```sh
npx skills add yuzio-ai/skills --skill cohestra
npx skills add yuzio-ai/skills --skill cadra
npx skills add yuzio-ai/skills --skill relatra
npx skills add yuzio-ai/skills --skill vistra
```

默认项目级安装；用户级加 `-g`，指定工具加 `-a <tool-a> <tool-b>`。本地未发布内容可使用源仓库绝对路径。也可把完整技能目录复制到宿主支持的位置，包含包内引用、模板、脚本及隐藏文件。安装不自动初始化业务项目。

安装、更新与排查见 [安装说明](cohestra/references/installation.md)。

## 调用

安装后，在智能体对话中输入 `$技能名 入口`，再补充项目、对象、目标和必要约束。下文示例都是**对话输入，不是终端命令**；`<…>` 替换为实际内容，其他宿主使用各自的技能调用方式。

未明确项目时，Cohestra 和 Cadra 默认使用当前任务项目；Relatra 需要确定项目集合，Vistra 需要明确设计对象。只讨论技能规则不会启动执行。

### Cohestra

用于推进单个工程任务。可以从任意阶段起步，**每次调用只执行一个阶段**；未指定入口时会根据目标选择。

| 入口 | 用法 |
|---|---|
| `init` | 初始化或复用项目协作上下文，不执行任务 |
| `need` | 澄清需求、范围和验收条件 |
| `design` | 制定方案、执行计划和验证方法 |
| `code` | 按有效设计实施 |
| `review` | 审查指定候选，列出问题 |
| `fix` | 裁决并修复审查问题 |
| `validate` | 补足验证证据，判断是否达到验收条件 |
| `verify` | 核对某阶段产出与上游依据之间的偏差 |
| `report` | 只读汇总当前项目任务、遗留问题和状态异常 |

```text
$cohestra design
项目：<项目绝对路径>
需求：为搜索增加历史记录，最多保存 20 条，支持单条删除和清空。
```

继续同一任务时，可附上前一阶段的交付文件或任务目录。阶段调用缺少上下文容器时会提醒并最小初始化；`report` 不初始化、不写文件。执行资料保存在项目 `.yuzio/cohestra`，必要正式文档按项目规范整理。

详细规则：[Cohestra](cohestra/SKILL.md)。

### Cadra

用于任务准备、串行执行和中断恢复。实际工程阶段由 Cohestra 完成，执行前必须有可用的 Cohestra。

| 入口 | 用法 |
|---|---|
| `add` | 新建或编辑任务定义，指定需求、优先级、依赖和流程 |
| `ready` | 检查目标、范围、验收、输入、依赖等是否满足执行条件 |
| `list` | 只读查看任务、队列和执行批次 |
| `run` | 创建执行批次，串行执行指定任务；默认选择全部 ready 任务 |
| `resume` | 恢复或收尾尚未完成的执行批次 |
| `report` | 为指定执行批次生成摘要文件，并登记报告链接 |

依次发送以下调用；任务标识使用 `add` 返回的 slug：

```text
$cadra add
项目：<项目绝对路径>
任务：搜索历史
需求：最多保存 20 条搜索记录，支持单条删除和清空；重启后仍保留。
流程：feature

$cadra ready
任务：<slug>

$cadra run
范围：<slug>
```

常用流程：`full` 从需求起步，`feature` 从设计起步，`small-change` 从开发起步，`bugfix` 从修复起步，`review-only` 仅审查。后续阶段按实际交付结果推进。

`add`、`ready` 不启动工程执行。同一项目最多有一个未完成的执行批次；依赖任务必须已完成才能准入。中断续跑用 `resume`；已结束批次中的失败任务，需明确恢复范围后建立新 `run`。任务定义和执行记录保存在 `.yuzio/cadra`。

详细规则：[Cadra](cadra/SKILL.md)。

### Relatra

用于个人项目复盘。支持日报、周报、月报、季报、年报和自定义起止日期。

```text
$relatra 周报
项目：<项目绝对路径，可明确列出多个项目>
报告目录：<报告目录绝对路径>
```

默认统计上一完整自然周期，使用中文和上海时区，周报为周一至周日。要看本期进展，明确写“本周截至现在”；要分析返工、人工介入或等待，直接补充这些要求。

普通模式汇总成果、状态、遗留及可观测时间和 token；效率诊断使用深度模式。单项目默认目录为 `<项目>/.yuzio/relatra`，跨项目需明确统一报告目录。可更正历史报告并保留旧版。

需要 Python 3.9+。只汇总证据，不执行原任务或改变其状态；缺失数据不会按零统计，也不自动定时运行。

详细规则：[Relatra](relatra/SKILL.md)。

### Vistra

用于移动端、桌面端和品牌的静态视觉工作。提供截图、素材、源码或准确候选，并说明本轮可改范围。

| 入口 | 用法 |
|---|---|
| `review` | 检查已有页面或素材，给出问题和建议 |
| `explore` | 生成或编辑图片，探索布局、配色、Logo 等方向 |
| `compare` | 比较已有方案，说明取舍 |
| `handoff` | 记录选定方案和采用范围，整理开发交接 |

```text
$vistra explore
对象：<页面截图或设计素材>
目标：探索 3 个视觉方向，突出主要操作。
约束：保留文案、功能和导航，仅调整布局、层级和配色。
```

多方向探索默认 3 个方向、最多一轮针对性修订，可明确调整预算。需要生成或编辑图片时，宿主必须提供图像能力。

在已有候选上下文中，“就用 B”会记录选择并进入交接；需要只记录选择时应明确说明。交接缺少关键决定或素材时会保留草案状态。Vistra 不直接修改生产代码，不制作 HTML 或交互原型，图片也不代表工程验收通过。

详细规则：[Vistra](vistra/SKILL.md)。

### 配合使用

单个工程任务使用 Cohestra；多个准备好的任务交给 Cadra 串行调度 Cohestra。需要视觉探索时使用 Vistra，确定方案并交接后，再明确要求工程实现。阶段性复盘使用 Relatra 汇总已有记录。

查看状态时：`cohestra report` 看项目任务总览，`cadra report` 生成某个执行批次的摘要，`relatra` 生成指定周期的成果与资源报告。

#### 完整示例

以“给现有搜索页增加历史记录”为例：Cohestra 明确需求 → Vistra 探索并交接 → Cadra 调度 Cohestra 实施和验证 → Relatra 复盘。

在同一个目标项目中依次发送下列调用，每次等待交付后再继续。把路径、候选版本、slug 和 run-id 替换为实际返回值。开始前需安装这 4 个技能，项目已是 Git 工作区，并具备图像能力和所需验证环境。

1. 先明确需求，解决影响实现的产品问题。

   ```text
   $cohestra need
   项目：<项目绝对路径>
   需求：为现有搜索页增加历史记录，最多 20 条，支持单条删除和清空，重启后仍保留。
   范围：不改搜索算法和其他页面；明确交互规则与验收条件。
   ```

2. 用需求交付和现有页面探索视觉方向。

   ```text
   $vistra explore
   项目：<同一项目绝对路径>
   依据：<need 返回的需求交付文件绝对路径>
   对象：<现有搜索页截图或源码路径>
   目标：探索 3 个搜索历史区域的视觉方向。
   约束：沿用品牌、文案和导航，不增加需求以外的功能。
   ```

3. 查看候选并作出选择后，整理正式交接；关键决定或素材未齐时先补齐。

   ```text
   $vistra handoff
   项目：<同一项目绝对路径>
   选择：<已查看并确定采用的候选及准确版本>
   要求：保存正式交接，明确采用范围、组件映射和未决项，供后续工程设计使用。
   ```

4. 把需求和视觉交接作为输入，建立工程任务。`feature` 从工程设计起步，不重复需求阶段；若接续同一 Cohestra 任务，明确给出其任务目录并确认绑定。

   ```text
   $cadra add
   项目：<同一项目绝对路径>
   任务：搜索历史功能
   需求：实现已确认的搜索历史需求和视觉方案；不改搜索算法和其他页面。
   输入：<需求交付文件绝对路径>、<Vistra 正式交接文件绝对路径>
   验收：最多 20 条，单条删除与清空有效，重启后保留；按需求交付中的完整验收条件验证。
   流程：feature
   ```

5. 分别发送 `ready`、`run`、`report`。仅在准入通过后执行 `run`；Cadra 按实际结果调用 Cohestra 的设计、开发、审查、修复和验收阶段。运行中断时先用 `resume` 恢复。

   ```text
   $cadra ready
   任务：<add 返回的 slug>

   $cadra run
   范围：<同一 slug>

   $cadra report
   Run：<run 返回的 run-id>
   ```

6. 最后复盘本周截至当前的实际成果。显式提供视觉交接引用，避免假设 Relatra 会自动采集 Vistra 目录；未完成和未验收事项仍保留为遗留。

   ```text
   $relatra 周报
   项目：<同一项目绝对路径>
   周期：本周截至现在
   补充证据：<Vistra 正式交接文件绝对路径>
   关注：搜索历史功能的实际交付、验收状态、遗留问题和可观测资源。
   ```

| 详细说明 | 入口 |
|---|---|
| Cohestra 阶段、交接与契约 | [公共流程](cohestra/references/workflow.md) |
| Cadra 准备、执行与恢复 | [公共流程](cadra/references/workflow.md) |
| Relatra 数据调用与统计口径 | [数据与调用](relatra/references/data.md) · [统计口径](relatra/references/metrics.md) |
| Vistra 模式、项目规范与配置 | [模式](vistra/references/modes) · [项目适配](vistra/references/project-adapter.md) |

## 本机资料与正式文档

`.yuzio/` 保存当前工作区的本机执行资料，根 `.gitignore` 使用 `/.yuzio/` 排除它。忽略不等于可丢弃或已有备份。需要共享的正式结论和附件进入项目文档目录，并可脱离本机资料读取。

各包独立携带具体约定：[Cohestra](cohestra/references/storage.md) · [Cadra](cadra/references/storage.md) · [Relatra](relatra/references/storage.md) · [Vistra](vistra/references/storage.md)。

## 维护与检查

仓库根目录运行全部自动化检查：

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

测试布局、单技能命令与验收场景见 [测试说明](tests/README.md)。检查覆盖包元数据、文档链接、隔离副本资源完整性及离线回归；实际安装器行为、智能体执行和视觉验收单独验证。

版本与协议在各包 `release.json` 维护，更新条件、兼容性和提交前检查见 [维护与版本规则](AGENTS.md#版本管理)。保持中英文 README 同步。提交、推送和发布标签需明确授权。许可证：[MIT](LICENSE)。

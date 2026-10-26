---
name: cohestra
description: 通过 init 初始化项目协作上下文，按任务目标自动选择 need、design、code、review、fix、validate 阶段，也可显式指定，按 verify 做阶段间偏差核对，或按 report 只读汇总项目任务状态与遗留问题。六阶段可从任意阶段起步；阶段缺 .yuzio/cohestra 时先提醒并初始化，report 不初始化或写入；任务 README Front Matter 提供机器可读契约；仅讨论流程不触发执行。
license: MIT
---

# Cohestra

一个技能，按阶段读取说明。技能包保存协作规则和提示词；项目 `.yuzio/cohestra` 只保存本机入口、任务执行交付和复盘；根据任务目标、交付用途和项目规范自动判断并整理必要正式文档到项目文档目录，无需另行要求；纯只读入口和用户限定的输出范围保持不变。技能版本见 [release.json](release.json)，协作协议为 v0.8。任务 README 的 Front Matter 保存当前控制状态，正文补充上下文和历史；术语、字段与枚举见[公共流程](references/workflow.md)。
 
## 路由

`$cohestra <入口>` 表示技能调用意图，不是终端命令；其他工具采用其技能调用写法。阶段调用后附原始需求、handoff 文件或任务目录，以及本次补充；未附 handoff 与任务目录时按[公共流程](references/workflow.md)第 1 节的自动衔接规则取用。`report` 默认汇总当前项目全部任务，不选择单个上游交付。

| 入口 | 按需读取 | 职责 |
|---|---|---|
| init | [init](references/init.md) | 建立或复用项目上下文容器，不执行任务 |
| need | [need](references/need.md) | 澄清需求（含提问）、范围与验收 |
| design | [design](references/design.md) | 设计方案、执行计划和验证方法 |
| code | [code](references/code.md) | 按有效设计实施并交付候选 |
| review | [review](references/review.md) | 审查固定候选，输出 findings |
| fix | [fix](references/fix.md) | 裁决并修复审查问题 |
| validate | [validate](references/validate.md) | 补足证据，判断验收状态 |
| verify | [verify](references/verify.md) | 核对某阶段产出与其上游依据的偏差 |
| report | [report](references/report.md) | 只读展示项目任务总览、遗留问题与状态异常，不落盘 |

## 执行边界与读取顺序

1. 固定目标项目绝对路径，读取适用项目规则及[存储约定](references/storage.md)。默认当前任务项目，目标无法唯一确定时澄清；不因技能安装位置改变目标。
2. 显式入口优先；未指定时按[公共流程第 2 节](references/workflow.md#2-起步位置)选择最直接的阶段并简短说明。六阶段可从任意阶段起步，一次调用只执行选定阶段，终点由用户决定；只讨论流程不触发执行。实质歧义、入口冲突或未知名称才澄清。validate 补验收证据，verify 核对偏差，不可混用。
3. `init` 只读取初始化说明、发行版本和必要模板。`report` 只读报告说明、发行版本、任务索引及必要问题来源，字段有疑问再查公共流程第 7 节；不初始化、不写文件、不推进阶段。其余入口读取一次公共流程、本阶段说明与发行版本，再读必要任务输入；缺容器时按公共流程第 2 节最小初始化，接续任务缺资料不能用空初始化代替恢复。
4. 写交付时读取对应骨架；正式阶段和 verify 准备更新索引时必须读取[索引发布与恢复](references/publication.md)。先确认发布前校验成功，再用后续工具调用发布；校验失败不得继续。init、report 不读发布细则。
5. 既有项目规范、有效决定和用户授权继续有效；授权、候选、证据、复审、历史和停止规则统一见公共流程。阶段交付后停止，不自动提交、发布或启动其他智能体；多任务调度由外部系统负责。
6. `verify` 按请求执行，仅在发现具体偏差时建议；不固定提议、不记录未执行核对，不替代 review、复审或 validate。调用方声明 `execution_mode: unattended` 时执行公共流程第 7.4 节，不新增授权或降低门禁，无法合法继续时受阻并停止。
7. Cadra 派发的阶段按[编排派发](references/workflow.md#编排派发)核对实际角色、候选和来源；本阶段执行者发布 Cohestra 交付与索引，不写 Cadra Run，也不自行启动下一阶段或其他 agent。单独调用 Cohestra 不因此强制委派。

## 来源与版本

- 从本次实际加载的技能目录读取规则和模板，不从工作目录猜测技能位置；也不把提示词复制回项目 `.yuzio/cohestra/prompts`。
- 每轮交付记录实际 Skill 发行版本和协议版本，保留历史交付。升级技能不改写任务决定、验收要求或历史结果。
- 同名技能存在多份时使用明确选择的入口；无法确定来源时报告位置并澄清，不假设用户级或项目级一定优先。
- 用户级升级影响后续调用。项目需要独立固定版本时使用项目级安装并随 Git 管理；不要从初始化记录推断当前实际技能版本。
- 不提供项目模板同步的 `update` 入口。用户提出旧 `$cohestra update` 时说明改由技能管理器升级；仅在安装、升级或迁移问题中读取 [安装说明](references/installation.md)，不自动运行更新命令。

## 交付

阶段交付及最终回复按公共流程第 5 节执行；同步失败按发布细则报告。`report` 直接在对话中输出报告与来源链接后停止。

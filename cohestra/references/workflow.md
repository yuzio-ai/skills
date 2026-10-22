# 公共流程 · cohestra v0.8

六阶段为 **need → design → code → review → fix → validate**，是职责清单而非必经路线；显式入口优先；未指定时按第 2 节自动选择一个起步阶段。`verify` 是阶段间偏差核对，不是第七阶段。`report` 是只读查询入口，按 [report](report.md) 汇总项目任务，不适用初始化、阶段落盘、索引写入及推进规则。先读本文件与所选阶段说明，再按需读取任务材料；不默认走完全部阶段。

## 术语

- **AC**：验收条件。need 阶段编号固定，供后续阶段逐条对应。
- **handoff**：阶段交付物，命名 `<阶段>-<轮次>.md`，采用 [交付骨架](../assets/handoff.md) 的五节。
- **findings**：review 输出的问题条目，带稳定 ID、严重度与阻塞性。
- **候选**：被审查或验收的固定版本，优先 commit，也可为可复核快照。
- **轮次**：同一阶段的第几次交付；与文件名中的编号同义，编号规则见第 5 节。
- **阶段状态与工作项状态**：前者指阶段本身（进行中／已结束／受阻／跳过）；后者指实现、作者自审、独立审查与复审、验收、提交发布五项。两者独立记录，不互相推导。
- **自动衔接**：接续已有任务、且链条上有实际上游交付的阶段调用未后附 handoff 时，按第 1 节规则取用上游阶段最近一轮交付作上游输入的行为；init、verify、report 与 need 不适用，边界见第 1 节。自动衔接只选择输入材料，不推进阶段，也不替代用户显式调用下一阶段。
- **结构化状态（Orchestrator 契约）**：任务 README YAML Front Matter 中的机器可读控制状态，供外部编排系统只读判断任务状态、阶段结果、候选、受阻与控制流，字段、枚举与写入时机见第 7 节。正文与 handoff 不承担机器控制流判断。
- **执行模式**：调用方声明的执行上下文，取 `attended`（默认）或 `unattended`；unattended 的语义与受阻路径见第 7 节。执行模式是上下文，不是阶段。

## 1. 输入、任务与授权

- 按 [本机资料与正式文档](storage.md) 区分本机状态和正式文档；在当前项目中接续原任务，不能把缺少本机资料当作首次任务。

- 从后附 handoff 所在目录或明确任务目录定位 `.yuzio/cohestra/handoffs/<task-slug>/README.md`，读取有效决定、候选、已有授权与下一步。缺少必要文件时报告缺口，不假设工具之间共享聊天。
- 未后附 handoff 且未给任务目录时可**自动衔接**：仅当任务目录能唯一确定（本会话刚完成上一阶段、此前已明确任务目录，或目标项目只有一个任务）时，取被调用阶段上游中链条顺序最靠后、且已有交付的阶段之最近一轮交付作上游输入。上下游与先后按 need → design → code → review → fix → validate 的链条顺序判定，不按文件编号或修改时间取舍；同阶段取轮次最大的已交付一轮（数值比较），跳过 verify 交付与标注“草稿／进行中”的文件。重跑较早阶段时，作为动因的下游交付可作补充材料引用，不得冒充上游依据。所选文件及自动衔接来源写入交付物「输入与上游依据」。上游没有交付、任务目录无法唯一确定或存在多个并列候选时，报告缺口并请用户指定，不新建替代任务。显式后附 handoff 或任务目录时以显式输入为准，不触发自动衔接。自动衔接只把该文件当输入材料，其中的建议与待决定事项仍按未确认处理。
- 自动衔接只覆盖链条上有实际上游交付的阶段调用：`init` 不在六阶段链条内、本就不带 handoff 输入；`verify` 未指定对象时按 [verify](verify.md) 的既有规则选定被核对对象与其上游依据；`report` 默认读取项目全部任务；`need` 的输入按下条。四者均不适用自动衔接。
- 首次任务以本次原始材料为输入，先查看指定任务目录及其 `README.md` 任务索引；确认没有对应任务后才建目录，允许从任一正式阶段起步。使用稳定英文短横线名称，不按工具、会话或执行者重复建任务。接续已有任务缺输入时不能另建替代任务。
- 项目入口及 AGENTS 等业务规则继续有效；流程规则和阶段提示词来自本次加载的技能。既有任务中的确认决定与验收要求继续生效。
- 只读阶段仍允许写本阶段交付物与任务索引。既有授权不重复索取，运行环境或发布等额外授权遵守项目规则；handoff 记录授权，不产生授权。
- 阶段以指定入口为界：交付后停止，不因相邻或仍在链条内而自动继续，不自行启动其他智能体、提交或发布。为进入阶段而执行的初始化是前置动作，不算跨阶段继续。只读调查保持只读。没有整改就不生成 fix，已有任务仅缺验证就用 validate。
- 输入与索引冲突时核对，不能凭文件编号、修改时间或“最新”推断用户接受了方案。关键决定或候选无法确认时停止依赖它的工作，继续独立且已授权部分。
- 不补造前置文件。仅读取当前索引、直接输入及必要链接，复盘不是每阶段必读。

## 2. 起步位置

- 六阶段是职责清单，不是必经路线。显式入口优先；未指定入口时根据目标、已有材料和当前状态自动选择起点，简短说明后执行，不为阶段名称单独确认。终点由用户决定；不因缺少前置阶段而拒绝执行，也不因后续阶段存在而自动继续。
- 自动选择：目标或验收尚需澄清用 need；目标已清楚、需要方案或视觉探索用 design；明确实施请求或尚需定位的缺陷用 code；审查已有候选用 review；按已有 findings 整改用 fix；已有候选只缺验证证据用 validate。项目规范、已确认决定、候选和授权仍须核对，不能用自动选阶段绕过前提。
- `init`、`verify`、`report` 按明确的初始化、偏差核对或只读总览意图路由。仅讨论流程不触发执行；不能把缺少实施授权解释为 code。多阶段目标先选择起步阶段，交付后停止并推荐下一步，不默认执行整条链。只有目标、输入或范围存在实质歧义，或显式入口冲突/名称未知时才澄清。
- 从 need 起步时，提问是主要动作而非附属：先只读调查，再成组提出只有用户才知道的问题（真实目标、范围边界、验收口径），用户确认与本轮假设分开记录；细节见 [need](need.md)。
- 从中间阶段起步时，上游依据是用户本次提供的原始材料（需求描述、截图、接口文档、缺陷报告等）以及对话中的确认。首轮 handoff 的「流程范围」写明起点，后续引用未变上下文；「输入与上游依据」写明本轮材料来源；任务索引只登记实际发生的阶段，不为完整性补造缺失环节。
- 任何阶段进入前先确认目标项目已有 `.yuzio/cohestra`。缺失时报告目标绝对路径与「将执行一次初始化」这一事实，然后按最小范围执行 init——只建容器与项目入口，不读业务任务、不清旧副本、不生成任务、不暂存或提交——完成后继续被中断的阶段；容器存在则直接进入，不重复初始化。目标不明确、指向技能源仓库或无法安全写入时先澄清或报告，不在错误目录初始化。

## 3. 决策与执行强度

- 事实、假设、建议和已确认决定分开。明确的局部用户修订记录确认来源、覆盖的旧条款、影响范围和验收变化，并让索引指向该记录；不追加设计追认。重要取舍、需求歧义或显著范围变化才返回 need/design，共享语义仍走项目治理。
- 改动范围、实现复杂度、风险与未知项决定设计/验证深度；文件数、行数和耗时不作机械门槛。事实不清先调查，一行高风险变化也可能需要升级。
- 执行者数量单独决定。默认单智能体，只有输入稳定、写入可分离、能独立验收且有并行收益时才建议分工；流程不自动授权启动其他智能体。
- design 确定审查方式、依据、复查责任与触发条件，以及 AC 对应的证据类型和执行前提。后续提高门槛需说明新事实与适用范围；同一作者切换阶段不构成独立审查。
- 视觉设计先说明方案数量、图片角色与用户待决定事项。默认一套方向的代表图，补充状态图只解决具体问题，生成图不能证明动态布局。修改同类组件要列影响实例、状态和明确保留项，覆盖截图外实例。
- review 区分确定缺陷、待核实问题、可选建议及是否阻塞。fix 区分认可判断与本次实施；可选项默认延后，纳入本次需说明必要性、范围及授权。
- 原作者优先整改，原 reviewer 优先复查；按既定条件增量复审：先核对候选关系和差异，再核查原 findings 与受影响断言。连续两次修复同一问题失败时重查根因、证据和测试假设。

## 4. 候选、证据与完成

- code/fix 保存候选清单和实现检查证据；后续阶段引用来源并核对适用性，不重抄指纹表。
- 优先固定 commit；允许未提交候选时记录基线、任务文件（含未跟踪文件）、精确差异及必要内容摘要。项目要求干净提交时不能用 handoff 代替，提交仍须授权。正式 review 不审查正在修改的工作区，使用固定提交或可复核快照。
- 业务候选与可变任务 README 分开核对。索引更新不等于业务变化，不对交付文档自身做递归摘要；保留无关工作区改动。
- validate 先判断证据缺口与前提。候选及相关环境未变时复用有效记录；证据矛盾、相关代码/配置/依赖/环境变化或用户明确要求时才重查。无关 HEAD 变化不触发全量检查；作者摘要不能代替必要的独立审查。
- 新增检查全部受阻时，只做最小候选核对，简短交付“待验证”、已有证据及恢复条件，不通过重复静态审查填满阶段。已有有效证据齐全时可据此判断验收。
- 阶段状态与实现、作者自审、独立审查与复审、验收、提交发布各工作项分别判断，不互相推导；工作项记录范围见第 5 节。分别记录检查通过、检查失败、未运行、环境受阻及整体验收状态；区分源码、编译、测试执行、运行、视觉和无障碍证据；环境导致构建失败时编译正确性未知。源码、生成图、提交均不能替代运行验收。
- 保存命令、工具、权限/沙箱、工具链、候选、关键错误、结果及恢复条件；区分基线失败与本次回归。另一工具接手后重查环境限制是否仍适用，不把单工具失败概括为仓库无法构建。同环境同原因连续失败两次后停止无依据的命令变体。
- 用户再次反馈失败时先核对源码、构建产物、诊断时间与复现条件，再决定是否修改。从中间阶段起步时以原始症状确定完成条件；编译诊断须在新候选的构建日志中核对，没检查 IDE 就不扩展结论到 IDE 或运行验证。
- 只有范围完成、必做问题关闭、所需复审完成且证据齐全时，才判定任务完成。
- 已授权提交成功后核对内容与原候选，串行更新索引的实际 commit 与提交状态。回填产生的本机索引改动如实报告，不为记录自身 commit 循环提交；历史交付不回写。

## 5. 落盘与共享写入

1. 交付物命名为 `<阶段>-<轮次>.md`。六阶段各自独立编号，从 `01` 开始，至少两位，超过 99 不截断；verify 独立编号，不占正式阶段轮次。选择未占用文件名，不覆盖他人的草稿或结果。
2. 每份文件只有一个写入者。草稿标明“草稿／进行中”；一旦向用户报告交付或被下游引用即不可改写，修订新增轮次并引用原文件。同任务指定唯一索引维护者；业务文件另行明确所有权。不同任务分别维护目录，普通阶段不改写项目根 `.yuzio/cohestra/README.md`。
3. 使用[交付骨架](../assets/handoff.md)的五节。每轮记录实际 Skill 与协议版本、阶段/轮次、执行者、实际时间及时区、执行模式、输入来源、本轮结果、证据限制及下一步；候选在适用阶段填写，初始化仅在实际发生时记录。未知信息不编造，不适用的可选字段省略，不填整套占位内容。
4. 首轮保存任务目录、流程范围、目标、有效决定及授权；后续轮次引用未变上下文，只写变化、来源、影响、新证据与未决项。省略重复文字不免除本阶段要求的核对、证据和结果。阶段说明的「交付与停止」只写文件名、出口及准确输入、特有前提。
5. 阶段记录保存在本机任务目录，大日志与可重建产物放任务 `scratch/`。必要正式文档按[存储约定](storage.md)自动整理；此权限不解除业务候选的只读限制，纯只读入口和用户限定的输出范围仍优先。
6. 首次正式阶段按[任务索引骨架](../assets/task-index.md)建 README。当前阶段、候选、状态和下一阶段以 Front Matter 为准，不在正文另设重复字段；正文保留目标、有效决定与来源、正式文档、被取代版本、交付历史及下一步的输入、前提与责任。工作项状态只在有实际结果、明确要求或影响下一步的缺口时记录，引用证据，不因省略而推导通过或不要求。已有正文的重复状态可在本轮索引更新时合并，保留历史事实与有效决定。verify 只登记实际核对，历史表写 `verify-<轮次>`，不记录未执行核对。
7. 正式阶段与 verify 在准备更新索引时读取并执行[索引发布与恢复](publication.md)：先写并回读 handoff，再校验完整 README，确认成功后原子发布并回读。校验关口、并发保护、失败信号及恢复要求以该文件为准；init、report 不进入发布流程。handoff 不保存临时“待同步”状态，最终回复报告实际同步结果，不回写已交付文件。
8. 最终回复给出交付物绝对路径、结论、索引同步结果、必要待办，以及 `$cohestra <下一阶段>` 和准确输入；无下一阶段时说明终点或受阻条件。推荐不产生执行授权，交付后停止。

## 6. 偏差核对与历史

- verify 的对象选择、偏差判定、处置与交付见 [verify](verify.md)。任意阶段交付后均可调用，不占正式阶段轮次；仅写核对交付、正文索引和必要正式报告，不改变控制字段或代替 review、复审、validate。
- verify 按用户请求执行；仅在发现具体偏差时建议核对并说明对象。不固定提议，不为未执行的 verify 生成跳过记录或人工介入项；review、复审与验收要求保持不变。
- 历史阶段和复盘保留原版本与事实。规则升级不自动接受方案、降低验收或重跑任务；仅处理当前任务的明确冲突。新的流程改动另行指派，普通阶段不改写技能。

## 7. 机器可读契约（Orchestrator Contract）

本节让外部编排系统无需解析正文即可判断：任务状态、阶段结果、候选、是否受阻、下一阶段、是否允许继续。Cohestra 仍是单阶段、可停止的执行单元：一次调用只执行一个阶段，阶段结束即停止，不管理队列、不负责调度，编排由外部系统决定。

### 7.1 载体与单一状态源

- 结构化状态写在任务 README（`.yuzio/cohestra/handoffs/<task-slug>/README.md`）的 YAML Front Matter；正文任务索引与 Markdown handoff 保持人类/智能体可读的推理与证据。
- Front Matter 是唯一可变的「当前控制状态」，只反映最近一次**正式阶段**交付的结果；handoff 仍是不可变历史交付。
- 不新增 `state.json`、`status.json`、`runtime.json` 等第二状态源；任务 README 的 Front Matter 与正文共同构成单一任务索引。
- `verify` 不是正式阶段：其本机交付只写 `verify-<轮次>.md` 与正文索引行；必要正式核对报告按第 5 节整理，不改 Front Matter 的 `stage_result`、`next` 等控制字段。`init` 不生成任务、不写 Front Matter。`report` 只读已有记录，不写 handoff、索引或 Front Matter，不新增契约字段或阶段枚举。
- YAML 必须恒可解析：**必填字段**（定义见第 7.2 节）每次正式阶段交付后全部写出；枚举写标量、布尔写 `true`/`false`、缺省写 `null`、整数不加引号。外部系统把必填字段缺失、无法解析或取值不合法的状态判为协议输出不合法，可选字段缺失合法，均不从正文倒推。

### 7.2 字段

```yaml
---
contract: "0.8"
task: <task-slug>
status: in_progress | completed | blocked | failed
execution_mode: attended | unattended
stage_result:
  stage: need | design | code | review | fix | validate
  status: completed | blocked | failed
  round: <阶段轮次，整数>
candidate:
  commit: <sha 或 null>
  snapshot: <可复核快照来源（handoff 路径）或 null>
findings:            # review/fix 交付后维护，可省
  blocking: <整数>
  non_blocking: <整数>
  unresolved: <整数，可省>
acceptance:          # validate 交付后维护，可省
  status: passed | failed | pending | blocked
next:
  stage: <六阶段名 或 null>
  allowed: true | false
  reason: stage_completed | blocking_findings | acceptance_failed | stage_failed | task_completed | human_decision_required | blocked | other
blocked:
  value: true | false
  reason: human_decision_required | missing_input | missing_permission | dependency_unavailable | environment_blocked | candidate_unavailable | other | null
---
```

- `contract`：契约版本，取当前协作协议版本（`"0.8"`），随协议一起演进。消费方据此核对版本；缺失或不支持时按「契约未就绪」处理，不猜测字段含义。协作协议版本变更时，同仓维护的编排技能（Cadra）须同步发布支持新契约的版本，否则其 run 前置检查将停在「契约未就绪」。
- `task`：任务目录 slug，与目录名一致。
- `status`（任务）：`in_progress`／`completed`／`blocked`／`failed`。不使用编排队列状态（如 draft、ready、queued、running）——那属于外部 Orchestrator。写入规则：正常推进写 `in_progress`；**终点到达**（用户声明的终点已完成，见第 7.3 节）或 validate 交付且 `acceptance.status: passed` 并满足既有完成条件时写 `completed`；`blocked.value: true` 时同步写 `blocked`，受阻解除、阶段继续交付后回到 `in_progress`；阶段产出被判无效且不可继续时写 `failed`。
- `execution_mode`：产生当前状态那次调用的执行上下文，缺省 `attended`。
- `stage_result`：刚结束的正式阶段及其结果；`status` 只取 `completed`／`blocked`／`failed`（阶段随交付结束，不设进行中值），`round` 为阶段轮次（见第 5 节）。
- `candidate`：被审查或验收的固定候选，优先 `commit`；无 commit 时用 `snapshot` 指向既有候选机制的可复核快照来源（不削弱第 4 节候选规则）。形状恒为映射、叶子可空：无候选（need/design）写 `candidate: {commit: null, snapshot: null}`。
- `findings`：当前**未关闭**的问题计数。review 交付时即其输出计数；fix 交付后按裁决与修复结果更新，`blocking` 表示仍未关闭的必做问题数；`unresolved` 为待核实未裁决数，可省。
- `acceptance`：validate 的验收判断。**validate 交付时**，只有 `status: passed`（且满足既有完成条件）才把任务 `status` 写 `completed`。终点未经 validate（终点到达于 validate 之前）时该字段可缺省（等价 `null`），不阻止 `completed`。
- **必填与可选**：必填字段为 `contract`、`task`、`status`、`execution_mode`、`stage_result`、`candidate`、`next`、`blocked`，每次正式阶段交付后全部写出；可选字段为 `findings`（review/fix）、`acceptance`（validate）及 `findings.unresolved`，阶段适用时写出，缺省等价 `null`。「协议输出不合法」的判定只针对必填字段；可选字段缺失合法。第 7.5 节的最小写入同样给出完整必填集，只是只含本次交付的值。
- `blocked.value: false` 时 `blocked.reason: null`；`next.allowed: false` 时 `next.stage: null`。`reason: other` 时必须在正文说明。

### 7.3 next 标准化

所有正式阶段交付后必须给出 `next`；外部系统只读该字段做控制流判断，handoff 的推荐与之保持一致；README 正文仅补充准确输入、前提与责任，不重复下一阶段字段，也不得与控制状态矛盾。映射：

| 交付 | 条件 | next.stage | allowed | reason |
|---|---|---|---|---|
| need／design／code | completed | 链条下一阶段（design／code／review） | true | stage_completed |
| review | completed 且 blocking = 0 | validate | true | stage_completed |
| review | completed 且 blocking > 0 | fix | true | blocking_findings |
| fix | completed，按既定要求需复审 | review | true | stage_completed |
| fix | completed，无需复审 | validate | true | stage_completed |
| validate | acceptance = passed 且既有完成条件满足 | null | false | task_completed（任务 status → completed） |
| validate | acceptance = failed | fix（建议回 design／need 时写对应阶段） | true | acceptance_failed |
| validate | acceptance = pending，缺必要复审且复审输入、授权与执行条件齐备 | review | true | stage_completed |
| validate | acceptance = pending，仅缺本阶段能够补足且已有执行条件的验收证据 | validate | true | stage_completed |
| 任意 | 用户声明的终点已到达（如 small-change 于 code／review 收尾、review-only 于 review 收尾） | null | false | task_completed（任务 status → completed，acceptance 可缺省） |
| 任意 | 受阻（环境／输入／权限／依赖／候选缺失／需人工决定） | null | false | blocked 或 human_decision_required（任务 status → blocked） |
| 任意 | 阶段失败、可重试 | 本阶段 | true | stage_failed（正文写恢复条件） |
| 任意 | 阶段失败、不可继续 | null | false | stage_failed（任务 status → failed） |

- `task_completed` 有两种来源：validate 验收通过，或用户声明的终点已到达。两者都写任务 `status: completed`；后者 `acceptance` 可缺省，消费方按其口径标注 `acceptance = unknown`。
- **validate 完成一致性**：本轮 validate 只有在范围完成、必做问题关闭、所需复审完成且必要证据齐全时才写 `acceptance.status: passed`。一旦本轮判为 passed，待发布 README 必须同时满足：`stage_result: {stage: validate, status: completed, round: 本轮轮次}`、任务 `status: completed`、`acceptance.status: passed`、`next: {stage: null, allowed: false, reason: task_completed}`、`blocked: {value: false, reason: null}`；正文如有状态说明须与之相符，不得留下后续必做阶段；无需重复抄写完成字段。发布前与发布后回读均逐项核对，并与本轮 handoff、候选及完成条件一致；缺项或任一冲突都不能报告索引同步成功。不将仅有 `stage_result.status: completed` 或部分检查通过当作验收 passed；也不把历史 passed 套用到另一轮次或候选。此约束不改变用户声明的非 validate 终点及 verify 不改控制字段的规则。
- 「用户声明的终点」只存在于对话与交付记录，不进契约；外部编排系统无法读取该声明，只能按任务 flow 推断终点合法性（如 Cadra 终态映射第 7、8 行：flow 含 validate 而验收缺省时判 blocked）。与外部编排配合使用时，终点范围用任务 flow 表达——以 review 收尾选 `review-only` 或显式序列，不靠 `small-change` 等含 validate 的序列提前声明。
- validate 已确认验收失败时优先推荐 fix/design/need，不因还缺复审改为 pending；缺必要复审且可执行时推荐 review，不能用重复 validate 代替。复审或补证据缺输入、权限、执行条件，或需要人工决定时走受阻路径；不能仅因缺口将来可恢复就允许重复本阶段。
- 终点到达以该阶段自身交付完成为前提（如 review 必做问题未关闭时不能按终点收尾，仍走 `blocking_findings`）；受阻与失败路径优先于终点表达。
- `blocked` 优先于 `next` 表达「禁止继续」：`blocked.value: true` 时 `next.allowed` 必为 `false`，任务 `status` 写 `blocked`。
- `next.stage` 只取六阶段名或 `null`，不发明新阶段；终点由用户决定，交付时按 `task_completed`（终点到达）或受阻路径表达，不自行宣布未经用户声明的终点。

### 7.4 执行上下文 unattended

调用方在调用中声明 `execution_mode: unattended`（记入 handoff「身份与输入」与 Front Matter）。这是执行上下文，不是新阶段。无人值守期间：

- 不主动提问并无限等待：need 的成组提问不执行，只用已确认信息加明确标注的假设推进，且仅当不需要产品方向选择；一旦需要用户才知道的决定（产品方向、范围边界、授权、权限），直接走受阻路径。
- 不自行选择产品方向，不扩大范围，不产生新的隐含授权。
- 不为了继续流水线而降低质量门禁或验收标准。
- 阶段无法在现有信息下合法继续时：`stage_result.status: blocked`、`blocked.value: true`（reason 按实际取 `human_decision_required`／`missing_input`／`missing_permission`／`dependency_unavailable`／`environment_blocked`／`candidate_unavailable`）、任务 `status: blocked`、`next: {stage: null, allowed: false, reason: human_decision_required 或 blocked}`，然后停止。

`attended`（默认）行为不变：提问、建议与用户决定仍按各阶段说明执行。

### 7.5 状态缺口与恢复

- 新任务首次从任一正式阶段起步时建立当前契约。已有正式交付或调用的任务缺契约、版本不支持或字段不合法时，报告路径与缺口，停止依赖该状态的推进；本版本交付中断按下条恢复，其余情况不自动转换旧格式、不从正文补造控制状态。
- 本版本交付中断或索引同步失败时，按[索引发布与恢复](publication.md)核对本轮结果并恢复同步，不重跑已完成阶段。
- `verify` 不修复控制字段；查询时无法核实的状态标为未知。历史文件与已确认决定保留，不因规则升级删除或重写。

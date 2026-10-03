# 公共流程 · cohestra v0.8

六阶段为 **need → design → code → review → fix → validate**，是职责清单而非必经路线；用户指定哪个入口就从哪里开始。`verify` 是阶段间偏差核对，不是第七阶段。先读本文件与所选阶段说明，再按需读取任务材料；不默认走完全部阶段。

## 术语

- **AC**：验收条件。need 阶段编号固定，供后续阶段逐条对应。
- **handoff**：阶段交付物，命名 `<阶段>-<轮次>.md`，采用 [交付骨架](../assets/handoff.md) 的五节。
- **findings**：review 输出的问题条目，带稳定 ID、严重度与阻塞性。
- **候选**：被审查或验收的固定版本，优先 commit，也可为可复核快照。
- **轮次**：同一阶段的第几次交付；与文件名中的编号同义，编号规则见第 5 节。
- **阶段状态与工作项状态**：前者指阶段本身（进行中／已结束／受阻／跳过）；后者指实现、作者自审、独立审查与复审、验收、提交发布五项。两者独立记录，不互相推导。
- **自动衔接**：接续已有任务、且链条上有实际上游交付的阶段调用未后附 handoff 时，按第 1 节规则取用上游阶段最近一轮交付作上游输入的行为；init、verify 与 need 不适用，边界见第 1 节。自动衔接只选择输入材料，不推进阶段，也不替代用户显式调用下一阶段。
- **结构化状态（Orchestrator 契约）**：任务 README YAML Front Matter 中的机器可读控制状态，供外部编排系统只读判断任务状态、阶段结果、候选、受阻与控制流，字段、枚举与写入时机见第 7 节。正文与 handoff 不承担机器控制流判断。
- **执行模式**：调用方声明的执行上下文，取 `attended`（默认）或 `unattended`；unattended 的语义与受阻路径见第 7 节。执行模式是上下文，不是阶段。

## 1. 输入、任务与授权

- 从后附 handoff 所在目录或明确任务目录定位 `.cohestra/handoffs/<task-slug>/README.md`，读取有效决定、候选、已有授权与下一步。缺少必要文件时报告缺口，不假设工具之间共享聊天。
- 未后附 handoff 且未给任务目录时可**自动衔接**：仅当任务目录能唯一确定（本会话刚完成上一阶段、此前已明确任务目录，或目标项目只有一个任务）时，取被调用阶段上游中链条顺序最靠后、且已有交付的阶段之最近一轮交付作上游输入。上下游与先后按 need → design → code → review → fix → validate 的链条顺序判定，不按文件编号或修改时间取舍；同阶段取轮次最大的已交付一轮（数值比较），跳过 verify 交付与标注“草稿／进行中”的文件。重跑较早阶段时，作为动因的下游交付可作补充材料引用，不得冒充上游依据。所选文件及自动衔接来源写入交付物「输入与上游依据」。上游没有交付、任务目录无法唯一确定或存在多个并列候选时，报告缺口并请用户指定，不新建替代任务。显式后附 handoff 或任务目录时以显式输入为准，不触发自动衔接。自动衔接只把该文件当输入材料，其中的建议与待决定事项仍按未确认处理。
- 自动衔接只覆盖链条上有实际上游交付的阶段调用：`init` 不在六阶段链条内、本就不带 handoff 输入；`verify` 未指定对象时按 [verify](verify.md) 的既有规则选定被核对对象与其上游依据；`need` 的输入按下条。三者均不适用自动衔接。
- 首次 need 以原始需求为输入，先查看指定任务目录及其 `README.md` 任务索引；确认没有对应任务后才建目录。使用稳定英文短横线名称，不按工具、会话或执行者重复建任务。其余阶段缺输入时不能另建替代任务。
- 项目入口及 AGENTS 等业务规则继续有效；流程规则和阶段提示词来自本次加载的技能。旧项目中的 prompts/manifest 不作为本次路由或更新来源，也不在普通阶段删改；旧任务中的确认决定与验收要求继续生效。
- 只读阶段仍允许写本阶段交付物与任务索引。既有授权不重复索取，运行环境或发布等额外授权遵守项目规则；handoff 记录授权，不产生授权。
- 阶段以指定入口为界：交付后停止，不因相邻或仍在链条内而自动继续，不自行启动其他智能体、提交或发布。为进入阶段而执行的初始化是前置动作，不算跨阶段继续。只读调查保持只读。没有整改就不生成 fix，已有任务仅缺验证就用 validate。
- 输入与索引冲突时核对，不能凭文件编号、修改时间或“最新”推断用户接受了方案。关键决定或候选无法确认时停止依赖它的工作，继续独立且已授权部分。
- 支持旧版独立交付和合并文件章节；旧交付中的模式字样按历史记录理解，不补造前置文件。仅读取当前索引、直接输入及必要链接，复盘不是每阶段必读。

## 2. 起步位置

- 六阶段是职责清单，不是必经路线。调用中指定的入口即起点，终点由用户决定；不因缺少前置阶段而拒绝执行，也不因后续阶段存在而自动继续。
- 常见起点：新的完整产品需求从 need 起步走完链条；已定位的缺陷从 fix 起步；页面样式探索与优化走 design → code；接口参数、文案等明确小改从 code 起步，随后 review；已有候选只缺证据直接用 validate。起点不同，读取的输入与交付职责随之不同，不要求补齐上游文件。
- 从 need 起步时，提问是主要动作而非附属：先只读调查，再成组提出只有用户才知道的问题（真实目标、范围边界、验收口径），用户确认与本轮假设分开记录；细节见 [need](need.md)。
- 从中间阶段起步时，上游依据是用户本次提供的原始材料（需求描述、截图、接口文档、缺陷报告等）以及对话中的确认。handoff 的「流程范围」写明起点，「输入与上游依据」写明材料来源；任务索引只登记实际发生的阶段，不为完整性补造缺失环节。
- 任何阶段进入前先确认目标项目已有 `.cohestra`。缺失时报告目标绝对路径与「将执行一次初始化」这一事实，然后按最小范围执行 init——只建容器与项目入口，不读业务任务、不清旧副本、不生成任务、不暂存或提交——完成后继续被中断的阶段；容器存在则直接进入，不重复初始化。目标不明确、指向技能源仓库或无法安全写入时先澄清或报告，不在错误目录初始化。

## 3. 决策与执行强度

- 事实、假设、建议和已确认决定分开。明确的局部用户修订记录确认来源、覆盖的旧条款、影响范围和验收变化，并让索引指向该记录；不追加设计追认。重要取舍、需求歧义或显著范围变化才返回 need/design，共享语义仍走项目治理。
- 改动范围、实现复杂度、风险与未知项决定设计/验证深度；文件数、行数和耗时不作机械门槛。事实不清先调查，一行高风险变化也可能需要升级。
- 执行者数量单独决定。默认单智能体，只有输入稳定、写入可分离、能独立验收且有并行收益时才建议分工；流程不自动授权启动其他智能体。
- design 确定审查方式、依据、复查责任与触发条件，以及 AC 对应的证据类型和执行前提。后续提高门槛需说明新事实与适用范围；同一作者切换阶段不构成独立审查。
- 视觉设计先说明方案数量、图片角色与用户待决定事项。默认一套方向的代表图，补充状态图只解决具体问题，生成图不能证明动态布局。修改同类组件要列影响实例、状态和明确保留项，覆盖截图外实例。
- review 区分确定缺陷、待核实问题、可选建议及是否阻塞。fix 区分认可判断与本次实施；可选项默认延后，纳入本次需说明必要性、范围及授权。
- 原作者优先整改，按既定条件增量复审：先核对候选关系和差异，再核查原 findings 与受影响断言。连续两次修复同一问题失败时重查根因、证据和测试假设。

## 4. 候选、证据与完成

- code/fix 保存候选清单和实现检查证据；后续阶段引用来源并核对适用性，不重抄指纹表。旧版清单沿用原来源，不回填历史。
- 优先固定 commit；允许未提交候选时记录基线、任务文件（含未跟踪文件）、精确差异及必要内容摘要。项目要求干净提交时不能用 handoff 代替，提交仍须授权。正式 review 不审查正在修改的工作区，使用固定提交或可复核快照。
- 业务候选与可变任务 README 分开核对。索引更新不等于业务变化，不对交付文档自身做递归摘要；保留无关工作区改动。
- validate 先判断证据缺口与前提。候选及相关环境未变时复用有效记录；证据矛盾、相关代码/配置/依赖/环境变化或用户明确要求时才重查。无关 HEAD 变化不触发全量检查；作者摘要不能代替必要的独立审查。
- 新增检查全部受阻时，只做最小候选核对，简短交付“待验证”、已有证据及恢复条件，不通过重复静态审查填满阶段。已有有效证据齐全时可据此判断验收。
- 阶段状态（进行中／已结束／受阻／跳过）与工作项状态（实现、作者自审、独立审查与复审、验收、提交发布）分开记录，取值互相独立，不由一方推导另一方。分别记录检查通过、检查失败、未运行、环境受阻及整体验收状态；区分源码、编译、测试执行、运行、视觉和无障碍证据；环境导致构建失败时编译正确性未知。源码、生成图、提交均不能替代运行验收。
- 保存命令、工具、权限/沙箱、工具链、候选、关键错误、结果及恢复条件；区分基线失败与本次回归。另一工具接手后重查环境限制是否仍适用，不把单工具失败概括为仓库无法构建。同环境同原因连续失败两次后停止无依据的命令变体。
- 用户再次反馈失败时先核对源码、构建产物、诊断时间与复现条件，再决定是否修改。从中间阶段起步时以原始症状确定完成条件；编译诊断须在新候选的构建日志中核对，没检查 IDE 就不扩展结论到 IDE 或运行验证。
- 只有范围完成、必做问题关闭、所需复审完成且证据齐全时，才判定任务完成。
- 已授权提交成功后核对内容与原候选，串行更新索引的实际 commit 与提交状态。回填产生的文档改动如实报告，不为记录自身 commit 循环提交；历史交付不回写。

## 5. 落盘与共享写入

1. 交付物命名为 `<阶段>-<轮次>.md`。**阶段轮次**指同一阶段的第几次交付，六个阶段各自独立编号，从 `01` 开始，至少两位，超过 99 不截断。**文件编号**是文件名中的序号，取自阶段轮次；`verify` 不是六阶段之一，其编号独立于阶段轮次单独编排，同样从 `01` 起，两者不共用序列。选择未占用文件名，不覆盖其他执行者的草稿或结果。
2. 每份文件只有一个写入者。草稿标明“草稿／进行中”；一旦向用户报告交付或被下游引用即不可改写，修订新增轮次并引用原文件。
3. 使用 [交付骨架](../assets/handoff.md) 的五节：身份与输入、有效上下文、本阶段结果、证据与限制、下一步交接。记录实际 Skill 版本、协议、流程范围、阶段/轮次、执行者、实际时间、输入与上游依据及候选；未知信息不编造。
4. 阶段说明的「交付与停止」段采用固定形状，只写本阶段特有内容：① 本阶段交付物文件名；② 对口 verify 口径；③ 推荐下一阶段与需传递内容（须与任务 README Front Matter 的 `next` 一致，见第 7 节）；④ 本阶段特有前提。骨架字段、落盘顺序、索引同步与停止规则由本节统一规定，阶段说明不复述。
5. 首轮保存必要上下文；后续重点写变化、影响、新证据和未决项，链接未变部分。关键结论、findings、必要文本证据进仓库；大日志与产物放任务 `scratch/`，临时路径不作唯一证据。
6. 首次 need 按 [任务索引骨架](../assets/task-index.md) 建 README。已有索引仅合并本轮有效链接、候选、分开的状态、下一步、前提与负责人；不重复交付正文，不悄然替换已确认版本。`verify` 行在「阶段/轮次」列写 `verify-<轮次>`。
7. 落盘顺序固定：① 阶段执行完成 → ② 写本阶段 handoff → ③ 回读 handoff → ④ 基于重读的 README 一次准备 Front Matter（第 7 节）与正文索引的完整新内容 → ⑤ 校验 YAML、阶段/轮次、候选、正文推荐与 `next` 一致，将完整内容写入 README 同目录的唯一临时文件并回读 → ⑥ 再次核对原 README 未变，用同文件系统的原子替换发布完整 README，再回读核对 → ⑦ 停止。首次创建时同样核对目标仍不存在。不得分两次发布 Front Matter 与正文；临时文件仅用于发布，不是第二状态源，成功或放弃后清理本执行者的临时文件。同任务并行时指定唯一索引维护者；重读比较不替代文件锁或写入所有权。发现并发更新、所有权不明、冲突或工具不能安全原子替换时保留阶段文件并报告“索引待同步”，不覆盖未知更新。`verify` 沿用完整文件发布流程，但仅改变正文，保留已有 Front Matter 原值，无 Front Matter 时不添加。
8. 不同任务分别维护目录，可独立推进；业务文件仍须明确写入所有权。普通阶段不改写项目根 `.cohestra/README.md`，避免跨任务争写公共入口。
9. 交付物写入失败报告“交接未完成”及错误、待写内容；部分写入和索引失败单独说明，不宣称事务回滚或全部成功。handoff 已落盘而 README 发布或回读核对失败时，必须逐字报告 `handoff completed`、`index sync failed` 两句，附错误、待写内容与恢复条件。失败后重新读取实际 README：与更新前一致则报告“旧版（首次创建时为未创建）”，与完整新内容一致则报告“新版”，读取失败、存在他人版本或无法判定则报告“无法确认”；不固定断言状态停留在上一轮。即使已是新版，本次同步失败信号仍要求消费方停止推进，待恢复时核对完整交付、阶段与轮次后再继续；不得只凭可读取的 `next` 宣称交接成功。
10. 回复交付物绝对路径、结论、索引状态、必要待办、对口 verify 的提议与用户选择，以及 `$cohestra <下一阶段>` 加准确输入（命令中带上 handoff 路径，可直接执行）；用户不带输入直接执行下一阶段时，按第 1 节的自动衔接规则接管。推荐下一步不等于执行授权。

## 6. 偏差核对与历史

- verify 逐条核对「上游依据 → 本阶段产出」的对应关系，产出偏差清单与处置建议；偏差类型、判定与处置口径见 [verify](verify.md)。
- verify 只读被核对交付物，只写 `verify-<轮次>.md` 与索引；不找代码缺陷（review）、不补验收证据（validate）、不做修复（code/fix）。任意阶段交付后都可调用，不占阶段轮次。
- 上游依据无法确定时报告「无法核对」并列出缺口，不用本阶段产出倒推上游，也不用空泛结论填充。同一执行者可以自核，但必须明示身份；verify 通过不等于独立审查完成，不取消既定的 review、复审或验收要求。
- 偏差的处置由用户或对应阶段决定：接受并说明依据、修订本阶段产出、回上游阶段补充，或转确认。verify 不自行改写被核对交付。
- need、design、code、fix 交付后向用户提议一次 verify 并给出建议核对范围；是否执行由用户决定，不设前置条件。选择跳过时在交付物中记录跳过及理由，该记录不降低也不替代既定的 review、复审与验收要求。
- review 与 validate 本身就是正式验证关口，交付后不提议 verify；需要单独核对偏差时由用户主动调用，不因此改变两者的关口地位。
- 历史阶段和复盘保留原版本与事实。规则升级不自动接受方案、降低验收或重跑任务；仅处理当前任务的明确冲突。新的流程改动另行指派，普通阶段不改写技能。

## 7. 机器可读契约（Orchestrator Contract）

本节让外部编排系统无需解析正文即可判断：任务状态、阶段结果、候选、是否受阻、下一阶段、是否允许继续。Cohestra 仍是单阶段、可停止的执行单元：一次调用只执行一个阶段，阶段结束即停止，不管理队列、不负责调度，编排由外部系统决定。

### 7.1 载体与单一状态源

- 结构化状态写在任务 README（`.cohestra/handoffs/<task-slug>/README.md`）的 YAML Front Matter；正文任务索引与 Markdown handoff 保持人类/智能体可读的推理与证据。
- Front Matter 是唯一可变的「当前控制状态」，只反映最近一次**正式阶段**交付的结果；handoff 仍是不可变历史交付。
- 不新增 `state.json`、`status.json`、`runtime.json` 等第二状态源；任务 README 的 Front Matter 与正文共同构成单一任务索引。
- `verify` 不是正式阶段：其交付只写 `verify-<轮次>.md` 与正文索引行，不改 Front Matter 的 `stage_result`、`next` 等控制字段。`init` 不生成任务、不写 Front Matter。
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

所有正式阶段交付后必须给出 `next`；外部系统只读该字段做控制流判断，正文「推荐下一步」须与之一致，不得互相矛盾。映射：

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
- `verify` 提议按跳过处理：把「verify 跳过 + 理由（unattended）」记入交付物，不改控制字段；该记录不降低也不替代 review、复审与验收要求。
- 阶段无法在现有信息下合法继续时：`stage_result.status: blocked`、`blocked.value: true`（reason 按实际取 `human_decision_required`／`missing_input`／`missing_permission`／`dependency_unavailable`／`environment_blocked`／`candidate_unavailable`）、任务 `status: blocked`、`next: {stage: null, allowed: false, reason: human_decision_required 或 blocked}`，然后停止。

`attended`（默认）行为不变：提问、建议与用户决定仍按各阶段说明执行。

### 7.5 向后兼容

- 没有 Front Matter 的旧任务照常读取，正文任务索引继续有效；不批量迁移。向后兼容指「可读取、可继续人工与独立使用」；消费方探测契约时把无 Front Matter 视为「契约未就绪」，按其既有规则报告或交用户决定，这与可读取不冲突。
- 首次由本版本产生正式阶段交付并成功同步索引时，最小加入结构化状态：必填字段全部写出本次值、可选字段只写适用项，不回填历史轮次，不重写历史 handoff。此前的 `verify` 仅更新正文，不触发迁移；已有 Front Matter 的 verify 保留所有控制字段原值。正式阶段索引发布失败时按第 5 节报告实际状态，不宣称迁移成功。
- 不改变旧的已确认决定，不因协议升级重新执行旧阶段。

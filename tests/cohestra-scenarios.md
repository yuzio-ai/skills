# Cohestra 验证场景

这是维护者的验收清单，不是每次阶段执行的必读文件。不创建自动安装器或将模拟结果冒充实际智能体执行。

## 文件与路由

- SKILL.md 前置元数据有效，发行版与协议版本明确，九个入口（init、六阶段、verify 与 report）均能定位说明文件；阶段只加载公共流程、对应说明及必要输入，init 不加载业务阶段，report 只加载报告说明、发行版本、任务索引与必要问题来源，字段含义不明时查公共流程第 7 节。
- Markdown 相对链接存在，模板占位符可识别，技能包无脚本和测试运行时依赖；无失效的项目 prompts 路由、旧安装器命令或模板管理清单。
- 普通阶段只读取任务索引及必要输入。need/design/review/validate/verify 的业务只读边界仍允许阶段落盘；code/fix 保留实施授权与停止线。
- 五节交付、任务索引、结构化状态（任务 README YAML Front Matter）、版本记录、AC、finding ID、候选及证据链可以通过模板和说明完整定位。
- 根 README 为双语版（`README.md` 英文、`README.zh-CN.md` 中文），顶部语言切换行双向可达；两版的标题层级、表格行列、代码块内容与相对链接目标一致，改一版必须同步另一版。

## 临时安装

在临时用户目录、临时 npm 缓存与临时 Git 仓库运行安装器，不修改真实用户安装或业务项目。记录实际 CLI 版本。

- 从本地源仓库发现并安装 cohestra，分别检查用户级与项目级；指定多个工具时核对实际目录与链接。
- 对比完整技能包与安装结果，包含嵌套 references、assets 和隐藏的忽略规则；安装本身不创建 `.cohestra`。
- 源仓库不可访问时，安装副本中的路由、相对链接和模板仍完整；移动临时项目后检查内部链接。
- 若验证技能更新，必须用临时的可控来源，核对命令仅更新指定技能/作用域且保留项目 `.cohestra`。没有对应实测时标明未实测，不能用文件复制代替 CLI 更新证据。

## 上下文与阶段桌面推演

| 场景 | 预期结果 |
|---|---|
| init 新项目 | 只有项目入口、忽略规则、两个空记录容器；没有 prompts、manifest 或示例任务 |
| 第二个工具重复 init | 复用原目录，不覆盖入口、交付或复盘，不按工具建立副本 |
| 旧版上下文 | 保留旧文件与业务决定；必要时仅追加一次来源说明，明确尚未清理，不冒称全面迁移 |
| 授权清理旧副本 | 仅在明确范围内执行：先判定制与漂移、盘点引用、备份后移废纸篓、回读并查链接；已交付文件保留悬挂；范围外不动 |
| 容器已删除但 Git 仍有记录 | 先报告可恢复与不可恢复清单，再按新项目建立；删除记录是否提交由用户决定，init 不提交、不 checkout |
| 入口混有协议副本 | 先提取项目专属事实清单，按入口模板重建并逐项核对；缺项即报告未完成，不搬运原文 |
| 要求删除任务记录 | 整体验收未通过时先报告前提并交用户决定；不按「已完成」删除 handoffs 或复盘 |
| 普通阶段缺少上下文容器 | 先报告目标路径并执行一次最小初始化，再继续本阶段；不误把技能源仓库或其他目录当目标 |
| need → design → code | 同一任务目录接力；未确认建议不自动变成实现依据 |
| 上一阶段交付后不带输入直接跑下一阶段 | 自动衔接同任务目录中被调用阶段上游、链条顺序最靠后的已有交付阶段之最近一轮（跳过 verify 与草稿，不按文件编号或修改时间取舍），交付物「输入与上游依据」写明所选文件与来源；handoff 内建议不因此变成已确认 |
| 重跑链条中较早阶段（如 fix 后再次 code）不带输入 | 取 code 上游（design 或 need）的最近一轮交付，不取下游 fix 交付；下游交付可作补充材料引用，不得冒充上游依据；上游无交付时报告缺口请用户指定 |
| 无输入调用 verify 或 need | 不适用自动衔接：verify 按其「最近一轮实际交付与其直接上游」规则选对象；need 的输入按公共流程第 1 节既有条（首次为原始需求），不衔接任务目录内交付 |
| 无参数 init（空项目或已有任务项目） | 不适用自动衔接：直接建立或复用容器与项目入口，不因缺上游交付报告缺口或请用户指定 |
| 任务目录无法唯一确定时裸跑下一阶段 | 报告缺口并请用户指定，不凭文件编号、修改时间或「最新」猜测，不新建替代任务 |
| review → fix → review | 固定候选、稳定 findings、新轮次交付、按差异增量复审 |
| 两个任务并行 | 各写本任务，不争写项目入口；业务文件另明确所有权 |
| 同任务索引冲突 | 保留独立交付物，报告索引待同步，不覆盖他人内容 |
| 从 design 起步（无 need 交付） | 以本次需求与参考为上游依据，「流程范围」写明起点，不补造 need 文件 |
| 从 code 起步（接口或样式小改） | 直接实施并落 code 交付，不要求先有 design；随后可接 review |
| 用 verify 核对 design 与 need | 输出偏差清单与处置，只写 verify 交付与索引，不改被核对文件 |
| verify 缺上游依据 | 报告「无法核对」并列出缺口，不用本阶段产出倒推上游 |
| verify 与 review 分工 | verify 不产缺陷级 findings；需要缺陷审查时推荐 review |
| verify 编号与索引登记 | 产出 `verify-<轮次>.md`，编号独立于六阶段序列；任务索引按 `verify-<轮次>` 登记，不占阶段轮次 |
| verify 提议无前置条件 | need/design/code/fix 交付后提议一次并给建议核对范围；是否执行由用户决定，不以需求规模作门槛 |
| 未初始化项目直接从中间阶段起步 | 先提醒并完成最小初始化，再执行该阶段；不要求用户先手工补 init |
| validate 缺运行前提 | 最小候选核对，复用有效证据，简短待验证，不重复审查填充 |
| 用户级技能更新 | 后续交付记录新技能版本，历史交付、已确认决定和验收状态不变 |
| need 提问 | 先只读调查再成组提问，问题针对目标、分解、边界、验收；用户确认与假设分开记录，用户不回答时按标注的假设继续并入未决项 |
| need/design/code/fix 交付后的 verify 提议 | 这四阶段交付后提出是否 verify 并给出建议核对范围；用户跳过时记录理由，不因此降低 review、复审或验收要求 |
| review/validate 交付后 | 不提议 verify，两者本身即正式验证关口；需要单独核对偏差时由用户主动调用 |
| 阶段说明的「交付与停止」段 | 只写本阶段文件名、对口 verify 口径、下一阶段推荐与特有前提；落盘、骨架、索引与停止规则指向公共流程，不复述 |
| 缺容器时从任意阶段起步 | 先最小初始化再执行；初始化不读业务任务、不清旧副本、不生成任务、不提交 |
| 目标路径不明确或有多个候选 | 先澄清，不在错误目录初始化，也不开始阶段 |
| 只讨论、未知入口、旧 update 调用 | 不开始实施或隐式更新，说明入口或澄清必要信息 |
| code 正常完成（契约） | Front Matter：stage_result.status=completed，next.stage=review、allowed=true、reason=stage_completed，正文推荐与 next 一致 |
| review 无阻塞（契约） | findings.blocking=0 → next.stage=validate、reason=stage_completed，不要求 fix |
| review 有阻塞（契约） | findings.blocking>0 → next.stage=fix、allowed=true、reason=blocking_findings |
| validate 验收通过（契约） | acceptance.status=passed 且满足既有完成条件 → 任务 status=completed、next.stage=null、allowed=false、reason=task_completed |
| unattended 缺人工决策（契约） | 不提问空等、不自行选择产品方向 → stage_result.status=blocked、blocked.reason=human_decision_required、next.allowed=false，然后停止 |
| 环境阻塞（契约） | stage_result.status=blocked、blocked.reason=environment_blocked、next.allowed=false，然后停止 |
| README 更新失败（契约） | handoff 已落盘并回读；逐字报告 `handoff completed`、`index sync failed` 及错误，失败后回读并区分旧版（或未创建）/ 新版 / 无法确认，消费方停止推进，不固定宣称停留在上一轮 |
| README 完整发布（契约） | 完整准备 Front Matter 与正文，校验后写同目录唯一临时文件、回读、重读原文件核对未变、原子替换、回读；不分次发布两部分，临时文件不是第二状态源 |
| 临时写入或原子替换失败 | 正式 README 保持原版或未创建，不消费临时文件；保留 handoff、报告失败，清理本执行者临时文件 |
| 替换前检测到并发修改 | 保留他人版本与本阶段 handoff，不覆盖；单写入者仍是前提，重读比较不冒充文件锁 |
| 替换成功但回读失败 | 不宣称回滚；恢复读取后区分完整新版或无法确认，仍报告 index sync failed，恢复核实前不推进 |
| validate 缺必要复审但可执行 | 无已确认验收失败、输入/授权/执行条件齐备 → acceptance=pending、next={review,true,stage_completed}，正文一致，不重复 validate 代替 review |
| validate 复审条件不足 | stage_result.status=blocked、任务 status=blocked、blocked.reason 按实际原因、next.allowed=false，不空等或绕过复审 |
| validate 已失败且仍缺复审 | 保留 acceptance=failed，优先推荐 fix/design/need；整改缺权限等前提时受阻，不降为 pending |
| validate 仅缺本阶段可补证据 | 有执行条件才 next={validate,true,stage_completed}；缺权限或环境等条件时受阻，不以“将来可恢复”为由空转 |
| 旧任务无 Front Matter（契约） | 正文继续读取；首次正式阶段交付成功同步索引时才最小加入本次结构化状态，不批量迁移、不重写历史 handoff、不重跑旧阶段 |
| 旧任务首次 verify 后再正式阶段 | verify 只写交付与正文、不加 Front Matter；随后正式阶段成功同步时补完整必填集，阶段/轮次仅记录本次，不补造历史 |
| 外部编排只读控制流（契约） | 只读 Front Matter 即可判断任务状态、阶段结果、候选、受阻、下一阶段与是否允许继续，不解析正文 |
| Front Matter 唯一状态源（契约） | 不出现 state.json / status.json / runtime.json；handoff 仍是不可变历史交付 |
| verify 交付（契约） | 只写 verify 交付与正文索引行；完整发布 README 时保留已有 Front Matter 全部原值，不改 stage_result / next / execution_mode 等控制字段 |
| 链条外终点（契约） | 用户声明终点（如 review-only 于 review 收尾、small-change 于 code 收尾）→ 任务 status=completed、next={null,false,task_completed}、acceptance 可缺省；不与「仅 passed 才 completed」冲突，必做问题未关闭不按终点收尾；与 Cadra 配合使用时终点由 flow 表达（flow 含 validate 而验收缺省时 Cadra 判 blocked，见 Cadra 终态映射第 7、8 行） |
| 受阻任务状态（契约） | blocked.value=true 时任务 status 同步写 blocked，受阻解除后回 in_progress；消费方单读 status 也能看到受阻 |
| 契约版本核对（契约） | Front Matter 含必填 `contract`（取当前协作协议版本）；消费方可核对版本，缺失判「契约未就绪」而非靠字段嗅探 |
| 必填与可选（契约） | 必填集缺失才判协议输出不合法；findings/acceptance 等可选字段缺失合法；旧任务首次写入含完整必填集但不回填历史 |
| unattended 下 verify 提议（契约） | 按跳过处理并记入交付物（不改控制字段），不降低也不替代 review、复审与验收要求 |

## validate 完成状态一致性场景

以下为验收要求，不代表已完成实际智能体调用。采用隔离任务目录，准备固定候选、有效 AC、已关闭必做问题、必要复审和有效证据；除各行声明的差异外保持输入不变。按[公共流程](../cohestra/references/workflow.md)第 5、7.3 节执行，分别核对 handoff、README 发布前后内容与最终回复。

| 场景 | 预期结果 |
|---|---|
| 本轮验收 passed，原 README 为 in_progress，正常发布并回读（attended／unattended 分别核对） | 本轮 validate 的 stage_result.status=completed、任务 status=completed、acceptance.status=passed、next={null,false,task_completed}、blocked={false,null} 同时写入；轮次、候选与 handoff 一致，正文记录任务完成且无后续必做阶段，才报告索引同步成功 |
| 本轮验收 passed，首次为无 Front Matter 的旧任务发布契约 | 原子加入完整必填字段及 acceptance，与正常成功分支相同地写入并核对完成字段；不保留正文“进行中”，不补造历史阶段 |
| 待发布内容验收 passed，但任务 status 仍为 in_progress／blocked／failed | 三种值分别核对；发布前拒绝冲突内容，按本轮有效结果补齐完成状态后重新校验，不降低 acceptance；不能将原冲突组合发布为同步成功 |
| 待发布内容漏写完成字段或与之冲突 | 分别缺失或改错任务 status、stage_result 的阶段／结果／轮次、acceptance、next 的 stage／allowed／reason、blocked 的 value／reason，或保留正文必做下一阶段；任一项均不能通过完成一致性检查；仅漏写字段时补齐再校验 |
| 写入临时文件或原子替换失败 | 保留已通过的 validate handoff，README 为旧版或未创建；最终回复同时含 handoff completed、index sync failed、「验收通过，完成状态待同步」、实际版本／任务状态、错误和恢复条件；不推进 |
| 替换前发现 README 并发更新 | 不覆盖他人内容，保留本轮 handoff；报告上述三句和实际可确认状态，不能将保留他人版本视为本轮同步成功 |
| 替换已成功但首次回读失败，随后读到新版 completed | 仍报告上述三句，并说明新版 completed 已读到但本次同步核对失败，恢复核实前不推进；不宣称回滚或状态必然停留在上一轮 |
| 发布后回读发现完成字段、候选或正文不符 | 不报告同步成功，不覆盖未知并发变更；报告上述三句及不符项、实际状态和恢复条件，保留验收通过的 handoff |
| 缺必要复审／验收证据，或确认验收失败 | 分别沿用 pending／blocked／failed 对应出口；stage_result.status=completed 或部分检查通过都不能触发任务 completed，也不能报告「验收通过，完成状态待同步」 |
| 历史轮次或另一候选有 passed，本轮尚未通过 | 不据历史 passed 强制 completed；先核对本轮候选、轮次与证据适用性，按本轮结果写状态 |
| 非 validate 终点与 verify | 用户声明的 review-only 终点仍可 completed 且 acceptance 缺省；verify 仍保留 Front Matter 原值，不借本次校验修改历史控制字段 |
| 发布前校验进程非零退出 | 实际检查退出非零后不调用发布；保留 handoff 和原索引，报告同步失败及「验收通过，完成状态待同步」 |
| 旧任务的解析依赖不可用 | 缺模块不等于校验通过；没有可用校验通道时停止，不给旧任务发布未校验的新契约 |
| 校验进程返回 0 但没有解析结果 | 输出为空或不能确认成功时不发布，不从进程码单独推导完整校验通过 |
| 前置校验失败，后续日志命令成功 | 逐项核对真实子命令结果；最后命令或外层调用退出 0 不抵消前置失败，索引保持原版 |
| 首次解析失败，但另有可用解析工具 | 用后续独立调用完成同一内容的完整校验，先读取成功结果再发布；不通过事后补验追认已发生的发布 |
| 校验成功后待发布内容发生变化 | 旧摘要不覆盖新内容，先重新校验变更后的完整内容，收到成功结果再发布；实际发布摘要与最近成功校验一致 |

## report 只读汇总场景

以下为验收要求；实际执行结果在本文件末尾单独记录，不把场景定义视为实测。

| 场景 | 预期结果 |
|---|---|
| 裸调用 report，项目有多个任务 | 汇总当前项目全部任务，不走单任务自动衔接，不要求挑选一个 handoff，不扫描其他项目 |
| 目标缺 .cohestra／缺 handoffs／空 handoffs | 分别报告未初始化／记录缺失／暂无任务；均不创建文件，不触发 init |
| completed 但 non_blocking > 0 | 总览保留已完成状态并标注未关闭项，遗留明细展示延期文档问题与来源；不转 fix、不重开任务 |
| 正常进行中、受阻、失败与已完成任务 | 每个任务一行，分开显示阶段结果、任务状态、验收状态、三类问题计数与已记录 next；不从阶段完成推导任务完成 |
| completed 且 acceptance 缺省 | 验收未知，不推导 passed，不把合法可选字段缺失当契约错误 |
| findings 缺省或只有计数没有明细 | 缺省写未知；有计数保留计数并注明明细缺口，不给伪完整汇总或宣称无遗留 |
| 多轮 review/fix、不同任务同名 finding ID | 只按任务 + ID 合并有效处置；已明确关闭的旧条目不重复出现，不跨任务合并；已修改未复审按来源分别展示 |
| 延后、转交、不接受与裁决不明 | 延后／转交不推导关闭；已有不接受裁决不重新打开；不明写待核实，缺负责人写待指派，不新增延期或关闭要求 |
| 无契约旧任务、缺 README、损坏 YAML 或不支持契约 | 旧任务正文状态标来源，缺项未知；缺索引任务仍保留目录行，契约异常不以正文补造有效控制状态，不迁移或修复 |
| 索引与 findings 计数冲突、来源缺失或指向草稿 | 展示各自来源并列状态异常，不以计数零跳过明细、不自行选最大编号交付覆盖索引 |
| 读取期间记录变化、部分目录不可读 | 重读受影响记录，仍变化时标明；部分结果保留并标覆盖不完整，不宣称原子快照或零问题 |
| report 的文件副作用与执行边界 | 比较调用前后项目文件内容、目录清单和写入时间，均不变化；无 report 文件、handoff、缓存、索引写入、测试、构建、阶段调用或提醒；unattended 同样只读 |
| 报告输出 | 含项目、实际时间及时区、扫描覆盖、状态分布、全部任务总览、遗留明细与状态异常；来源可点击，输出后停止、不提议 verify |

交付检查结果时分开标注：文档静态检查、文件/CLI 实测、桌面推演、独立智能体实测。未执行项如实列出。

## 0.4.0 本地验证记录

- 使用 skills CLI 1.5.23，九组检查通过：元数据、文档与链接、八个入口、技能发现、项目级多工具安装、隔离用户级安装、移除源目录与移动项目、双项目模板落盘、实际离线 npx 重装。
- 39 个本地 Markdown 链接有效；安装后的完整技能包逐文件核对摘要，包含隐藏模板文件。重装保留已有任务、复盘和另一项目的记录。
- 项目级安装实测使用已有某工具配置目录的临时项目。该 CLI 版本在该配置目录缺失时会跳过对应工具入口，安装说明已记录核对方法。
- 上表场景已按路由、公共规则、阶段说明及模板完成桌面推演。模板落盘是文件系统检查，不代表独立智能体执行 init；并发安全依赖明确写入者及冲突停止规则，不宣称具备自动文件锁。
- 未执行远程 GitHub 安装、远程技能更新或独立智能体逐阶段实测；未启动真实工具会话验证技能发现。业务项目和真实用户安装未修改。

## 0.4.1 本地验证记录

- 变更：`references/init.md` 增加「授权内的清理」流程（把原先只写「需另行明确范围」的空白补成可执行步骤），并补两处规则空白——混合内容文件的收敛规程、磁盘无容器但 Git 仍有记录时的处理；`tests/cohestra-scenarios.md` 同步新增对应场景；`references/installation.md` 与根 `README.md` 的安装示例改用工具占位符，实测记录同步去掉具体工具名，全部文档保持工具中立。协议版本仍为 v0.3，阶段语义与交付骨架未变。
- 已执行（文档静态检查）：全包 16 份 Markdown 共 41 条相对链接全部解析；`SKILL.md` 路由表与 `init.md` 引用一致；`release.json` 与 `README.md` 的发行版本字样同步。
- 已执行（CLI 实测）：用 skills CLI 1.7.0 在一个已有项目级安装的真实项目中把副本从 0.4.0 刷新到 0.4.1，验收为副本与源仓库逐文件一致、`release.json` 版本正确、锁文件摘要由 CLI 改写。实测：按名称更新的调用（`update <name> -p` / `--project`）对该本地来源安装**静默空转**——命令正常结束，已安装副本与锁文件摘要均不变；改用 `add <源仓库绝对路径> --skill cohestra` 才生效，且该调用会在 CLI 默认作用域外顺带创建未配置的工具目录，需按「安装」一节核对实际路径后清理。
- 未执行（如实列出）：未在临时用户目录、临时 npm 缓存与临时 Git 仓库中做隔离安装实测；`$cohestra init` 尚未在独立智能体会话中执行；未做远程安装验证。
- 待补证据：`$cohestra init` 在真实项目的首次执行记录，同时覆盖「容器已删除但 Git 仍有记录」与「入口混有协议副本」两个新场景。
- 已补文档：据上述实测，在安装说明与仓库说明的「更新」章节记入本地来源的静默空转、替代调用、副作用清理与验收依据。
- 未做替代：未用文件复制冒充 CLI 更新证据；副本刷新由 CLI 调用完成并逐文件核对。桌面推演、文档静态检查与 CLI 实测分开标注。

## 0.5.0 本地验证记录

- 变更：移除 `quick` 入口与「轻量模式」；六阶段改为「职责清单、可从任意阶段起步」的一等规则，`SKILL.md` 增加诉求 → 起步对照表；新增 `references/verify.md`（阶段间偏差核对，偏差类型为遗漏、越界、偷换、口径不一致、未决被当成已决、追溯断链），`review` 与 `validate` 仍是代码与验收的正式关口；每份阶段说明新增可直接复制的「调用」片段（含从中间阶段起步的变体）与「对口 verify」段落；交付骨架与任务索引以「流程范围」替换「执行模式」，骨架增加「对口 verify 与建议核对范围」。协议版本 v0.3 → v0.4，发行版 0.4.1 → 0.5.0。
- 已执行（文档静态检查）：全包 16 份 Markdown 共 42 条相对链接全部解析，`references/quick.md` 移除后无悬挂链接；`SKILL.md` 路由表八个入口与 `references/` 下对应文件一一相符（`installation`、`workflow` 由路由规则内联引用，不进路由表）；除历史发行记录外，正文无 `quick` 残留、无「轻量模式」字样；`release.json`、根 `README.md`、`SKILL.md`、`workflow.md`、`assets/handoff.md` 的发行版本与协议版本字样一致。
- 未执行（如实列出）：未用 skills CLI 做 0.5.0 的安装或更新实测；`$cohestra verify` 尚未在独立智能体会话中执行；未做从 design、code、fix 起步的真实任务调用；未做远程安装验证。
- 待补证据：`$cohestra verify` 在真实任务中的首次执行记录，建议同时覆盖 design → need 的一致性核对与「缺上游依据」两种结果；从中间阶段起步的实际调用记录。
- 未做替代：本版结论仅来自文档静态检查，未用桌面推演冒充 CLI 实测或独立智能体实测，未改动业务项目与真实用户安装。

## 0.6.0 本地验证记录

- 变更：普通阶段的前置条件反转——目标项目缺 `.cohestra` 时不再只报告 init 入口，而是先说明目标绝对路径与「将执行一次初始化」，再按最小范围执行 init（只建容器与项目入口，不清旧副本、不读业务任务、不生成任务、不提交），完成后继续被中断的阶段；`need` 新增「澄清提问」小节（先只读调查再成组提问，目标／分解／边界／验收四类必问，识别被当成需求的方案，用户确认与假设分开记录，用户不回答时的收尾规则）；need、design、code、fix 四阶段交付后提议是否执行 `verify`，轻量需求可跳过，跳过理由记入交付物，`review` 与 `validate` 本身是正式验证关口、不提议 verify（同日维护者裁定：提议只对这四个阶段出现）。交付骨架的「对口 verify 与建议核对范围」改为「对口 verify 提议与用户选择」，任务索引增加跳过记录。协议版本 v0.4 → v0.5，发行版 0.5.0 → 0.6.0。
- 已执行（文档静态检查）：全包 16 份 Markdown 共 43 条相对链接全部解析，无断链；`SKILL.md` 路由表八个入口与 `references/` 下对应文件一一相符（`installation`、`workflow` 由路由规则内联引用，不进路由表）；旧规则字样（不隐式初始化、报告 init 入口后停止、先手工初始化项目、review 不再另设 verify）与 `quick`、「轻量模式」均零残留（历史发行记录除外）；`release.json`、根 `README.md`、`SKILL.md`、`workflow.md`、`assets/handoff.md` 的发行版本与协议版本字样一致。
- 未执行（如实列出）：未用 skills CLI 做 0.6.0 的安装或更新实测；「缺容器时自动初始化」「need 提问轮次」「交付后 verify 提议与跳过」三项均未在独立智能体会话中实跑；`$cohestra verify` 在真实任务中的首次执行记录仍缺；未做从 design、code、fix 起步的真实任务调用；未做远程安装验证。
- 待补证据：一次真实任务中「未初始化项目 → 提醒并最小初始化 → 继续阶段」的完整记录；一次 need 提问与用户确认的实际记录；一次用户选择跳过 verify 并记录理由的实际记录。
- 未做替代：本版结论仅来自文档静态检查，未用桌面推演冒充 CLI 实测或独立智能体实测，未改动业务项目与真实用户安装。

## 0.7.0 本地验证记录

- 变更：本版为**文档一致性与歧义修订**，不新增阶段、不改阶段职责划分与入出口集合。五类改动：① 去重——7 份阶段说明「交付与停止」段的逐字模板句（「下一步使用 `$cohestra <阶段>` 加本轮交付物或任务目录与补充指令；交付后停止，不自动执行下一阶段。」7 处、「在原任务目录新增…采用交付骨架…串行同步任务索引」6 处）收归 `references/workflow.md` 第 5 节新增的固定形状规则，阶段说明只保留本阶段特有内容；「常见诉求 → 起步」表去重（原在 `SKILL.md` 与根 `README.md` 逐字双份，仅表头一词之差）；六类偏差类型定义由 `workflow.md` 收归 `references/verify.md`；根 `README.md` 的「更新与职责」6 条（与 `installation.md`／`SKILL.md`／`init.md` 逐条重叠）删除，「提示词不复制回项目」由 4 处收敛为 2 处，README 改为使用者导读＋真源索引。② 取消「轻量需求」限定词：need、design、code、fix 交付后提议 verify 不变，是否执行改为「由用户决定，不设前置条件」（4 处同步）。③ verify 编号规范：verify 不占阶段轮次，其文件编号独立于六阶段序列单独编排，任务索引按 `verify-<轮次>` 登记；`workflow.md` 第 5.1 条区分「阶段轮次」与「文件编号」两个概念。④ 表意澄清：`workflow.md` 新增「术语」小节（AC、handoff、findings、候选、轮次、阶段状态与工作项状态）；`SKILL.md` 拆分「起步位置」与「执行规则」并补引导句、删除同文件内 7 行之隔的重复 verify 段落；`need` 统一为「design 前提判断」，并把来源不明的「初步分档」改为「复杂度与风险分档」；`design`／`fix` 的 verify 倾向性表述（「建议不要跳过」／「通常跳过」）改为中性；`fix` 展开「不复审代替裁决」为两句完整表述；`verify` 明确「本任务目录中最近一轮」与多候选取舍规则，并删除文件内重复的「一致时说明未覆盖部分」；`init` 定义「最小初始化」与「完整 init」两个执行范围；`workflow` 的「简短索引」改为具体文件路径；`handoff` 补 verify 自身的填法，`task-index` 把两行重叠字段改为「工作项状态」与「交付物链接」并说明与阶段状态的归属。⑤ 删除孤儿文件 `cohestra/agents/openai.yaml`（全包零文档引用，且文件名含产品名）。⑥ 统一容器最小初始化清单——同一规则原有三套措辞，现统一为「只建容器与项目入口，不读业务任务、不清旧副本、不生成任务、不暂存或提交」（`SKILL.md` 规则 3、`workflow.md` 第 2 节、`init.md`「由普通阶段触发的初始化」）；`verify.md` 补上与其余六份阶段说明一致的「对口 verify：」段。协议版本 v0.5 → v0.6，发行版 0.6.0 → 0.7.0（按既有规则，交付契约层面的字段改动属流程语义变化）。
- 已执行（文档静态检查）：全包 16 份 Markdown 共 53 条相对链接全部解析、0 断链；`SKILL.md` 路由表八个入口与 `references/` 下对应文件一一相符（`installation`、`workflow` 由路由规则内联引用，不进路由表）；`release.json`、根 `README.md`、`SKILL.md`、`workflow.md`、`assets/handoff.md` 五处版本字样一致（0.7.0 / v0.6）；旧措辞在正文零残留——「轻量需求」「轻量模式」「初步分档」「简短索引」「不复审代替裁决」「通常跳过」「建议不要跳过」均为 0 命中（`tests/` 历史记录除外），`quick` 仅存于历史记录；两处被收归的模板句在 `cohestra/` 下 0 命中；`agents/openai.yaml` 删除后全包零引用、目录已移除。正文改动 16 文件（+96／−103，净 −7 行）；`tests/` 另追加 12 行记录，合计 17 文件 +108／−103。
- 未执行（如实列出）：未用 skills CLI 做 0.7.0 的安装或更新实测；本轮五类改动均未在独立智能体会话中实跑；`$cohestra verify` 在真实任务中的首次执行记录仍缺；未做从 design、code、fix 起步的真实任务调用；未做远程安装验证。
- 待补证据：一次真实任务中 verify 交付并写入 `verify-<轮次>` 索引行的记录；一次 need 提问与用户确认的实际记录；一次用户选择跳过 verify 并记录理由的实际记录。
- 规模说明（如实）：本版目标是消除重复与歧义，不以缩短篇幅为目标。技能包正文（`SKILL.md`＋`references/`＋`assets/`）中文由 13,548 字变为 13,728 字（+180），因为同期新增「术语」小节与多处澄清；根 `README.md` 由 2,540 字符降至 2,046 字符（−19%）。因此净行数仅 −7，审前评估中「可减 55–70 行」的估计**未达成**——去重腾出的篇幅被新增的术语与澄清占用，本版的实得是「同一条规则不再写两遍」，而非篇幅缩短。
- 未做替代：本版结论仅来自文档静态检查，未用桌面推演冒充 CLI 实测或独立智能体实测，未改动业务项目与真实用户安装。

## 0.7.0 补充：README 双语化（发行版与协议版本不变）

- 变更：根 README 拆为双语版——`README.md` 改为英文并作为默认首页，原中文内容迁入新增的 `README.zh-CN.md`；两版顶部各有语言切换行，维护段各自写明「改一版需同步另一版」。中文版是原文件的迁移而非重写（逐行比对确认除语言切换行与维护段新增的一句同步说明外无改动）。英文版指出所链接的技能包文档目前仍为中文，并说明调用示例中的指令参数保持中文的原因。按既有规则「措辞与呈现变化不改版本号」，本次不动 `release.json`：发行版仍 0.7.0，协议仍 v0.6。
- 已执行（文档静态检查）：全包 17 份 Markdown 共 71 条相对链接全部解析、0 断链；中英两版结构对齐——标题层级序列、表格行数与列数、两个代码块内容逐字一致，16 条相对链接的目标集合相同（唯一差异为语言切换那一对，属预期）；版本字样现分布于 6 个文件（由原 5 处增加 `README.zh-CN.md`），逐处命中 0.7.0 / v0.6；两版互链可达。
- 同轮修正：双语 README 的调用示例占位符与阶段文件对齐——design 的 `参考：<截图或现状链接>` 改为 `参考：<截图、现状链接或设计规范>`，code 的 `参考：<相关文件或接口文档>` 改为 `参考：<相关文件、接口文档或截图>`；其余六处（need、review、fix、validate、verify）比对后本已逐字一致。
- 未执行（如实列出）：英文版由中文版改写，未经英语母语者或独立审校；未用 skills CLI 实测（README 不属安装内容）；未在 GitHub 或任何渲染器中查看实际排版。
- 未做替代：未用机器翻译直出，也未用文件复制冒充双语维护；结构对齐与链接解析由脚本实测，不是目视核对。

## 0.8.0 本地验证记录

- 变更：新增**自动衔接**规则——上一阶段交付后用户不带输入直接执行下一阶段命令时，自动带上上一阶段 handoff。四类改动：① `references/workflow.md` 第 1 节新增自动衔接条款（仅接续已有任务、链条上有实际上游交付的阶段调用；仅当任务目录能唯一确定——本会话刚完成上一阶段、此前已明确任务目录，或目标项目只有一个任务——才取被调用阶段上游中链条顺序最靠后的已有交付阶段之最近一轮作上游输入，上下游与先后按六阶段链条顺序判定、同阶段取轮次最大的已交付一轮、跳过 verify 交付与「草稿／进行中」文件、不按文件编号或修改时间取舍；重跑较早阶段时作为动因的下游交付可作补充材料引用、不得冒充上游依据；上游无交付、任务目录无法唯一确定或多候选并列时报告缺口请用户指定，不新建替代任务；`init`／`verify`／`need` 均不适用（init 不在六阶段链条内，verify 选对象从其说明既有规则，need 输入按第 1 节原条）；显式后附 handoff 或任务目录时以显式输入为准；自动衔接只定位输入材料，其中建议与待决定事项仍按未确认处理），并在「术语」小节补「自动衔接」词条。② 第 5.10 条交付回复闭环：派发命令带上 handoff 路径可直接执行，用户不带输入直接执行时按自动衔接条款接管。③ `SKILL.md` 调用说明补「未附 handoff 与任务目录时按公共流程第 1 节的自动衔接规则取用」。④ `assets/handoff.md`「输入与上游依据」占位说明补自动衔接取用时的填法。刻意不动：7 份阶段说明的「调用」片段保持显式形态（不加可省略输入的重复说明行），`verify.md` 的「最近一轮」规则不变。协议版本 v0.6 → v0.7，发行版 0.7.0 → 0.8.0（输入定位属协作语义变化）。
- 已执行（文档静态检查）：全包 17 份 Markdown 共 73 条相对链接全部解析、0 断链（较上版 +2，为 `SKILL.md` 新增的公共流程链接与自动衔接条款内指向 verify 说明的链接）；`assets/handoff.md`、`assets/task-index.md` 两份模板仍为 0 相对链接；版本字样分布仍为 6 个文件，逐处命中 0.8.0 / v0.7（`release.json` 的 `protocol_version` 为 `0.7`）；`tests/` 历史记录外旧字样 0 残留；场景表新增「不带输入直接跑下一阶段」「重跑较早阶段」「verify／首次 need 边界」「任务目录无法唯一确定」四行。
- 同轮修正：经同会话文档审查指出两处语义缺口后收窄规则——① 补适用范围：`verify` 与首次 need 不被自动衔接接管（否则无输入 `$cohestra verify` 会与 verify 说明「最近一轮实际交付与其直接上游」的选对象规则撞车，无输入 `need` 会错取 handoff 当需求来源）；② 「最近一份已交付」改为「上游中链条顺序最靠后的已有交付阶段之最近一轮」：各阶段轮次独立编号、文件名不表先后，原口径既未定义「最近」又与「不能凭文件编号、修改时间或『最新』推断」的既有禁令表面冲突，重跑较早阶段（fix 后再次 code）时还会错取下游交付。同会话审查不构成独立审查。
- 同轮补齐（可选项，依用户指示纳入）：① 术语「自动衔接」尾补「只选择输入材料，不推进阶段，也不替代用户显式调用下一阶段」，与执行规则 5 禁止的「自动继续」划清边界；② `SKILL.md` 调用说明原「上一阶段刚完成时可不附 handoff」比所引规则窄（条款允许三种情形），改为「未附 handoff 时按公共流程第 1 节的自动衔接规则取用」，口径与条款对齐。
- 同轮二修（第二轮同会话审查新增四条后收口）：① 排除条补 `init`——无参数 `$cohestra init` 是正常用法，不应被 `SKILL.md` 的统一表述带进自动衔接再报「上游没有交付」（空项目与单任务项目各推演一次）；② need 输入规则去重：排除条只留边界并指向第 1 节原条，「首次 need 以原始需求为输入」不再在排除条与术语条重复；③ `SKILL.md`「未附 handoff 时」改「未附 handoff 与任务目录时」，只附任务目录时以显式输入为准、不误触发；④ 重跑较早阶段补「作为动因的下游交付可作补充材料引用，不得冒充上游依据」，避免交付物「输入与上游依据」与真实动因不符。同会话审查不构成独立审查。
- 未执行（如实列出）：自动衔接未在独立智能体会话中实跑（含「跳过 verify 与草稿」「多任务并列请指定」两个分支）；未用 skills CLI 做 0.8.0 的安装或更新实测；未做远程安装验证。
- 未做替代：未用桌面推演冒充智能体实测；自动衔接的行为结论以文档规则为准，实跑证据留待补。

## 0.9.0 本地验证记录

- 变更：新增**机器可读契约（Orchestrator Contract）**，让外部 Task Orchestrator 不解析正文即可判断任务状态、阶段结果、候选、受阻、下一阶段与是否允许继续；Cohestra 仍保持一次调用只执行一个阶段、阶段结束即停止，不新增 queue、batch、run-all、night-run、scheduler 等多任务调度入口。四类改动：① `references/workflow.md` 新增第 7 节——7.1 载体与单一状态源（任务 README 的 YAML Front Matter 是唯一可变控制状态，正文与 handoff 保持人类可读，handoff 仍是不可变历史；禁止 state.json／status.json／runtime.json 第二状态源；verify 交付不改控制字段、init 不写契约；YAML 恒可解析，缺失或不合法由调用方判为协议输出不合法）；7.2 字段（task、status、execution_mode、stage_result.{stage,status,round}、candidate.{commit,snapshot}、findings.{blocking,non_blocking,unresolved}、acceptance.status、next.{stage,allowed,reason}、blocked.{value,reason}，与 cadra 第 6 节契约字段名逐字对齐，多出的字段为增量扩展；status 只取 in_progress／completed／blocked／failed，不引入 draft／ready／queued／running；blocked.reason 七值为 human_decision_required／missing_input／missing_permission／dependency_unavailable／environment_blocked／candidate_unavailable／other）；7.3 next 标准化（所有正式阶段交付后必须给出 next，给出六阶段出口映射表——review blocking=0 转 validate、blocking>0 转 fix 并写 blocking_findings、validate 仅 passed 且满足既有完成条件才 status=completed 且 reason=task_completed、受阻一律 next.allowed=false；正文「推荐下一步」须与 next 一致；blocked.value=true 时 next.allowed 必为 false）；7.4 执行上下文 unattended（不提问空等、不自行选择产品方向、不扩大范围、不产生新的隐含授权、不降低质量门禁，无法合法继续时 stage_result.status=blocked＋blocked 枚举原因＋next.allowed=false 后停止）；7.5 向后兼容（旧任务无 Front Matter 可继续读取、不批量迁移、首次写入时最小加入结构化状态、不重写历史 handoff、不重跑旧阶段）。术语表补「结构化状态（Orchestrator 契约）」「执行模式」；第 5 节落盘顺序改为固定七步（阶段完成 → 写 handoff → 回读 → 更新 Front Matter → 更新正文索引 → 回读 → 停止），README 更新失败时逐字报告 `handoff completed`、`index sync failed` 并注明机器状态停留在上一轮。② 模板：`assets/task-index.md` 加 Front Matter 骨架（全部字段、枚举与缺省约定，说明每个字段只写一个实际值），`assets/handoff.md`「身份与输入」加「执行模式」行。③ 阶段说明：review 输出 findings 结构化计数（blocking>0 即必做整改，next 指向 fix 并写 blocking_findings），fix 按裁决与修复更新未关闭计数，validate 给出 acceptance.status（passed／failed／pending／blocked，仅 passed 且满足既有完成条件才判任务 completed）。④ `SKILL.md` 协议字样 v0.8、执行规则增第 7 条（结构化状态写入、正文与 next 一致、不含多任务调度入口的边界声明）与第 8 条（unattended 语义）、描述元数据补机器契约提示；`release.json` 发行版 0.8.0 → 0.9.0、协议 v0.7 → v0.8（契约字段属交付契约层面的流程语义变化）；根 README 双语同步（cohestra 段补机器契约说明与「一次调用一个阶段、不含队列与调度」边界，维护段版本字样）。
- 已执行（文档静态检查）：全包 17 份 Markdown 共 100 条相对链接全部解析、0 断链（本版改动净增 7 条；0.8.0 记录的 73 条与此刻 93 条基线之差来自其间并入 cadra 导致根 README 等文件增加的链接，不属本版）；版本字样 6 处一致（release.json 0.9.0／0.8，SKILL.md、workflow.md、assets/handoff.md、README.md、README.zh-CN.md 均 v0.8／0.9.0），旧字样 v0.7 与 0.8.0 在上述文件 0 残留；契约字段名与 `cadra/references/workflow.md` 第 6 节逐字比对一致（task／status／stage_result.{stage,status}／next.{stage,allowed,reason}／blocked.{value,reason}）；next.reason 八值、blocked.reason 七值、acceptance.status 四值、status 四值在 workflow.md 第 7.2 节与 task-index.md 骨架两处逐值一致；`cohestra/` 下无 state.json／status.json／runtime.json；queue／batch／run-all／scheduler 字样仅出现在「不含多任务调度入口」的否定式边界声明中，未新增对应入口。
- 已执行（桌面推演）：任务书八场景（code 完成 → next=review；review blocking=0 不要求 fix；review blocking>0 → next=fix；validate acceptance=passed → 任务 completed；unattended 缺人工决策 → blocked 且 next.allowed=false；环境阻塞 → blocked；README 写入失败 → 报告 handoff completed／index sync failed；旧任务无 Front Matter → 读取成功、首次写入最小升级）加「外部编排只读控制流」「Front Matter 唯一状态源」「verify 不改控制字段」逐条推演，结果与场景表一致。
- 未执行（如实列出）：未在独立智能体会话中实跑任何一次带 Front Matter 的阶段交付；unattended 语义未实跑；未用 skills CLI 做 0.9.0 的安装或更新实测；未做远程安装验证。
- 待补证据：一次真实任务中「阶段完成 → 写 handoff → 回读 → 写 Front Matter → 同步正文 → 回读」的完整记录；一次 unattended 缺人工决策的受阻记录；一次 README 更新失败的 `handoff completed`／`index sync failed` 报告记录。
- 遗留事项：① 消费侧「接口现状声明」已由并行 cadra 改动就地更新（`cadra/references/workflow.md` 现记「Cohestra v0.8 起在任务 README YAML Front Matter 提供 Orchestrator 契约」），本条原「将过时」表述随同轮整改一并修正（见 0.9.0 同轮整改 F9b）；cadra 侧其余口径仍归 cadra 任务，本次未触碰。② 本验证记录落盘时工作区内 `cadra/` 与 `tests/cadra-scenarios.md` 另有并行未提交改动，非本任务产生、未触碰，静态检查中涉及 cadra 文件的比对基于当时的磁盘内容。
- 未做替代：未用桌面推演冒充智能体实测或 CLI 实测；契约字段与枚举以文档规则为准，实跑证据留待补。

## 0.9.0 同轮整改（独立审阅 findings）

仍在 0.9.0 发行内（本版尚未发布，契约补缺不另起版本）。阻塞三条（F1/F2/F3）与流程一条（F10）逐条处置，非阻塞五条（F4–F9b）除消费侧一条外一并整改：

- **F1（P0，完成语义矛盾）**：`workflow.md` §7.2 补 `status` 写入规则并把「仅 passed 才 completed」限定为「validate 交付时」；§7.3 新增「用户声明的终点已到达」行（`next={stage: null, allowed: false, reason: task_completed}`、任务 status → completed、acceptance 可缺省），并注明 `task_completed` 两来源（validate 通过／终点到达）、终点前提（阶段自身交付完成、必做问题未关闭不按终点收尾）与优先级（受阻、失败路径优先）。链条外终点的任务（review-only、small-change 于 code／review 收尾）由此可合法写 `completed`，且与消费侧「completed + acceptance 缺省 → 标注 unknown」的口径衔接。
- **F2（P1，无版本标记）**：§7.2 增必填字段 `contract: "0.8"`（取当前协作协议版本、随协议演进），消费方可核对版本；§7.5 明确向后兼容指「可读取、可继续使用」，契约就绪与否由消费方按 `contract` 或探测判定，无 Front Matter 视为「契约未就绪」，兼容声明与版本核对不再冲突。
- **F3（P1，必填/可选冲突）**：§7.2 新增「必填与可选」条——必填集 `contract`／`task`／`status`／`execution_mode`／`stage_result`／`candidate`／`next`／`blocked`（每次正式阶段交付全部写出），可选集 `findings`（review/fix）、`acceptance`（validate）、`findings.unresolved`（缺省等价 `null`）；「协议输出不合法」只针对必填集；最小写入同样给出完整必填集、只含本次值。7.1 的「核心字段」措辞改为「必填字段」，三处规则（恒写出／可省／最小写入）的冲突消除。
- **F5（P2，status: blocked 空转）**：补写入规则——`blocked.value: true` 时任务 `status` 同步写 `blocked`，受阻解除后回 `in_progress`；§7.3 受阻行、§7.4 受阻路径、SKILL 规则 8 与场景表同步。
- **F6（P2，candidate 形状不唯一）**：统一「恒映射、叶子可 null」——无候选写 `candidate: {commit: null, snapshot: null}`，§7.2 与模板同步，取消 `candidate: null` 写法。
- **F7（P2，模板占位符歧义）**：`assets/task-index.md` 占位符统一为 `<a|b|c>` 单值占位并加说明（无值叶子写 `null`），拷贝未填时不再产出「语法合法、取值非法」的 YAML。
- **F8（P2，unattended × verify 单边）**：§7.4 与 SKILL 规则 8 补齐握手——unattended 下 verify 提议按跳过处理并记入交付物（理由 unattended）、不改控制字段、不降低也不替代 review／复审／验收要求，与消费侧既有处置对称。
- **F4（检查方法缺口）**：原「契约字段名与 cadra 第 6 节逐字比对」只覆盖 task／status／stage_result／next／blocked 五组键，恰好漏掉 `acceptance`——正是并行实现自造 `accepted` 的位置，该口径不可能发现该偏差。整改后比对口径改为**契约键全集**（含 `contract`、`execution_mode`、`candidate`、`findings`、`acceptance` 及全部子字段）在 `workflow.md` §7.2 与 `task-index.md` 两处逐键核对，并核对消费侧载体（`cadra/references/workflow.md` 契约段引用的字段名）。
- **F9（消费侧，不改）**：cadra 终态表第 2/3 行（completed + acceptance failed／pending）在 cohestra 语义下仍不可达（validate 未通过／未决不写 completed），属消费侧防御性行；F1 整改后第 4/8 行（completed + acceptance 缺省、以 flow 边界收尾）恢复可达。cadra 口径归 cadra 任务，本次不触碰。
- **F9b（记录漂移）**：本文件 0.9.0 记录的「遗留事项①」已就地更新（见上文）。
- **F10（候选未冻结）**：仓库规则要求提交需明确授权，本轮未获授权，候选以工作区相对 `HEAD`（7b9e57f）的 `git diff` 为可复核快照，整改前后均可复核；建议授权一次提交冻结候选后再做终验，本轮不以文档改动冒充已冻结候选。
- 已执行（文档静态检查，整改后复测）：全包 17 份 Markdown 共 100 条相对链接全部解析、0 断链；契约键全集（20 键含子字段）在 §7.2 与模板逐键一致；`next.reason`／`blocked.reason`／`acceptance.status`／`status` 全部枚举值两处一致；`contract`、版本字样 6 文件一致；`cohestra/` 下仍无第二状态源文件。
- 未执行（如实列出）：整改内容未在独立智能体会话实跑；消费侧联调（cadra run 探测与终态判定）未实测；仍未用 skills CLI 做安装/更新实测。
- 未做替代：逐条整改以文档规则为准，F10 以可复核快照记录而非宣称候选已冻结；桌面推演不冒充实测。

## 0.9.0 四项修复验证（2026-10-01）

本节补充本轮结果；前述同版记录保留原事实，旧的分步 README 更新与“状态必然停留在上一轮”口径由本轮规则取代。发行版仍为 0.9.0、协议仍为 v0.8；没有提交、推送、发布或升级真实安装。

- 修复：① validate 缺必要复审且可执行时输出 `acceptance=pending`、`next={review,true,stage_completed}`；已确认验收失败仍转整改，复审或补证据条件不足则受阻。② README 的 Front Matter 与正文完整准备、校验后写同目录临时文件、核对原文件未变、原子替换并回读；临时文件不作状态源、不替代单写入者。③ 发布或回读失败后报告 `handoff completed`、`index sync failed`，实际状态区分旧版（或未创建）/ 新版 / 无法确认；即使新版可读也要求消费方恢复核实后再继续。④ 旧任务仅在首次正式阶段交付成功同步时加入契约；verify 不触发迁移，已有控制字段原值保留。handoff 中记录写入时“待同步”，最终同步结果由回复报告，不回写已交付文件。
- 文档静态检查：两技能与测试、根双语 README 共 30 份 Markdown、158 条相对链接，0 断链；生产契约与索引模板的 18 个叶子字段逐键一致，状态与原因枚举一致；契约版本按字符串解析、轮次按整数、布尔按布尔、candidate 恒映射。两技能元数据及当前发行/协议字样通过检查，release.json 相对本轮开始未变；`git diff --check` 通过。
- 文件操作实测（隔离临时目录，6/6）：完整发布、首次创建、临时文件写入失败、原子替换失败、替换前并发修改、替换后回读失败。写入与替换失败通过临时文件/目录权限触发实际 `PermissionError`（errno 13），正式 README 保留旧版；并发修改保留另一写入者内容；回读失败通过替换后禁止读取触发，恢复权限后确认正式文件为完整新版。各分支无 Front Matter/正文混合版本，handoff 保留，本执行者临时文件已清理；失败信号不因读取到新版而取消。该结果验证文件操作方法，不证明任意环境均具备相同工具能力。
- 阶段输出夹具演练（同会话、脚本辅助落盘，6/6）：整数加法候选的 `add(2,3)` 实际执行；正确候选但缺必要复审 → pending/review；复审权限未授予 → blocked/missing_permission；错误候选实际返回 -1 → failed/fix（不被缺复审改写为 pending）。三份 validate-01 写出五节交付与完整契约，候选内容未变，未执行 review/fix。旧任务 verify-01 仅更新正文；design-02 才加入本轮契约；随后 attended 的 verify-02 保留先前 unattended 契约全部原值，旧 need/design 文件摘要未变。YAML、完整发布及回读核对通过；这不是实际独立智能体调用或真实业务任务验收。
- 消费侧桌面推演：18 个终态分支与 6 个本次结果核对分支通过，详见 cadra 场景记录；必做后续超出 flow 不完成，阶段轮次不跨阶段比较，同步失败不消费旧 next。
- 工具限制与未执行：原生 `skill-creator/scripts/quick_validate.py` 因当前 Python 缺少 PyYAML 未完成；未安装依赖，采用 Ruby Psych 解析 YAML 并检查等价基本元数据。未执行独立智能体阶段调用、cadra 真实 run/resume 联调、skills CLI 安装/更新或远程验证。夹具演练、映射模型与文件操作实测各自报告，不互相替代。

## 0.10.0 只读 report 验证（2026-10-15）

- 变更：新增 `$cohestra report` 查询入口与专用说明，默认展示当前项目全部任务、遗留问题和状态异常；已完成任务的未关闭项保留。结果只在对话中输出，明确豁免初始化、阶段落盘、索引写入、自动衔接和推进，不改变延期与关闭规则。同步路由、项目入口模板与双语导读。
- 兼容性：发行版 0.10.0，协议保持 v0.8。相对 HEAD 核对公共流程第 7.2 节起的字段、出口、unattended 与兼容规则，以及八份原入口说明、任务索引和 handoff 模板，内容均未变；Cadra、Relatra 未改。report 不进入 stage_result / next 的阶段枚举。
- 已执行（文档静态检查）：18 份 Markdown、122 条相对链接，0 断链；九个入口均能定位说明。双语 README 标题层级、表格结构、相对链接目标（语言互链除外）、Cohestra 调用代码块与版本字样一致。`git diff --check` 通过。Ruby Psych 解析 SKILL Front Matter 并检查名称、描述类型/长度及允许键通过；默认与捆绑 Python 的原生 quick validator 均因缺 PyYAML 未运行完成，未安装依赖。
- 已执行（隔离文件检查）：完整技能包复制到临时迁移路径后，20 个文件（含隐藏模板文件）逐文件摘要一致，九个路由文件可达；临时副本已清理。这是打包与迁移完整性检查，不是 skills CLI 安装/更新或 report 调用证明。
- 已执行（同会话文档桌面核对）：核对缺容器、缺目录与空目录的不同出口、completed 遗留项、可选字段未知、旧任务/契约异常、多轮 ID 合并、计数冲突与覆盖缺口的处理边界。只记录规则核对，不宣称实际 report 输出或文件零副作用已通过行为实测。
- 未执行：独立智能体 report 调用及调用前后文件副作用检查、skills CLI 安装/更新、远程验证；未更新真实已安装副本，未提交、推送或发布。

## 0.10.0 report 实际调用补验（2026-10-15）

本节补足上一节当时尚未执行的 report 行为验证；保留前述历史记录，不改变技能规则或发行版本。

- 实际调用：独立子智能体 `/root/report_actual_call` 在新上下文中显式加载本仓库 Cohestra，对隔离项目执行 `$cohestra report`；未向执行者提供期望答案。夹具脚本只生成原始任务记录与文件系统快照，不生成报告。[调用、核对及复现记录](cohestra-report-validation.md)、[实际输出](cohestra-report-actual-output.md)。
- 结果：5 个任务全部展示；已完成任务的延期非阻塞项未漏报，计数为零但明细未关闭的项仍展示并标冲突。跨轮同一 finding 只保留一行有效状态，跨任务相同 ID 不合并；已关闭与已否决项不复活，第二轮已修改但待复审项保持未关闭；旧任务与可选字段缺失保留未知。人工逐项核对 10 项通过（含文件状态检查），不是汇总逻辑的模拟输出。
- 只读证据：调用前后目标项目 30 个、完整技能包 26 个文件及目录条目逐项一致；比较目录清单、SHA-256、大小、权限、inode、mtime_ns、ctime_ns，无新增、删除或变动。完整快照摘要一致，见[文件系统核对结果](cohestra-report-filesystem-check.json)。证据由父智能体在调用结束且快照核对后保存，不属于 report 写入。
- 边界：一次隔离夹具上的独立智能体实际调用，不证明全部输入与环境；不覆盖系统会话日志或全系统文件写入事件，也未实测缺容器、读取失败、并发变化等其余场景。未执行 CLI 安装/更新、真实业务项目调用、提交、推送或发布。

## 0.10.0 validate 完成状态规则补强（2026-10-15）

- 变更：本轮 validate 判 passed 后，发布前与发布后回读必须联合核对任务 completed、阶段/轮次、acceptance、next、blocked、候选与正文；冲突不得报告同步成功。验收通过但索引校验、写入、并发检查、发布或回读失败时，保留验收结论并明确报告「验收通过，完成状态待同步」，同时保留两句既有失败信号与实际状态说明。handoff 模板同步提示该报告。
- 场景：新增上述 11 组完成一致性场景，覆盖正常成功、旧任务首次写契约、状态漏写与字段冲突、写入/替换失败、并发变化、回读失败与不符，以及未通过、历史 passed、非 validate 终点和 verify 边界。场景是待执行的行为验收清单，不冒充实际阶段调用结果。
- 已执行：文档静态检查覆盖技能包、根双语 README 与本场景文件，共 18 份 Markdown、126 条相对链接，0 断链、无未闭合代码围栏；Ruby Psych 解析技能元数据并检查名称、描述与允许键通过；`git diff --check` 通过。仅补强现有完成映射的检查与失败报告，发行版保持 0.10.0、协议保持 v0.8，不新增字段、状态枚举或阶段。
- 限制：原生 `skill-creator/scripts/quick_validate.py` 因当前 Python 缺少 PyYAML 未运行完成，Ruby 检查不冒充原生校验通过。未执行独立智能体阶段调用、故障注入或 CLI 安装/更新；未修改真实任务、已安装副本，未提交、推送或发布。

## 0.10.0 validate 实际调用补验（2026-10-15）

- 实际执行：上述 11 组场景展开为 40 个隔离用例，3 个新上下文子智能体实际执行；6 个交付时间记录有误的用例由第 4 个新上下文子智能体在全新目录复跑。共 46 次阶段调用，实际产物与回复由父级只读核对，未用脚本生成验收结论。
- 结果：首轮 34 通过、6 个时间记录失败；复跑 5 通过、1 个发布顺序失败。每个逻辑用例按最后一次执行汇总为 39/40 通过，不能判为全通过。未通过的旧任务用例在 YAML 校验失败后仍发布，随后已如实报告同步失败；最终 completed 不抵消顺序违规。
- 目标状态检查：验收通过且确认索引同步成功的用例均为 completed；7 个预设同步故障分支均实际触发且报告两句失败信号及「验收通过，完成状态待同步」。未通过、历史 passed、review-only 和 verify 边界符合预期。
- 证据与复现：[实际调用记录](cohestra-validate-validation.md)、[完整原始证据与断言](cohestra-validate-evidence.json)、[输入与故障驱动](cohestra-validate-fixture.py)、[只读核对器](cohestra-validate-check.py)。两轮技能包均与当前源的 20 个文件逐文件一致；未更新已安装副本，安装前后摘要一致。未改写已交付文件，未提交、推送或发布。

## 0.10.1 串行校验关口修复与实跑（2026-10-15～16）

- 修复：发布前完整校验必须先得到并确认成功结果，随后独立调用才允许写入/发布；非零退出、缺依赖、空输出或不确定结果不继续，外层/后续命令成功不抵消子检查失败。可用备用解析器必须先重新校验成功；内容改变后旧摘要失效。入口规则同步，发行版 0.10.1，协议仍 v0.8，无新增契约字段或运行依赖。
- 实跑：原 40 个用例全部重跑，加 6 个校验关口回归；共 47 次真实阶段调用，按最后一次有效执行汇总 46/46 通过。首轮 1 个备用工具夹具未正确表达可用性，保留其安全停止记录；明确 Python 不可用/Ruby 已可用后，用新上下文和全新项目单独重跑通过。未向执行者提供预期状态或作者判定表。
- 关键观察：校验退出 7、缺模块、解析输出为空、前置失败但日志使外层退出 0 时均无 publish 事件，原索引保留，按要求报告完成状态待同步；备用解析成功后才发布；草稿变化后重新校验。每次实际发布都有更早的成功解析记录，且字节摘要一致。
- 交付：[修复与实际验证报告](cohestra-validate-0101-validation.md)、[完整证据及安装核验](cohestra-validate-0101-evidence.json)。原生技能校验器通过；PyYAML 仅在临时目录用于校验。skills CLI 1.7.2 已定向更新用户级 Codex 副本，安装版本 0.10.1/协议 0.8，20 个文件与已测试源一致。旧失败记录保持不变，未提交、推送或远程发布。

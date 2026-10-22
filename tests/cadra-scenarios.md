# Cadra 验证场景

当前验收口径为 0.6.0 / v0.6。技能本身无脚本运行依赖；下面的模型测试不是调度运行时，也不能代替实际智能体调用。后面的 v0.3–v0.5 记录只保留历史事实，不作为现行兼容要求。

## 结构与接口

- 六入口可发现，按需加载；状态解析、Gate、契约、预算和恢复只有一处权威定义。
- Task 保存 revision、preparation、定义及 Gate，Run 保存有序任务数组、previous_run、定义快照、调用与结果；没有独立队列文件或 Task 执行状态副本。
- flow 首项加允许集合，preset 与等价列表一致；未知阶段与空值拒绝，后续重复去重，不限制中间链序。
- Markdown 链接、元数据、模板字段、版本与契约匹配；双语说明内容对应，不锁定措辞或排版数量。
- .yuzio 本机存储、忽略规则、正式总结范围保留；旧协议停止相关操作，不迁移、不双写、不覆盖。

## 行为场景

| 场景 | 预期 |
|---|---|
| add/ready | 只写定义与准入；八项 Gate；未完成 Run 所属任务不编辑 |
| 普通串行执行 | Run 固定顺序；只写 Run 执行状态；默认失败继续，策略停止时未执行项 skipped |
| 来源链 | 显式 previous_run；分叉、缺失、循环、重复 slug、修订倒退停止；不以时间选来源 |
| 新定义与依赖 | 旧 completed 不放行新修订；开始与续跑前重核依赖 |
| Flow | 等价 preset/列表同结果；正常范围边界收尾，必做后续超范围 blocked；复审不按列表位置推进 |
| 相同结果 | 无额外提前停止，允许契约许可且预算内的重试或补证 |
| 三项预算 | 重试 2、整改 3、调用 16；第三轮 fix 后仍可复审；第 16 次刚完成时保留完成结果 |
| 契约核对 | 缺字段、错 task/模式/阶段、旧轮次、同步失败停止；跨阶段独立轮次合法 |
| 中断边界 | Run 建立后、调用意图后、Cohestra 交付后、结果已写但 Run 未收尾分别恢复 |
| 派发不明 | 旧契约不证明未调用；无确证停止，只有明确未发起才沿用原 call id |
| 重复 resume | 已结束项不重跑，预算不重复消费；只补收尾，不重开结束 Run |
| 定义连续编辑 | 未入 Run 的同修订累计变更；requirement/flow 曾变更从新 start 起步 |
| skipped 与修订 | 未调用不消费授权；重新核对原准入；跨 skipped 修订累计变化不丢失 |
| 首调用前受阻与修订 | blocked/failed 无调用且未消费时不截断累计变更；仍核对原因解除；后续仅改策略也保留未执行的 requirement/flow 重启 |
| 执行依据 | prepared 意图须核对而非跳过；合法无调用收尾可作为依据；缺少消费证据不推定未启动 |
| 普通调用与特殊授权 | 普通调用及普通核对收尾可保持 authorization_consumed=false；失败后策略修订仍能找到执行依据 |
| 首调用前 running 中断 | 无调用、零预算、未消费且可证未派发时重核 start_action；准入失败或派发不明不调用；已有 prepared 只核对原调用 |
| Flow 起点改变 | allowed 相同但 start 改变仍使 Gate 失效；只有 start 与 allowed 都相同才等价 |
| 非法控制枚举 | next.reason、blocked.reason、acceptance.status 非法时 failed；缺省/null 的可选 acceptance 合法；不闭合调用或推进 next |
| 显式恢复 | 新 Run 引用旧来源，原 Run 不变；解除证据、旧调用核对及一次授权必需 |
| 历史报告 | 新成功不覆盖旧失败；新修订不改旧定义和报告，缺材料 unknown |
| 原子保存失败 | 原目标不被半写文件替换，回读失败不推进；无跨系统事务承诺 |

## 本轮证据

现行静态检查：`python3 -B tests/cadra-static-checks.py`。行为模型：`python3 -B -m unittest discover -s tests -p 'test_cadra.py' -v`。实际智能体执行及限制见 [v0.6 验证记录](cadra-v06-validation.md)。历史 v05 脚本与结果仅作历史模型，不是当前验收入口。

## 历史验证记录（非现行规则）

## v0.3 首次启动、恢复与历史回归

| 场景 | 预期结果 |
|---|---|
| 新任务 full / small-change / bugfix | 所选 Cohestra 支持契约，且无 README、正式 handoff、既往调用时分别首次调用 need / code / fix |
| 仅目录不存在或 README 不存在 | 不能单凭一项判断首次启动；还须核对正式交付与调用历史 |
| README 缺失但已有 handoff/调用 | 停止前置检查，不当作新任务；Task 不变、无新 Run/队列行 |
| 旧 README 无契约、契约版本不支持或实际技能不支持 | 停止，不用源仓库规则代替实际加载副本、不补写契约 |
| 首次调用后无契约/错阶段/同步失败 | 该 Task failed，记录调用前无状态与错误，不推进 |
| 恢复参数未在显式范围内，或搭配空范围/全部 ready | 拒绝本次参数，不改文件、不建 Run |
| 恢复选择 ready/completed 或不存在任务 | 拒绝，不把正常任务或已完成任务当重试 |
| 原 Run 包含 blocked/failed 后 completed | 保留 Run 结束事实；补齐条件、显式选择恢复后建新 Run，原结果/队列行不变 |
| 恢复 Gate 或原因解除核对失败 | 原 Task 仍 blocked/failed，该项不入队；无合格项时不建 Run |
| 存在未完成 Run 时恢复 | 停止，先 resume 续跑/收尾，不出现第二个未完成 Run |
| Cohestra blocked/failed 且最近阶段同为 blocked/failed | 阶段与原 checkpoint 一致、在 flow 内、条件解除后允许首个恢复重试一次；调用前保留旧状态 |
| 最近阶段已 completed 但任务仍 blocked/failed | 不能套用失败阶段重试；只使用经核实的合法 next，或证明已完成后核对收尾，无合法动作则停止 |
| 恢复的新输出仍 blocked/allowed=false | 新 Run 记 blocked，不再次用旧恢复授权绕过限制 |
| 恢复已消费授权后中断 | 先核对调用前记录与本次交付，不重复首个恢复调用 |
| 同步失败但新版完整交付可确认 | 新 Run 记录恢复核对，按合法 next 接续或核对收尾；不重跑已交付阶段、不改原 Run |
| 源 Run 缺 checkpoint 或控制状态无法确认 | 停止，列历史材料缺口，不补造记录或自动迁移 |
| 未完成 Run 中编辑 queued/running Task | Task、Run、队列字节不变；提示先 resume 收尾 |
| 收尾后的定义编辑 | requirement/dependencies/flow/execution policy 修改回 draft 并保留旧 Gate/执行历史，随后重新 Gate |
| Gate 复核失败 | ready → draft，追加失败事实，旧通过记录仍存在 |
| 多 Task checkpoint | 分别保存调用前状态、调用原因、同步、轮次及闭合标志，后任务不覆盖前任务 |
| 新 Run 成功后重报旧 Run | 旧报告仍按旧结果快照计 blocked/failed，候选与 acceptance 取旧固定来源；新成功另列补充 |
| 旧 Run 无快照且历史证据不足 | 缺失项 unknown，不把当前 README 的成功当作旧 Run 成功 |

## v0.4 修订重启、执行边界与重试上限

| 场景 | 预期结果 |
|---|---|
| 终态任务定义修订 | requirement/dependencies/flow/execution policy 变更 → 回 draft 并追加 rev 记录（变更字段与原因、旧定义快照引用、原 Run、原终态）；旧 Run、队列行与历史报告不变；只改 title/priority 不回退 |
| 修订后重新 Gate | draft → ready，旧 Gate 与执行历史保留；修订后的 ready 不进入恢复列表，同一任务不同时走两条路径 |
| 修订重启起点：requirement/flow 变更 | 原终态 completed 或（原因已解除的）blocked/failed → 调用新 flow 首项一次，原因记「修订重启 rev-N」；不消费旧 next、不用旧 acceptance 作新结论 |
| 修订重启起点：仅 dependencies/execution policy | 原终态 blocked/failed → 核对后重试原 checkpoint 待调用阶段一次；原终态 completed → 不调用阶段，修订收尾，旧验收继续有效 |
| 修订重启准入未通过 | 缺 rev 记录、定义与记录矛盾或原因未解除 → Task 保持 ready 不入队，记录缺口；不把修订当作绕过旧受阻状态的通道 |
| 修订重启授权与历史 | 首个调用落盘前记已消费，一次修订只给一个起点；旧 Run 的 blocked/failed/completed 不被改写，报告同时标注 rev-N 与原终态 |
| 执行模式核对失败 | 声明 unattended 而契约记为 attended（或字段缺失、非法）→ 本次结果不成立，Task 记 failed，即使 next.allowed=true 且阶段在 flow 内也不推进；列入需人工介入 |
| 非 Git 目标、目标不明或不可安全写入 | run/resume 前置检查停止：不建 Run、不入队、不代建 .yuzio/cohestra、不执行 git init |
| Git 工作区缺 .yuzio/cohestra | 不作为停止条件；由 Cohestra 在首个阶段调用时最小初始化，Run 与 Task 记录标注“本轮需先初始化” |
| flow 等价写法 | `flow: bugfix` 与显式 `[fix, review, validate]` 准入结果相同；`[review, fix, review]`、`[need, design, code, review, fix, review, validate]` 合法，`[review, review]`、`[fix, validate, review]`、`[validate, fix]` 拒绝；序列含阶段名即可承接对应 next.stage |
| 可重试失败达到上限 | 逐阶段失败重试预算各 2 次：该阶段第 3 次调用仍可重试失败 → 不再调用，Task 记 failed（重试上限耗尽）；预算是许可上限而非必须用满，比较字段完全相同的重复失败由无进展先停、不消费剩余额度；预算不因穿插其他阶段或某次成功返还；stop_queue_on_failure: true 时停止队列，未执行任务出队回 ready |
| 重试无进展 | 连续两次调用后 stage_result.status、candidate、findings、acceptance 与 next 全未变（轮次增加不算进展）→ 立即停止并记 failed，不等上限；validate 本阶段补证出口豁免，改由任务调用预算兜底 |
| 三项上限跨 resume | checkpoint 按阶段保存失败重试预算、整改轮与调用总数、上次核实结果与调用标识；resume 一律沿用不清零、按 run-id + slug + 调用序号去重，同一交付不重复计数；恢复与修订重启的首次调用各只允许一次并计入新 Run 预算 |
| 未消费修订的再次编辑 | draft/ready 继续编辑保留同一 rev-N 的原 Run/终态，累计字段并更新新定义快照；先改 requirement 再改 policy 仍从新 flow 首项重启 |
| 修订准入失败后补材料 | ready 保持原状态，不进入只收 blocked/failed 的恢复列表；补齐后重新 run 或继续编辑再 Gate |
| 已交付阶段的策略修订 | 仅 dependencies/policy 变更时，完整交付且 completed 的阶段不重跑；核实合法 next 或作核对收尾，无合法动作则不入队 |
| 修订收尾不调用阶段 | 结果落盘并回读后关闭 rev-N；中断只补齐同一收尾，新 Run 不重复消费；旧候选/验收标明沿用，模式按原调用记录核对 |
| 阶段切换后的失败重试预算 | 同一 Run 各阶段累计预算不因成功或穿插其他阶段返还；该阶段已追加 2 次失败重试后再次失败，不再调用 |
| resume 补闭合同一交付 | run-id + slug + 调用序号标识去重；回读或补闭合不重复计数，已落盘的预算消费不返还；缺记录或矛盾则停止 |
| 无进展与完成优先级 | 必填校验与终态映射第 1–9 行先处理，已 completed 不因结果相同改判 failed；非终态同阶段连续结果相同才停止（validate 补证出口除外）；可选字段缺失与显式 null 等价，与写有内容的映射不等价 |

## v0.5 无人值守控制上限与部分写入恢复

| 场景 | 预期结果 |
|---|---|
| 跨阶段整改循环 | review 判必做问题未关闭（blocking_findings）触发的 fix 整改轮在同一 Run 内不超过 3 轮；第 4 次不再调用，Task 记 failed（整改轮上限耗尽）；候选与 findings 逐轮变化不构成豁免 |
| 整改轮计数口径 | 只按 blocking_findings 原因累计；acceptance_failed、stage_failed 与正常新增修复不计入整改轮，也不因此获得额外额度，但计入任务调用预算 |
| 任务调用预算 | 同一 Run 内单个 Task 已发起的阶段调用总数不超过 16（含重试、整改与补证）；达到后不再调用任何阶段，记 failed（调用预算耗尽）；不调用阶段的恢复核对收尾与修订收尾不计入 |
| 三项上限互相独立 | 逐阶段失败重试预算、整改轮、任务调用预算分别计算，互不抵扣；任一耗尽即停止，受 stop_queue_on_failure 约束 |
| 预算跨 resume 与跨 Run | resume 沿用同一未完成 Run 的预算不清零；新 Run 使用自身预算；显式恢复与修订重启的首次调用计入新 Run 预算；预算耗尽后只能由用户在恢复列表中重新选择，unattended 不自动重置 |
| validate 本阶段补证 | validate-01 补 AC-1、validate-02 补 AC-2，而候选、findings、acceptance=pending 与 next=validate 全部未变 → 不判无进展；重复补证由调用预算兜底，不会无界 |
| 补证豁免的边界 | 豁免只限 validate 的 completed 自循环（next.stage=本阶段、reason=stage_completed）；其他同阶段自循环两次结果全未变仍判无进展 |
| 无进展是加速停止 | 比较字段完全相同的重复失败按无进展停止，不再消费剩余重试额度；「最多追加 2 次」是许可上限而非必须用满的额度 |
| 入队三步写入 | 入队按 Run → Task → 队列清单顺序写入，每步回读，携带同一 enq-<run-id>-<NN>；队列行存在且带该编号即入队完成 |
| 入队中断后恢复 | Run 已存在、Task 仍为入队前状态、队列缺行 → resume 按同一编号判定为同一次入队并补齐 Task 与队列行，不新建 Run、不调用阶段、不放宽 add 的归属拒绝 |
| 补齐的幂等边界 | 补齐只写尚未写入的步骤：不重复追加队列行、不重写已有结论、不动其他 Run 的行；补齐后再次 resume 判定为已完成 |
| 补齐的停止条件 | 编号缺失或无法对应、定义快照与实际 Task 不一致、入队前状态却已有阶段调用记录、同一编号多行、Run 快照与队列结论矛盾 → 停止并报告，不补写、不猜测 |
| 出队部分写入 | Run 已保存结果快照与出队结论、队列行未回写 → resume 按 deq- 编号只补回写步骤，不重复追加 |
| 旧版队列清单读取 | 当前只支持八列格式；不支持时报告状态未知与缺口，不转换、不补写、不据此放行新 Run |
| 旧清单升级方式 | 不自动追加新表头或迁移旧记录，保留原文并报告格式不支持 |
| 行定位键 | 以 enq-<run-id>-<NN> 定位，并以 run-id + slug 复核；必要编号缺失时停止 |
| 逐行完成判据 | 对应 deq- 编号、结论与时间齐全，且 Run 结果快照、Task 状态与队列行一致才确认收尾 |
| 旧记录经恢复入口可达 | 格式不支持或必要编号缺失时停止并报告，不建立无编号恢复分支 |
| 旧记录定位歧义 | 多行无法唯一匹配时停止并报告，不猜测目标行 |
| 出队三步写入 | 出队按 Run 结果快照 → Task 终态（或 skipped 回退 ready）→ 队列行 deq- 编号顺序写入并逐份回读；Run 结果、Task 状态与队列行三者一致才算收尾，未一致不放行新 Run |
| 补齐先分阶段 | 读 Run 中该 Task 有无结果快照：无 → 入队阶段按入队规则补齐；有 → 出队阶段以快照为唯一依据补 Task 终态与队列回写；不得只凭 Task 状态字面值判断——blocked/failed 既可能是入队前原状态也可能是本轮终态 |
| 终态任务出队补齐 | failed/blocked 终态在队列缺行时判为出队部分写入并补齐，不误报「入队前状态却已有阶段调用记录」；completed 补齐后不停在 running；skipped 补齐后 Task 回到 ready 并记队列结论 |
| 出队不一致的停止条件 | 快照为 completed 而 Task 为 ready 且无 skipped 回退记录、或 Task 状态与快照互不相容时停止并报告，不补写 |
| 判定顺序：先定是否需要调用 | 先按终态映射确定是否还需再调用（完成、受阻、失败与正常 flow 边界在此终止）；确需调用时才检查三项上限与无进展。第 16 次交付恰好到达正常边界时按边界收尾，不因预算判 failed |
| 整改轮只拦第 4 次 fix | 第 3 轮 fix 交付后仍按 next 正常调用必要复审；复审不消耗整改轮，随后按终态映射收尾或再判 |
| 依赖在执行窗口被修订 | 依赖原 Run 已结束、在本 Run 排队期间被 add 修订回 draft/ready → 任务开始或续跑前重核落盘状态，记 blocked（依赖未满足），不调用阶段；依赖经新 Run 回 completed 后由用户在恢复列表显式恢复本任务 |
| 同 Run 依赖链不入队 | 依赖未 completed 的任务不得入队（Gate 第 6 条与入队条件同口径）；依赖链逐层各开一个 Run，排序不含依赖优先 |
| slug 同名收养防护 | add 时 cohestra_task 目录已有正式交付 → 记录主题摘要并请用户确认对应关系；run 前置收养核对主题明显不对应 → 不接续、不入队，请用户选择（确认接续 / 更换 slug / 先人工处理） |
| 终点表达口径 | Cohestra「用户声明终点」不进契约；flow 含 validate 而验收缺省的 completed 判 blocked（终态表第 7 行），需在 validate 前收尾的任务用 review-only 或显式序列表达 |
| 契约版本同步 | Cohestra 协作协议变更时两技能同步发布；未同步前按新协议交付的契约判契约未就绪，run 前置检查停止 |

## 安装

安装走通用技能管理器（如 skills CLI），Cadra 不提供自研安装器。安装副本须包含 references、assets 与隐藏模板文件；安装本身不创建 `.yuzio/cadra`。没有对应实测时标明未实测，不能用文件复制代替 CLI 安装证据。

交付检查结果时分开标注：文档静态检查、文件/CLI 实测、桌面推演、独立智能体实测。未执行项如实列出。


## 0.1.0 本地验证记录

- 变更：首个版本。新增 `cadra/`（SKILL.md、release.json、LICENSE、references/workflow.md 与 add/ready/list/run/resume/report 六份入口说明、assets/task.md、assets/run.md、assets/project/ 容器模板）与 `tests/cadra-scenarios.md`；根双语 README 增加 cadra 导航、调用示例与安装命令。发行版 0.1.0，任务/Run 协议 v0.1。
- 已执行（文档静态检查）：全包 Markdown 相对链接解析（137 条、0 断链）、SKILL.md 路由表与 references 六文件一一对应、release.json 与各文档版本字样一致（0.1.0 / v0.1）；写入范围以提交为准可复核——`git show --stat 7b9e57f` 的文件清单不含 `cohestra/` 路径，本技能未改动 Cohestra。
- 已执行（桌面推演）：上表场景按公共流程、入口说明与模板逐行推演，规则间无冲突；Task/Run 状态机转换、排序口径与 resume 核对规则在推演中可闭合。
- 未执行（如实列出）：未用 skills CLI 做安装实测；六入口均未在独立智能体会话中实跑；Cohestra 结构化状态接口尚未就绪，run 的无人值守闭环未实测；未做远程安装验证。
- 待补证据：一次真实项目中 add → ready → run → report 的完整记录；一次中断后 resume 的实际恢复记录（覆盖不重复已完成阶段与 blocked 解锁两个分支）；契约就绪后的 unattended 串行实测。
- 未做替代：未用桌面推演冒充智能体实测或 CLI 实测；未修改 `cohestra/` 或真实用户安装，未把模拟输出写成执行证据。

## 0.2.0 修订记录

- 变更：针对独立审阅意见的 P0/P1/P2 逐条修订，契约与状态机语义变化，协议 v0.1 → v0.2、发行版 0.1.0 → 0.2.0。① **P0-1**：最小初始化限定为写入口（add/ready/run/resume/report），`list` 纯只读、容器缺失只报告“未初始化”与目标路径，消除“任意入口初始化 vs list 不写文件”的矛盾（SKILL.md 规则 2、list.md、场景表两行）。② **P0-2**：契约载体钉死为 `cohestra_task` 任务 README 的 YAML Front Matter（Cohestra v0.8「Orchestrator 契约」），字段名与取值**逐字采用 Cohestra 公共流程第 7.2 节原文**（`status`、`stage_result`、`next`、`acceptance.status`、`blocked`），Cadra 不另立别名——首轮实现曾自造 `accepted.value`，与 Cohestra 契约不符（该字段在 Cohestra 中不存在），复核后改为 `acceptance.status`；保留 `task` 与 slug 一致性校验；终态判定改写为**穷尽映射表且行序即优先级**——`status` 为终态时先于 `next` 判定，`next.allowed = false` 不得越过 failed/blocked 行（Cohestra 在受阻与不可继续时同样给 `allowed=false` + `stage=null`，首版行序会把这类状态误判为 completed，复核后已按状态优先重排）。映射结果：completed+passed → completed；completed+failed → blocked；completed 且验收无结论时按 flow 是否含 validate 分流（含 → blocked，不含 → completed 并强制标注 acceptance=unknown）；failed 或 stage_failed 不可继续 → failed；blocked 或 allowed=false → blocked；allowed=true 且 stage 在 flow 内 → 推进；allowed=true 且 stage 是六阶段名但在 flow 外 → completed（flow 边界）并强制标注与人工介入；stage 为空／非法、status 越界、task 不一致 → failed。run.md 不再自设终态口径。③ **P1-3**：新增调度回边（`queued → ready` 出队回退、`blocked`/`failed → queued` 仅经 resume）、明确「未完成 Run」定义与 **Run 收尾**（放弃续跑后剩余任务回 ready、Run 标注已收尾、不再阻塞新 Run），`skipped` 口径随之改为“本轮未执行且已出队回 ready”。④ **P1-4**：阶段调用后附 `.yuzio/cadra/tasks/<slug>.md` 并声明 requirement 为本次上游依据（feature/small-change/bugfix 中链起步不再必然缺输入）；`cohestra_task` 目录名与 Task slug 绑定并校验。⑤ **P1-5**：unattended 写入对 Cohestra 的接口要求（不交互提问、需人类决定表达为受阻）；verify 处置落定——unattended 下 Cadra 不调用 verify，记“跳过+理由”并列入人工介入清单。⑥ **P1-6**：run/resume 前置 cohestra 技能可用性检查，缺失一次性报告缺依赖。⑦ **P2**：最小初始化绑定容器模板并补半初始化最小补齐；新增 `queue/order.md` 模板（七列定义，缺失不算缺口）；`.gitignore` 删除永不匹配的 `/runs/*/scratch/` 规则；§4.4 标注为非法状态兜底；preset 首项改为“声明的期望起始阶段”并要求显式序列为链序单调子序列（add 校验）；定义报告轮次（与 Cohestra 阶段轮次无关）；tests 标准放宽为“公共规则只引用、不重复定义”并清理 run/resume 复述；list 展示队列位次与出队结论；验证记录改用 `git show --stat` 可复核表述。
- 已执行（文档静态检查，复核轮实测）：cadra 包内 12 份 Markdown、59 条相对链接、0 断链（全仓 30 份、159 条、0 断链；全仓数字随 cohestra 侧并发改动浮动，故以包内数字为准，首轮记录的“152 条”不可复现已修正）；SKILL.md 路由表与 references 六文件一一对应；`release.json`、`SKILL.md`、`workflow.md`、双语 README 的版本字样一致（0.2.0 / v0.2）；契约字段与 Cohestra v0.8 第 7.2 节及 `assets/task-index.md` 骨架逐值比对（`status` 4 值、`stage_result.status` 3 值、`next.reason` 8 值、`blocked.reason` 8 值、`acceptance.status` 4 值），自造字段零命中（首轮自造的验收字段名已全部替换为 Cohestra 原生的 `acceptance`）；终态映射表与各入口引用无互相矛盾的旧口径（“状态保持 queued”“是终态，回到队列”等字样零命中）；双语 README 标题层级（6）、表格行数（19）、表格数（3）、代码块数（3）逐一对齐。
- 已执行（桌面推演）：上表新增场景（终态映射各分支、出队回退、Run 收尾、verify 跳过、中链起步输入、半初始化补齐）逐行推演可闭合；resume 三分支与调度回边不冲突。终态映射另做脚本枚举：按 Cohestra 第 7.3 节标准化出口与边界态共 17 类输入逐条套用映射表，结果与预期一致，假完成／假 blocked 0 条（含两项回归：受阻态 `allowed=false` + `stage=null` 不再被判 completed；`allowed=true` 但 `next.stage` 为空或非六阶段名判 failed）。
- 未执行（如实列出）：六入口仍未在独立智能体会话实跑；无人值守闭环未实测——Cohestra v0.8 的 Orchestrator 契约仍在该技能的进行中改动里、尚未发布，本次实际加载的 Cohestra 尚无结构化状态；未用 skills CLI 实测安装或升级。
- 待补证据：契约发布后一次真实 `run` 的闭环记录（覆盖终态映射各分支）；一次 Run 收尾后开新 Run 的记录；一次 unattended 下 verify 跳过写入人工介入清单的记录。
- 未做替代：未改动 `cohestra/`（其工作区 v0.8 进行中改动非本技能所写，未触碰、未回滚）；未用桌面推演冒充智能体实测；未替 Cohestra 实现契约字段，只在 Cadra 文档声明接口要求。

## 0.2.0 契约联动修复验证（2026-10-01）

本轮是同仓库 Cohestra 四项修复的必要消费侧联动；前述单技能任务记录保留原事实。发行版仍为 0.2.0、协议仍为 v0.2，未提交或发布。

- 规则变化：终态表先核对协议与本次结果，再处理失败、受阻和完成，最后处理 flow 边界。整改在 flow 内继续；`blocking_findings`／`acceptance_failed`／`stage_failed`、fix/validate 推荐的必要 review 或本轮 pending 验收超出 flow 时记 blocked；正常边界仍完成并注明截断。报告保留已知 passed/failed/pending/blocked，无结论才 unknown；不改 Cohestra 控制字段。
- 本次结果核对：调用前落盘拟调用阶段和已有 stage_result.stage/status/round；调用后先核实同步结果，再核对阶段、同阶段轮次增加，跨阶段不比较轮次大小。索引同步失败、旧结果或阶段不匹配时记 failed，不消费旧 next。Run checkpoint 模板与 run/resume 同步记录；中断恢复先核对完整 README 与本轮 handoff，不自动重跑已落盘阶段。report 同步保留已知验收结论。
- 桌面推演（脚本化映射模型，18/18）：验收失败的整改在 flow 内/外、review-only 有必做整改、fix 必要复审在 flow 外、validate 必要复审在 flow 内/外、正常 code/review 边界、passed 完成、completed+failed 防御分支、completed+pending 在含/不含 validate 的 flow、协议错误优先于完成、同步失败但新版 next 可读、可重试失败在 flow 内/外、非法 next、不可重试失败。已知 acceptance 在判定前后保持原值；失败或必要后续被截断时不产生 completed。
- 本次结果推演（6/6）：同阶段轮次不增拒绝、同阶段新轮次接受、review-03 → fix-01 接受、返回错误阶段拒绝、首次合法结果接受、即使阶段正确但同步失败仍拒绝。该模型按文档表构造，不是 Cadra 运行时实现或真实 run/resume 实测。
- 静态与文件证据：两技能共 30 份 Markdown、158 条相对链接检查通过，元数据/字段/枚举/版本与 `git diff --check` 通过；README 发布的 6 个实际文件操作分支与 Cohestra 同会话夹具演练见其本轮记录，Cadra 不自行写 `.yuzio/cohestra`。
- 未执行：独立智能体调用、真实 cadra run/resume、CLI 安装/更新与远程验证；原生 quick_validate.py 缺 PyYAML，已用 Ruby Psych 做 YAML 与等价基本元数据检查。未把桌面推演或脚本化输出夹具写成独立智能体实测。

## 0.3.0 首次启动与恢复修复验证（2026-10-01）

- 变更：协议 v0.3、发行版 0.3.0。首次启动允许无交付/调用任务执行 flow 首项一次；契约检查在建 Run/入队之前。新增 run 的显式恢复列表，blocked/failed 通过 Gate、原因解除与 checkpoint 核对后进入新 Run；一次恢复授权不改变 Cohestra 控制字段。resume 不重开终态；未完成 Run 中禁止定义编辑，准入字段变化强制回 draft，ready 复核失败也回 draft。逐 Task checkpoint、调用记录与结果快照用于恢复及历史报告，旧 Run 不被新结果覆盖。
- 静态检查：Cadra 包内 12 份 Markdown、50 条相对链接、0 断链；六入口齐全；0.3.0/v0.3 版本一致；双语 README 的标题层级、表格列数、代码块与链接目标一致（语言互链按对应版归一化）；旧执行口径在当前 Cadra 包内零命中；git diff --check 通过。对照本轮开始时 SHA256，cohestra/ 与 tests/cohestra-scenarios.md 共 20 个既有文件字节未变；现有未提交修改保留。
- 桌面推演：临时脚本化文档模型 50/50 通过，覆盖三种首次起点、既有交付缺索引、版本缺口、恢复参数/准入、旧状态受阻、一次授权、合法 next、必要阶段超出 flow、已交付收尾、定义编辑与 Gate 失效、调用后阶段/轮次/同步核对。该模型不是 Cadra 运行时实现，也不是独立智能体证据。
- 同会话实测：明确选定本仓库 Cadra 0.3.0 与 Cohestra 0.9.0/v0.8 源规则，在隔离临时项目逐入口和阶段执行；Cohestra 角色实际完成需求、设计、四份 txt 的修改、固定候选审查和验收。共 15 份正式 handoff；最终四份任务 README 的合法 YAML 契约均回读为 completed/passed。临时 Python 辅助只做文件操作、候选字节/哈希检查与交付发布，不作为技能安装器或调度运行时。

| 实测 Run | 本轮结果 | 关键证据 |
|---|---|---|
| run-20261001-01 | completed；completed=2、blocked=1、failed=1、skipped=0 | full 从 need 首次起步，必要输入在 Gate 后被移走，实际 code 读取报 FileNotFoundError 并 blocked；bugfix 从 fix 起步，经注入 checkpoint 中断后 resume 核对，不生成 fix-02；small-change 从 code 起步完成；failed-sync 实际实施并交付 code 后，原子替换因注入的目标父目录缺失失败，记录 handoff completed/index sync failed，不消费待发布 next |
| run-20261001-02 | completed；completed=2、blocked=0、failed=0、skipped=0 | 缺输入时恢复请求先被拒绝，没有空 Run；输入补回、Cohestra 核实并原子恢复索引后显式恢复两个任务。full 在旧 blocked/allowed=false 仍保留时重试 code-02；failed-sync 直接 review/validate，无 code-02。恢复期间原 Run 与原报告 SHA256 不变；重报原 Run 仍为 blocked=1/failed=1，只追加新报告链接 |
| run-20261001-03 | stopped/已收尾；edit-probe skipped 回 ready | queued Task 的定义编辑被拒绝，Task/Run/queue 字节不变；明确 resume 收尾后修改 execution policy，Task 回 draft、旧 Gate 保留，已结束 Run 与队列记录不变 |

- 其他文件实测：running bugfix 的定义修改同样拒绝且三类文件 SHA256 未变；必要输入实际缺失时，另一 ready Task 的 Gate 复核回 draft，旧放行事实保留。
- 固定候选与实际验收：每次实施都保存原始/修改后字节与精确差异，检查仅目标 txt 改变、末尾换行保留；review 回读固定候选，validate 核对候选未变并复用 AC 证据。临时项目只要求作者审查，同一作者切换阶段不声称独立审查。最终内容及 SHA256（UTF-8，均含末尾换行）：

| 业务文件 | 最终内容 | SHA256 |
|---|---|---|
| full.txt | Full flow ready. | f1066fac397fabbd88fc0cc46a4010ba57136524cac378bfb06c74f060e503dc |
| bugfix.txt | Bug fixed. | 52192d2aaffc107ab7e2f0f834c4ad25bf68f651cdca77061d907877ab8d624d |
| sync.txt | Sync ready. | 5685961a12ed4a7ccee78f4cb010e8c7de9ec1dd4b4a8d944274b5f2a9fac9b1 |
| small.txt | Small change ready. | 75bd5f6c7fa36708dbbcbbf0e8ef645381e393b9e92ab3c1d6c975ff2d6238df |

- 证据入口：本轮临时目录 /private/tmp/cadra-v03-nK9pF3，项目中的 .yuzio/cadra/runs、.yuzio/cohestra/handoffs 和 evidence 保存交付、调用前记录、快照与故障操作；static-results.json、model-results.json、actual-results.json 保存检查结果。上述关键结果与候选哈希已记录在本文件，临时文件不是唯一依据。
- 限制与未执行：原生 skill-creator quick_validate.py 本次实际运行因缺 PyYAML 未通过环境启动；已用 Ruby Psych 做 YAML 和等价基本元数据检查，未安装依赖。不把本会话手工选择入口/阶段与实际文件执行写成独立智能体调度验证；未执行独立智能体调用、CLI 安装/升级或远程验证。中断/输入丢失/发布失败由显式故障注入产生，不声称自然会话断开。未提交、推送、发布、更新已安装技能或操作真实业务项目。

## 0.4.0 修订重启与执行边界修复验证（2026-10-01）

- 变更：协议 v0.3 → v0.4、发行版 0.3.0 → 0.4.0，针对综合审阅的 4 项问题与 1 项运行风险。① **P1 终态任务定义修订后的重新执行**：新增调度回边 completed/blocked/failed → draft、第 2.2 节（修订记录 `rev-<N>`、新旧两代定义与结论绑定、准入未通过保持 ready 不入队）与第 6.3 节（按「变更字段 + 原终态」确定重启起点：requirement/flow 变更取新 flow 首项；仅 dependencies/execution policy 变更时 blocked/failed 重试原待调用阶段、completed 只作修订收尾）；修订后的任务不进入恢复列表，两者不并行。② **P2 执行模式核对失败映射为停止**：第 6 节读取规则、终态映射表第 1 行与第 7 节改为——声明 unattended 而契约记为 attended（或字段缺失、非法）即记 `failed`、不消费本次 `next`，即使 `next.allowed = true` 且阶段在 flow 内也不推进；调用前记录与 checkpoint 增加本次声明的 execution_mode。③ **P2 flow 校验口径统一**：显式序列与 preset 同口径，须为 `need → design → code → review → fix → review → validate` 的子序列（`review` 至多两次且第二次在 `fix` 之后，其余阶段各至多一次），`[fix, review, validate]` ≡ `bugfix`。④ **P2 建 Run 前检查初始化前提**：第 6.1 节新增「目标与初始化前提」前置检查（Git 工作区根、可安全写入、非技能源仓库），非 Git 停止且不代建 `.yuzio/cohestra`、不执行 `git init`；缺容器由 Cohestra 在首个阶段调用时最小初始化。⑤ **运行风险（可重试上限）**：新增「重试与无进展上限」——同一阶段可重试失败最多重试 2 次，第 3 次仍失败记 `failed`（重试上限耗尽）；连续两次调用后结构化状态全未变即判无进展、立即停止；计数写入 checkpoint 且 resume 沿用不清零，落 failed 后 `stop_queue_on_failure` 照常生效。⑥ 联动更新 SKILL.md、add/ready/run/resume/report/list、assets/task.md、assets/run.md、assets/project/README.md、assets/project/queue/order.md 与双语 README。
- 静态检查：Cadra 包内 12 份 Markdown、53 条相对链接、0 断链（Cohestra 包 14 份、48 条、0 断链；全仓 30 份、153 条、0 断链）；六入口齐全；0.4.0 / v0.4 版本字样在 release.json、SKILL.md、workflow.md、双语 README 与测试口径间一致；旧口径表述（现行规则中的“单调子序列”、“不静默当作无人值守结果”、checkpoint 的“恢复授权：”栏）在当前 Cadra 包内零命中，历史记录节保留当时事实；双语 README 标题层级 6/6、表格行 19/19、代码块 3/3（内容逐字一致）、相对链接目标 26/26 一致；`git diff --check` 通过。本轮只改 `cadra/`、`tests/cadra-scenarios.md` 与双语 README：按 mtime 核对，`cohestra/` 下 0 个文件被本轮触碰，`tests/cohestra-scenarios.md` 未改。
- 既有桌面推演记录：原总数标为 35/35，但分组列为 flow 15、修订重启起点 6、执行模式 5、重试与无进展 5、建 Run 前提 5，合计 36；原脚本未在仓库归档，不能据此确认原总数。flow 的首轮模型曾暴露“不重复”与必要复审的冲突，规则改为「子序列 + review 至多两次」；该历史记录不作为运行时或独立智能体证据。重新核对结果见下方本轮记录。
- 未执行（如实列出）：本轮为文档修订与边界推演，未在独立智能体会话中实跑 cadra run/resume；未做真实项目的修订重启与重试上限实测；未用 skills CLI 做安装、升级或远程验证；未执行阶段调用联调。Cohestra 包本轮零改动，其场景与验证记录维持原事实。
- 待补证据：一次真实终态任务修订 → ready → 修订重启的完整记录（覆盖 completed 与 blocked/failed 两种原终态）；一次同阶段可重试失败达到上限并触发 `stop_queue_on_failure` 的记录；一次契约 execution_mode 记为 attended 的核对失败记录。

### 0.4.0 规则闭合复核（2026-10-01）

- 工作区开始时已包含五项主修复，本轮保留既有修改，补齐未消费修订的累计编辑、新定义快照、ready 准入失败后的可执行建议、无调用修订收尾的消费标记、已完整交付阶段不重跑、逐阶段累计重试预算与 resume 按调用标识去重；显式 flow 不能为空。双语 README 按变更字段区分重启与收尾，不再一概宣称从新 flow 首项起步。
- 文档静态检查：Cadra 12 份 Markdown / 53 条相对链接、Cohestra 14 份 / 48 条，均 0 断链；六入口、0.4.0/v0.4、双语标题层级、表格行数、代码块和链接目标一致，git diff --check 通过。以本轮开始时的 SHA256 为基准，cohestra/ 与 tests/cohestra-scenarios.md 共 20 个文件字节不变；未用 mtime 代替内容核对。
- 重新执行脚本化文档模型 43/43：flow 15、修订起点 6、模式 5、失败重试/无进展 5、初始化前提 5，原五组共 36；补充边界 7，覆盖累计编辑、原因未解除保持 ready、阶段切换不返还预算、resume 已消费预算不重计、无调用收尾关闭修订、完成优先于无进展、可选字段缺失/null 等价。模型从现行文档构造，读取实际 preset，临时路径为 /var/folders/2q/s5d5ttp9495_8f42knmdq69r0000gn/T/cadra-v04-closure-x6jbqnwl/checks.py，结果在同目录 model-results.json；不是 Cadra 运行时，也不是实际阶段联调。
- 独立复核（同一工作区，事后重建）：按现行文档重写文档模型 47 例（flow 16、修订起点 6、执行模式 5、逐阶段预算 4、无进展与终态优先级 4、初始化前提 5、补充边界 7）全部一致，覆盖「完成优先于无进展」「可选字段缺失与 null 等价」「预算不因成功或阶段穿插返还」「按 run-id + slug + 调用序号去重」「无调用收尾关闭修订」；核对后将三处仍按旧语义描述的清单/报告行对齐——可重试上限行与重试预算跨 resume 行改为逐阶段预算口径，report 的修订标注补上修订收尾。复核脚本未归档，本轮结论只作静态推演证据。
- 原生 skill-creator quick_validate.py 实际启动失败：ModuleNotFoundError: No module named 'yaml'；未安装依赖。Ruby Psych 解析 Front Matter 并核对 name/description 通过，只作为基本元数据检查，不声称原生校验通过。
- 未执行：独立智能体 run/resume、真实阶段调用与 Git 容器初始化联调、真实项目修订重启/重试上限、CLI 安装/升级或远程验证。未提交、推送、发布、更新已安装技能或修改 Cohestra。
- 未做替代：未用脚本化推演冒充智能体实测；未修改 `cohestra/` 的协议、阶段定义或 handoff 语义；未提交、推送或发布。

## 0.5.0 控制与恢复缺口修复验证（2026-10-02）

- 变更：协议 v0.4 → v0.5、发行版 0.4.0 → 0.5.0，针对联合审阅的 3 项控制与恢复缺口。① **P1 跨阶段整改循环无整体上限**：第 6 节新增三项上限——逐阶段失败重试预算（不变，2 次）、整改轮上限（blocking_findings 触发的 fix 不超过 3 轮）、任务调用预算（单 Task 单 Run 已发起阶段调用不超过 16 次，兜底 acceptance_failed 往复、必要复审往复与 validate 补证重复），任一耗尽记 failed 并列入需人工介入；预算是 Task 级、跨 resume 沿用不清零、新 Run 用自身预算、unattended 不自动重置，重新获得额度只能由用户在显式恢复列表中重新选择。② **P2 无进展误伤验收补证**：无进展判据收窄，Cohestra 第 7.3 节「仅缺本阶段可补证据」的 validate 自循环豁免，改由调用预算兜底；并写明该判据是加速停止、与重试预算取先到者；「可选字段缺失与 null 等价」明确为缺失 ≡ 显式 null、与写有内容的映射不等价。未采用扩展 Cohestra 契约的路线：Cadra 不解析正文，证据进度若要进控制流须由 Cohestra 新增机器字段，本轮只记录该后续选项。③ **P2 入队部分写入无恢复步骤**：第 4 节新增入队三步写入（Run → Task → 队列清单，携带 enq-<run-id>-<NN>）、出队同编号协议（deq-）与「补齐范围」条，明确补齐只写尚未写入的步骤、Run 为先写方与权威来源；第 3 节把该情形从「记录矛盾」改为只有 resume 能判定的幂等补齐，解除「run 拒绝新建 / resume 报矛盾 / add 拒绝编辑」的三入口互锁，add 的归属拒绝不放宽。队列清单模板新增「入队操作编号」「出队操作编号与结论」两列，并保留旧清单按表头只读的口径。
- 联动更新：SKILL.md 规则 7 与协议版本、run/resume/list/report、assets/run.md（checkpoint 新增入队写入进度、调用预算与整改轮、出队回写，调用记录表新增预算消费列）、assets/project/README.md、assets/project/queue/order.md，以及双语 README 的 cadra 段落与版本行。
- 静态检查（脚本，当时未归档；后于 2026-10-03 归档，见「0.5.0 复核补正三」）：Cadra 包 12 份 Markdown / 57 条相对链接 / 0 断链（0.4.0 记录为 53 条，新增链接来自第 4 节与 resume 对公共流程的引用）；全仓 30 份 / 157 条 / 0 断链；release.json 0.5.0 / v0.5 与 SKILL.md、workflow.md 标题、双语 README 版本行一致，现行规则与两份 README 内无 v0.4／0.4.0 残留；resume.md 条目编号 1–10、workflow.md 第 4 节条目编号 1–9 连续；队列模板表头八列、列定义与分隔行列数一致，list.md 与容器 README 已同步两个新列；双语 README 标题层级 6/6、表格行 19/19、代码块 6/6；`git diff --check` 通过。**范围限制**：`git diff --check` 只覆盖已跟踪改动，本行引入且当前未跟踪的模板 `cadra/assets/project/queue/order.md` 不在其检查范围内，该模板由静态检查脚本按表头八列、列定义与分隔行列数一致核对。临时目录 /var/folders/2q/s5d5ttp9495_8f42knmdq69r0000gn/T/tmp.cy8bNUnTr7。
- 脚本化文档模型 23/23（三项上限 7、无进展 7、部分写入 9）：上限组覆盖失败重试预算按比较字段有变化计 2 次后耗尽、无进展优先于预算、预算不因穿插返还、整改 3 轮后耗尽、整改轮与重试预算独立、acceptance_failed 往复在 16 次调用后兜底、完整路径 8/16 次调用与 1/3 轮不误伤；无进展组覆盖 validate 补证第二轮不再 failed、补证重复 16 次后由预算停止、豁免只限 validate 出口、仅轮次增加不算进展、缺失与显式 null 等价、写有内容的映射与 null 不等价、完成优先于无进展；部分写入组覆盖建 Run 后中断可补齐、补齐幂等、已 queued 只补队列行、快照不一致停止、状态与调用记录不相容停止、同编号多行停止、出队只补回写、add 归属拒绝不放宽、无 enq 记录不进入补齐。模型从现行文档构造，不是 Cadra 运行时，未调用 Cohestra 阶段，也未读写任何项目文件；结果 JSON 在同目录 model-results.json。
- 模型暴露并已回写的两处口径：一是「最多追加 2 次失败重试」与无进展判据的相互作用——比较字段完全相同的重复失败会先被无进展停住，已在第 6 节写明两者取先到者、重试预算是许可上限；二是写有内容的可选字段（如 findings {blocking: 0}）与 null 不等价，可用于规避无进展，但受 16 次调用预算兜底，作为残余口径如实记录，本轮未额外收紧。
- 本轮未改 `cohestra/`：其文件最新 mtime 为 2026-10-01 10:59（`assets/handoff.md`；`references/workflow.md`／`references/validate.md`、`assets/task-index.md` 为 2026-10-01 10:57），早于本轮全部写入（2026-10-02 10:21 起），本轮写操作只落在 `cadra/`、`tests/cadra-scenarios.md` 与两份根 README。**证据限制**：mtime 只作时间线旁证，不能证明字节未变；本轮开始时未取基线哈希，故不主张字节级未变。Cohestra 协议、阶段定义与 handoff 语义零改动，未采用契约扩展路线。**（补正 2026-10-03）** 本行原记最新 mtime 为 2026-09-29 10:06，比实测更早，漏掉 2026-10-01 的改动（09-29 10:06 实为 `SKILL.md` 的时间）；「本轮未改 cohestra」的结论仍成立。另 `cohestra/` 相对 HEAD 有 8 个未提交改动（属更早一轮），故「未改」只限定在本次 cadra 0.5.0 窗口内。
- 未执行（如实列出）：未在独立智能体会话中实跑 cadra run/resume；未做真实项目的整改轮耗尽、调用预算耗尽与入队中断实测；未用 skills CLI 做安装、升级或远程验证；未执行阶段调用联调，也未对真实 `.yuzio/cohestra` 任务验证 validate 补证路径。
- 待补证据：一次真实 review→fix 整改三轮触顶的记录；一次入队三步写入中途中断后由 resume 补齐的真实记录；一次真实 validate 多轮补证未被判无进展的记录。

### 0.5.0 复核补正（2026-10-02）

首轮 0.5.0 记录的 23 个模型用例未覆盖以下三处边界，复核发现后已修正；三者都属于 v0.5 内更正（v0.5 尚未提交或发布，故不另起协议版本）。

- **出队补齐未覆盖 Task 状态**：原第 4 节第 8 条只写 Run → Queue，遗漏 Task 终态或 `skipped` 回退，导致 failed/blocked 出队被误判为「入队前状态却已有阶段调用记录」，completed/skipped 补齐队列后 Task 仍可能停在 `running`/`queued`。现改为出队三步写入 **Run 结果快照 → Task 终态（或回退 `ready`）→ 队列行 `deq-` 编号与结论**，逐份回读，三者一致才算收尾；结果快照的写入即标志该 Task 进入出队阶段。第 9 条补齐规则同步改为**先分阶段再补齐**：无结果快照按入队规则、有结果快照按出队规则，并写明不得只凭 Task 状态字面值判断（`blocked`/`failed` 既是恢复任务入队前的原状态，也可能是本轮终态）。据此新增出队阶段的停止条件：快照为 completed 而 Task 为 `ready` 且无 `skipped` 回退记录时停止。
- **旧版队列只有读取规则**：七列旧清单既要求保留、又要求新行写 `enq/deq`，直追旧表块会列含义错位。现明确升级方式为**在文件末尾追加一个完整八列表块**，旧表块原样保留；读取按表头分别解析各表块并合并，旧块缺列写 unknown；定位新块用 `enq-<run-id>-<NN>` 并以 run-id + slug 复核，旧块只用 run-id + slug；写入一律作用于新表块。list.md 与容器 README 同步该口径。
- **预算检查与正常收尾的优先级**：原第 6 节总述把预算检查排在 flow 边界之前，与模型实现相反——第 16 次交付恰好到达正常边界时，按文档顺序会判 failed。现统一为**先确定是否还需要再调用，确需调用时才检查对应上限**：完成、受阻、失败与正常 flow 边界都在前一步终止，上限只约束继续调用，不把已成立的收尾改判为耗尽。同时写明整改轮只拦该原因的第 4 次 fix，**第 3 轮 fix 交付后仍按 `next` 正常调用必要复审**。run.md 与 resume.md 的相应表述同步。
- 复核后的脚本化文档模型 **37/37**（原 23 例 + 判定顺序 4 + 出队阶段 7 + 旧清单升级 3）：判定顺序组覆盖「收尾结论优先于预算检查」「确需调用时才检查预算」「第三轮 fix 后仍进入必要复审」「上限只拦第 4 次 fix」；出队阶段组覆盖 failed/blocked/`skipped`/completed 四种终态的补齐、三者一致时的 noop、快照与 Task 状态互不相容时停止、以及入队阶段的 blocked 不被出队规则误伤；旧清单升级组覆盖七列与八列块合并读取、新行只追加到八列块且旧块字节不变、只有旧块时新建八列块。脚本与结果仍在临时目录 /var/folders/2q/s5d5ttp9495_8f42knmdq69r0000gn/T/tmp.cy8bNUnTr7，当时未归档（后于 2026-10-03 归档，见「0.5.0 复核补正三」）。
- 复核后的静态检查：Cadra 12 份 Markdown / 57 条相对链接 / 0 断链，全仓 30 份 / 157 条 / 0 断链；resume.md 条目编号 1–10、第 4 节条目编号 1–9 连续；`git diff --check` 通过。复核提出的「0.5.0 / v0.5、57 条、157 条、diff --check」与其独立核对一致。
- 证据限制同前：`cohestra/` 未改动只由 mtime 时间线旁证，未取基线哈希，不主张字节级未变；本轮仍为文档修订与模型推演，未执行真实 run/resume。

### 0.5.0 复核补正二（2026-10-02）

复核发现的第 4 处缺口：**旧表块中未出队记录的收尾规则冲突**——第 4 节第 8 条 ③ 要求定位旧表块的行并回写出队结果，模板升级规则又规定写入只作用于新表块，于是旧行"能定位但没有合法写入路径"；旧 Run 未结束时会持续阻挡新 Run。

- **取舍**：未采用「在新表块追加关联旧 run-id + slug 的收尾记录」，改为**按行就地回写该行自己的结论列**。理由有三：① 旧块的「出队结论与时间」本来就是这个行的出队槽位，补写它是升级前协议原有的写入，不涉及迁移、回填新列或列结构变化；② 新旧行共用一套机制，只有新块额外携带 `deq-` 编号，避免为同一动作维护两套语义；③ 兼容性——只读旧块的旧版本 Cadra 仍能看到出队结果，而新表块里的收尾记录对它是不可见的，旧行会永远显示为待出队。
- **冻结范围收窄并写明**：旧表块冻结的是**列结构与已有结论的行**——不迁移、不回填新列、不改列序、不重排、不改写已出队的行；唯一允许的写入是给**仍未出队**的行补写它本来就有的那个结论单元格，且只写一次。
- **完成判据改为逐行**：某行只要自身结论列非空即为已出队（新块看「出队操作编号与结论」，旧块看「出队结论与时间」），旧行不因缺 `deq-` 编号被判为未出队。第 3 节「未完成 Run」的定义同步改为按该合并视图与逐行判据判定，不看表块新旧。第 9 条出队阶段补齐也改为「该行结论列为空时补 ③」，旧表块就地补既有单元格。
- **模型 42/42**（原 37 例 + 旧行收尾 5）：G1 旧行未出队 → 仍阻挡新 Run；G2 就地收尾后允许新 Run（列结构不变、未新增编号列）；G3 再次 resume 无重复写入、无新增行；G4 已出队的旧行不得改写；G5 新旧表块混合时只改目标行，新表块字节与其余待出队行不受影响。复核建议的核查序列（旧行未出队 → 收尾 → 再次 resume 无重复写入 → 允许新 Run）已完整覆盖。
- 静态检查复跑：Cadra 12 份 Markdown / 57 条相对链接 / 0 断链，全仓 30 份 / 157 条 / 0 断链；`git diff --check` 通过。
- 证据限制同前：`cohestra/` 未改动只由 mtime 时间线旁证，未取基线哈希，不主张字节级未变；本轮仍为文档修订与模型推演，未执行真实 run/resume。

### 0.5.0 复核补正三（2026-10-02）

复核发现的第 5 处缺口：**旧行收尾没有接通 `resume` 入口**。第 4 节第 8 条 ③ 已允许就地回写旧行，但 resume.md 第 2 条仍写「队列缺 `deq-` 编号时补回写」并在停止清单里保留「编号缺失」，模型的 `resume_writes()` 也在缺少 `enq` 时直接返回停止。复现结论：旧 Run 有结果快照、旧行可由 run-id + slug 定位、但没有新版操作编号时，恢复入口返回 `stop：缺少入队记录，无法定位队列行`——旧 Run 仍然无法收尾。补正前的 G2/G3 直接调用队列回写辅助函数，只证明了旧行可写与重复写幂等，没有证明恢复入口能到达该写入。

- **修正**：把「旧记录例外」同步到恢复入口与公共流程。定位基准键统一为**消费 run-id + slug**，`enq-` 编号只在存在时用于区分同一键下的多行；核对用 Run checkpoint 的「入队定义快照」与结果快照；回写落在该行自身既有的结论列（旧表块写「出队结论与时间」）。**编号缺失本身不是停止条件**，并写明不得因为「没有新版编号」就停在停止分支、把旧 Run 永久留在未完成状态。停止条件相应精确化为「同一 run-id + slug 匹配到多行且无法用 `enq-` 编号区分」，其余停止条件不变。
- **模型 48/48**（原 42 例 + 恢复入口贯通 6）：H1 旧 Run（无 enq-/deq- 编号）经恢复入口判定为可补齐、不再停止（复核给出的复现路径）；H2 端到端——入口判定 + 就地收尾后旧行已出队、未完成 Run 不再阻挡新 Run；H3 端到端幂等——再次 resume 判定为已完成，入口不重复补写、文本不重复写入；H4 旧 Run 的入队阶段同样可达（用 checkpoint 的入队定义快照核对）；H5 同一 run-id + slug 多行且无编号可区分时仍停止，不放宽停止条件；H6 既无编号又无入队定义快照时不猜测补齐，仍按其他恢复规则处理（与原 C9 一致）。
- 静态检查复跑：Cadra 12 份 Markdown / 57 条相对链接 / 0 断链，全仓 30 份 / 157 条 / 0 断链；`git diff --check` 通过。
- **证据归档（2026-10-03 补正）**：本轮 48/48 模型与静态检查脚本此前只存临时目录 /var/folders/2q/s5d5ttp9495_8f42knmdq69r0000gn/T/tmp.cy8bNUnTr7，仓库内不可复现；现归档为 `tests/cadra-v05-model.py`（结果写同目录 `tests/cadra-v05-model-results.json`）与 `tests/cadra-v05-static-checks.py`。运行：`python3 tests/cadra-v05-model.py`（合计 48/48）、`python3 tests/cadra-v05-static-checks.py`（cadra 12 份 57 条 0 断链、全仓 30 份 157 条 0 断链，版本/队列列/术语/双语一致性全通过）。两脚本以 `__file__` 推导路径（模型结果写脚本同目录、静态检查 ROOT 取上两级），不硬编码机器路径；它们是维护者侧的文档模型与一致性检查，位于 `tests/`（非分发技能包），不改「技能包无脚本」口径，也不代表 Agent 实测或运行时联调。
- **静态检查范围补正**：`git diff --check` 只覆盖已跟踪改动；未跟踪的 `cadra/assets/project/queue/order.md` 不在其检查范围内，该模板由静态检查脚本按表头八列与列定义一致性核对。行 260、286 与本行的「`git diff --check` 通过」同此范围。
- **cohestra mtime 引数补正**：第 1 轮（行 263）将 cohestra 最新 mtime 记为 2026-09-29 10:06，实测应为 2026-10-01 10:59，已在行 263 就地改正；结论「本轮未改 cohestra」不变，且只限定在 cadra 0.5.0 本轮窗口内。
- 证据限制同前：`cohestra/` 未改动只由 mtime 时间线旁证，未取基线哈希，不主张字节级未变；本轮仍为文档修订与模型推演，未执行真实 run/resume。

### 0.5.0 复核补正四（2026-10-03）

组合流程联合审阅发现的 3 项规则缺口与 3 项跨技能对齐问题，均属 v0.5 内更正（v0.5 尚未提交或发布，不另起协议版本）。

- **变更（cadra 侧规则缺口）**：① **依赖在执行窗口内被修订无兜底**：第 4 节第 4 条由「依赖为 blocked/failed/skipped」扩为「依赖落盘状态非 completed 的任意情形」（含被修订回 draft/ready），任务开始或续跑前重核、记 blocked（依赖未满足），并写明解除路径（依赖经新 Run 回 completed 后由用户显式恢复）；run.md 串行执行第 2 条与 resume.md 第 5 条 queued 分支同步接入。② **依赖优先排序是死规则**：Gate 第 6 条与入队条件要求依赖全部 completed，同一 Run 本就不可能含任务与其未完成依赖；删除第 4 节第 3 条的「依赖优先于优先级」，写明依赖链按层级逐 Run 推进，第 6 条改为「依赖只影响入队判定，也不在同一 Run 内串行链接」，双语 README 同步。③ **slug 同名即绑定无内容核对**：第 6.1 节「已有任务」新增收养核对（README 正文「任务目标」与 requirement 对照，明显不对应不接续、不入队，请用户选择），并注明这是一次性收养防护、不违反「不解析正文决定流程」；add.md 第 2 条与 assets/task.md 增加绑定确认记录。
- **变更（跨技能对齐）**：④ **「终点」表达互注**：Cohestra 第 7.3 节新增——「用户声明的终点」不进契约，外部编排只能按任务 flow 推断终点合法性，与编排配合时终点用 flow 表达（review 收尾选 review-only 或显式序列）；Cadra 第 5 节（preset 末项即终点范围）与第 6 节终态表前言同步互注，两侧场景表互引。⑤ **契约引用块补 findings**：Cadra 第 6 节 YAML 块按 Cohestra 第 7.2 节顺序补齐 findings 映射，字段集与之一致。⑥ **契约版本共发布约束**：Cadra 第 6 节「版本同步」与 Cohestra 第 7.2 节互相声明——协作协议版本变更时两技能同步发布，否则 run 前置检查停在契约未就绪；双语 README 维护段同步。
- **模型 52/52**（原 48 例 + 依赖兜底 4）：I1 排队期间依赖被修订回 draft → blocked；I2 依赖新 Run 回 completed 后显式恢复可入队；I3 依赖未 completed 不得入队（逐层逐 Run）；I4 blocked 出队后允许新 Run（自锁解除）。模型从现行文档构造，不是 Cadra 运行时，未调用 Cohestra 阶段；结果在 tests/cadra-v05-model-results.json。
- **静态检查（tests/cadra-v05-static-checks.py 重跑）**：cadra 12 份 Markdown / 60 条相对链接 / 0 断链，全仓 30 份 / 160 条 / 0 断链；新增断言——契约引用块字段集 ⊇ 且仅含 Cohestra 第 7.2 节十个字段、两技能契约版本字样一致、「依赖优先于优先级」在 cadra 包内零命中、run/resume/add 接入新规则文本、cohestra 侧两条互注齐备；双语 README 标题层级、表格行、代码块一致。
- **未执行（如实列出）**：本轮仍为文档修订与模型推演；依赖兜底、收养核对未在独立智能体会话实测；未执行真实 run/resume、CLI 安装/升级或远程验证；未提交、推送或发布。
- **待补证据**：一次依赖任务在排队期间被修订后 blocked 并经新 Run 解除的真实记录；一次 slug 同名既有 cohestra 任务的收养核对记录。

## 0.5.0 同会话实测（2026-10-03）

- 口径：同会话手工驱动实测，**不是独立智能体调度验证**。明确选定本仓库 Cadra 0.5.0/v0.5 与 Cohestra 0.9.0/v0.8 源规则，在隔离临时项目逐入口与阶段执行；中断、连败与模式违例均由显式故障注入产生，不声称自然会话断开或自然失败。临时 Python 辅助（scribe.py）只做文件写入/回读断言/同目录原子替换/SHA256，不做任何控制流判定，不作为技能安装器或调度运行时。
- 项目：`/private/var/folders/2q/s5d5ttp9495_8f42knmdq69r0000gn/T/opencode/cadra-v05-actual/proj`（Git 工作区，9 个任务、7 个 Run）与 `…/legacy`（v0.4 旧记录场景）；候选均为未提交快照（记录基线、精确差异与字节 SHA256），项目未授权提交。

| 实测 Run | 覆盖场景 | 结果 |
|---|---|---|
| run-20261003-01 | 双任务串行；**validate 三轮本阶段补证**（B1 豁免实测） | completed；completed=2。backfill-task validate-01/02 的 stage/status、candidate、findings（缺失≡null）、acceptance=pending 与 next=validate 全未变，checkpoint 记录「补证出口豁免、不判无进展、调用预算兜底」，第三轮 AC-3（wc -c = 16）补全后 passed；调用预算 5/16 |
| run-20261003-02 → 03 → 04 | **依赖在执行窗口被修订**（A1 全链路） | run-02：filler-task completed 后中断注入，`add` 修订 dep-parent（rev-1，其原 Run 已结束、归属拒绝不触发）；resume 的 queued 重核发现 dep-parent=draft → dep-child **blocked（依赖未满足）、未调用任何阶段**、出队，run-02 completed。run-03：dep-parent 修订重启（requirement 变更 → 新 flow 首项 code，轮次继续递增 code/02…validate/02）→ completed，rev-1 关闭。run-04：显式恢复 dep-child（Gate 复核依赖满足 + 原因解除证据；原 checkpoint 无调用 → 沿用原「首次启动 code」动作）→ completed |
| run-20261003-05 | **整改轮触顶 + 执行模式核对失败 + 失败后队列照常** | completed；completed=1、failed=2。loop-task：fix×3（整改轮 1/2/3，F-001/F-002/F-003 逐轮修复并复审关闭），review-04 必要复审（不耗轮）发现 F-004（loop.txt.bak 越界新建）→ 该原因第 4 次 fix 不再调用 → **failed（整改轮上限耗尽）**，调用 8/16；mode-task：code-01 契约记 `execution_mode: attended`（注入）→ **failed（执行模式核对失败）**，不消费 next（review 在 flow 内也不推进）；after-task 照常 completed（stop_queue_on_failure=false）。report-01 四类计数齐全、人工介入清单含两项上限/核对失败与 verify 跳过 |
| run-20261003-06 | **入队中断补齐**（① 后中断） | resume：无结果快照 → 入队阶段，enq 编号与定义快照和实际 Task 一致、入队前状态且无调用记录 → 判同一次入队，按同一 `enq-run-20261003-06-01` 补 ②③，不新建 Run、补齐前不调用阶段；随后正常执行 code/review，flow [code, review] 正常边界截断 completed（标注未执行 validate/fix、验收 unknown、列入人工介入）；二次 resume 三文件 SHA256 不变（noop） |
| run-20261003-07 | **无进展加速停止 + 出队中断补齐** | code 同因连败两轮（stage_result=code/failed/1→2、candidate 两叶 null、findings/acceptance 缺失、next 相同）→ **判无进展 failed（加速停止）**，重试预算 code 1/2 剩余额度不消费；出队中断（结果快照已写、Task running、队列缺 deq）→ resume 先分阶段（有快照→出队阶段）补 Task 终态 failed 与队列 deq，**不误判「入队前状态却已有阶段调用记录」**；二次 resume noop |
| legacy 项目 | **v0.4 旧记录恢复**（无 enq-/deq- 编号、七列旧清单） | resume：旧记录例外——run-id + slug 定位唯一行、入队定义快照核对一致、有结果快照 → 出队阶段，就地写入旧行既有的「出队结论与时间」单元格（不新增列、不迁移）→ 旧 Run 收尾 completed；二次 resume noop；新 run 前置判定为「没有合格任务」而非「存在未完成 Run」（旧 Run 不再阻挡）；七列块列结构不变 |
| run（未建 Run） | **slug 同名收养核对**（A3 实测） | 既有 `.yuzio/cohestra/handoffs/orphan-probe/`（attended 诗歌任务，completed）与 cadra 新 Task orphan-probe（probe.txt 文本修改）同名：add 记录「绑定时已有交付（主题摘要）」并报告不符；run 前置收养核对判主题明显不对应 → 不接续、不入队、不建 Run（无 run-20261003-08、队列无行、Task 保持 ready），请用户选择 |

- 不变量核对：proj 队列 11 行全部带 deq 结论；7 个 Run 全部 completed；9 任务终态 6 completed（dep-parent、backfill-task、filler-task、dep-child、after-task、resume-task）3 failed（loop-task、mode-task、fail-task）；legacy 七列块无编号列新增。
- 关键哈希（SHA256，UTF-8）：loop.txt=39ecaae9b715b0495be311e4a4507b4057a304bfae631b9419da45cc5067d6ce（fix-03 后 AC 全满足，遗留 loop.txt.bak 为 F-004 证据）；parent.txt=28ec5132ab5ff91f794cf40d9fc2baaff816d367798360724d8d7c24f85b2a76（rev-1「Parent v2.」）；proj queue/order.md=d25653ce21fb6bb3bf3d054c4c19c8b75e645c8e927455375a7b55f280cf773a；run-20261003-05.md=3d1fcf4a13a8513fe955666b5282bec979c4553b68b44931fac99912e396be68；run-20261003-05-report-01.md=f35319ae703682073a26ec1988104bc95d2e7922891775dff954426f26ab35a9；legacy queue/order.md=4d2e0e3742b9f3d70ac2767f252b2c2404c1ed90613ccd56a595a0f84ecc7ce5。
- 未执行（如实列出）：独立智能体会话实测；CLI 安装/升级与远程验证；真实长时运行的自然中断证据（本轮中断均为注入）。本轮未修改技能包与真实用户项目。
- 闭合情况：0.5.0 与复核补正四列出的待补证据中，「整改三轮触顶」「入队中断补齐」「validate 多轮补证」「依赖排队期间被修订」「slug 同名收养核对」本轮已补同会话实测证据；仍缺独立智能体与 CLI 安装证据。


## 2026-10-21 规则精简检查

- 取消固定 verify 提议和未执行记录；Cohestra 根据明确目标自动选择一个起步阶段，显式入口优先；初始化与队列不再执行旧格式兼容。Cadra 通过公共流程索引按入口及条件读取规则。
- 对照修改前文件，Task 状态与 Gate、终态定义修订、修订重启、Cohestra 契约/终态映射/预算原规则完整保留；索引发布校验、checkpoint、轮次与预算恢复仍适用。
- 验证：现有 unittest 82/82；更新后的 Cadra 文档模型 47/47（在临时目录运行，未覆盖历史结果 JSON）；两技能 quick_validate、双语结构、全仓相对链接与 diff 空白检查通过。
- 以上为静态检查与模型推演；阶段自动选择和按需读取尚未进行新的实际智能体调用验证。历史验证记录保留当时事实，不作为现行兼容规则。

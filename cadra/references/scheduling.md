# 固定两任务小组与资源等待（协议 0.11）

ready/run/append/resume 读取本页；list/report 只读取数据形状和视图。规则由包内 [scheduler.py](../scripts/scheduler.py) 计算，[run_guard.py](../scripts/run_guard.py) 校验和发布。脚本不派发、不调用项目工具，也不能证明调用者保存的观察和输入证据真实。

## 准入与路径

Task 增加 `ready_scope: null`；ready 在既有八项中的范围／输入检查内填写：

```json
{"revision":1,"scope":{"mode":"parallel","files":["Sources/Screen.swift"],"dirs":["Tests/Screen"]},"inputs":{"Sources/Screen.swift":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}
```

- files 为预计修改／删除／新增文件；dirs 为预计修改范围的目录前缀。`mode=exclusive` 独占成组，无法可靠定位时采用；不靠“不同模块”代替完整清单。
- 包含本地化、路由、工程配置、注册 runner、共享文档及新文件目录；共同只读 AGENTS／设计规范不占用。输入指纹与 scope 分开；仅有读取关系不构成修改占用，但变更可能使候选证据失效。
- 项目相对 POSIX 路径；禁止绝对、空组件、`.`、`..`、反斜杠、NUL、`.git`、`.yuzio`。Unicode NFC／大小写保守合并，目录按组件边界包含；现有和未来路径均核验，不接受符号链接或硬链接别名。进程记录属于单独所有权，不纳入业务修改范围。
- inputs 是相关业务输入路径→SHA-256，尚不存在为 null；既有 Gate 的规范／环境指纹继续保留。revision 或范围／输入语义改变后清空 ready_scope 并重新 ready。运行前重核相关变化；仅重算准入不产生新工程授权。
- 输入路径按相同的 NFC／大小写规则比较，同一份指纹表不得包含别名键。最终候选须明确保留旧证据依赖的路径（不存在仍写 null）；缺少该路径记录属于证据缺口，不能当作已确认不存在。
- Run.definition 冻结 ready_scope；运行时扩大范围进入调度日志，不修改 Task。每次恢复都申请原范围与新增范围的完整并集，不靠缩小范围绕过冲突。

## 分组与角色

单队列、单未完成 Run。按既有冻结队列顺序找首项，再向后找第一个 scope 不相交的合格项，最多两项。依赖必须在准入时已 completed，仍按当前定义核对；不新增同组依赖或 DAG。找不到第二项即单项成组。

首次派发前写 group 事件并回读，成员固定；等待、失败或先完成均不补位，append 只追加后续队列。本组结果完整落盘后再开下一组。每项同一时刻最多一个阶段、全组最多两个阶段；角色会话数量不等于正在执行阶段数。独立 reviewer 可同时评审各自固定快照；不要求 worker/reviewer 四个角色同时执行。槽位暂不可用沿既有等待／受阻规则，不切换自审或伪造释放。

取得范围时保存 before 完整字节／不存在标记和摘要，事件只保存摘要索引与 before_refs/before_ref。每次写入只归属本任务授权的增量，不能用共享工作区总 diff 作为本 Task 的改动。恢复先读取当前字节及相对上次候选的差异，保留同组任务已做的修改。

## 数据与确定性 API

Run 增加 `scheduler: {events: []}`。日志是资源决策唯一来源，`replay(data)` 派生 groups、当前组、leases、stopped、requests、active、windows、scope；不把该视图再写成第二份状态。每项原 state 增加 waiting；waiting 的 result=null，原 checkpoint.pending_call 和调用预算保留。

每个事件有递增 `id`、带时区 `at`、当前 `generation`。请求 FIFO 使用独立递增 seq，不用墙钟或 agent 回复先后猜顺序。通过 `append_event(data, kind, when, **payload)` 准备完整提案，再走 guard update 的摘要比较、owner/代次和文件锁；不能直接写 Run。可一次发布同一决策的连续事件，但禁止混入新阶段派发，交付仍逐项落盘。

| 事件 | 必需载荷／效果 |
|---|---|
| group | members（一至两项）、before（每项路径摘要）、before_refs（每项实际快照引用）；保留全部预计修改范围 |
| wait | slug、call_id（尚无调用时为 null，否则绑定最近调用）、resource、完整 scope、candidate、stop；暂停并释放全部文件，创建新的 FIFO 请求 |
| agent_ready | seq、agent_ref、source；原阶段已闭合后，先保存实际角色绑定，再登记可用；不可用的角色申请不阻挡安全验证窗口 |
| grant | seq；files/agent 另提供 before、before_ref，verification 提供当前稳定 candidate；只能授予可执行申请中最早者 |
| barrier | candidate；全组停止写入、零占用、没有可继续的文件／角色申请后进入稳定验证窗口 |
| finish | seq、stop、outcome（passed/failed/inconclusive/interrupted）、source；结束一个验证命令，原阶段的文件续接申请排到队尾 |
| window_end | 验证申请处理完且无在途命令，返回可写窗口；此前不得继续生产写入 |
| invalidate | slug、stage（flow 内的 review/validate）、新 candidate、实际变化 paths、source；撤销临时完成依据，自动排入文件续接队列 |
| abort | slug、call_id、stop、state（failed/blocked）、reason、source；停止失败成员、取消申请并释放文件，保留原 pending 和已授予命令的不确定执行事实；已终态项原结果不改写 |
| close | 最后稳定 candidate；失败项另有逐项 residuals 安全依据；成功项均须等待 finalization，输入仍匹配且无 pending call |

`scope={mode,files,dirs}`；`candidate={snapshot,sha256,inputs}`。snapshot 指向不可变可复核材料，sha256 为真实清单摘要；不能填占位摘要。`stop={agent_id,host_id,tools_stopped:true,observed_at,source}` 必须匹配该 call 原角色，不早于调用意图、实际派发和最近资源授予。仅尚无调用时 call_id=null、agent_id=null，并提供实际未调用依据；已有 prepared 或 dispatched call 均须绑定该 call 的实际 agent_id/host_id，不能用 null 绕过核验。

FIFO 只在当前可执行申请之间成立：文件不可得者保留 seq，跳过它继续能执行者；等待时不持有部分文件。verification 一次只授予一个，所有业务写入禁止；files/agent 必须取得完整范围。调度无可执行动作时保留原因，不用超时抢占。等待仍占小组名额。

## 阶段内请求与原 call 续接

派发时提供协议0.11、Run/执行实例/代次、slug、call、agent_ref、scope、候选、项目规定的验证入口和资源请求位置。Cohestra 实际安装副本必须支持本约定及正式契约0.8，不从版本号大小推断兼容。

子 agent 在安全边界结束所有写入／子进程，写唯一不可变文件：

`.yuzio/cohestra/handoffs/<slug>/scratch/resources/<唯一标识>.json`

请求正文使用 UTF-8、键排序、无额外空白的 JSON，字段为 `run_id,generation,slug,call_id,agent_ref,resource,scope,candidate`；verification 另有完整 argv。向主 agent 报告请求路径，结束本次工具执行回合。不得发布正式阶段 completed／blocked／failed handoff、改 Cohestra Front Matter 或继续下一阶段。

主 agent 用正式宿主工具核实原角色及全部相关工具停止，保存 wait；未闭合 call 的 wait 还保存 `request={path,sha256,body}`。guard 回读实际请求字节和摘要，核对身份、阶段、代次、资源及 argv。每个请求路径在整个 Run 内只消费一次，必须是规范相对路径；拒绝大小写／Unicode别名、空组件、`.`、`..`、符号链接和硬链接。重试或新的验证动作须由原角色生成新的唯一请求文件，不能重新消费旧请求；同一调用预算不因新请求增加。请求是待核查数据，不扩大 Task 授权；实际工具执行前仍检查项目入口／参数／权限。

grant 落盘回读后才向原 agent 继续原 call；传递原暂停点、有效授予及当前输入。不能重跑已完成阶段、重复计费或让替代者接手未闭合 call。prepared 到 dispatched 是实际派发边界，须再次检查 Run、当前组、完整租约和 stop_queue_on_failure。历史派发补记仅增加事实，不重新启动工具；dispatch_evidence 增加 `historical={observed_at,source}`，提供当前宿主核实来源，派发时间不得晚于已记录的停止／释放／验证屏障边界。没有可核实边界则保持现场，不猜测。开始命令和结束命令分别记录真实工具来源；prepared/granted 均不是命令未执行或执行成功的证明。

角色等待仅发生在原阶段已闭合／未开始时，wait 另有预期 stage。实际角色未可用前不可授予文件；先独立保存匹配角色绑定，再写 agent_ready。角色等待不派发工程阶段；阶段内等待仍保留原 call。无法原角色续接，或命令已授予但执行事实不明时，按既有恢复规则受阻／失败并保留现场，不盲目重放。

## 验证窗口与最终候选

code/fix 内也可能需要构建。任何阶段均可申请互斥验证，不要求所有成员先完成评审；否则 code 的必要编译会与“等 code 完成”相互等待。

- 一项申请验证后继续让另一项自然推进，直到双方处于已确认停止写入的等待点／阶段边界。不得暂停正在写文件的工具，也不能只把状态改成 waiting。
- 没有可继续的文件／角色申请，且全组零文件占用，才固定整体输入与 candidate 并建立 barrier。所有构建、主机测试、快照捕获和项目声明的互斥验证统一按 FIFO 执行。Cadra 不内置 Mewoo 路径或命令。
- 单个验证结束，worker 可报告结果和暂停点，但不能自动恢复生产写入；finish 把续接请求排队，window_end 后才可重新授予。失败后的修改也等验证队列处理完再进行。
- 每次命令核对当前整体候选及请求的输入／argv，证据绑定实际受测版本。共享工作区的两次构建不代表两个独立代码版本。
- 临时完成项进入 finalization 等待，不立即将 Run 条目标为 completed。组收尾对照每项证据记录的输入和最后整体输入；仅无关新路径不使证据失效，相关输入改变则保存 invalidate，再在已授权 flow 内真实复审／复验。
- 原验证已 finish、原 call 已核验闭合且只剩过程交付时，finalization 的 wait 可原子取消该 call 尚未授予的文件续接请求，再登记 finalization；不授予业务写入、不新增调用或预算。停止策略仍禁止新工程派发，但不阻止这条已完成结果的收尾路径。其他文件申请、未结束验证或未闭合 call 不得如此取消。
- refresh 调用保存原 before 和完整 invalidate 事件引用；不改旧 next，不复用已消费的刷新依据。超出 flow、缺独立审查或未解除产品／权限决定时 blocked。正式契约真值核验仍按 [契约](contract.md)，调度器不凭空替代验收。
- close 后逐项保存成功终态与实际结果，再开启下一组；失败项先用 abort 取消其资源申请，否则失败等待者可能阻挡另一项验证；残留安全依据与工具停止观察不可省略。未知／不安全残留导致整组受阻，不自动撤销用户或其他任务的字节。
- 每个 completed 条目都必须属于已 close 的小组；无需新阶段调用的核对收尾同样经过 finalization 和最终候选核验，不能由 queued 直接跳到 completed。

## 中断、预算与报告

正常排队、wait/grant/finish、原 call 续接与交付回读不新增调用预算。真实新 review/validate 仍计调用总额；真实整改和阶段失败重试沿用既有16/3/2上限。等待不是 Cohestra stage_failed，不能消耗重试后再创建 call 绕过原 pending。

恢复前核查主执行者和全部历史角色／工具；不凭 waiting、无进展或宿主 idle 判断已停止。takeover 只换 owner/代次并保留全部日志、seq、scope、组、call、预算；每次授予均按原角色的实际停止观察核对当前代 claimed_at；请求新建于当前代或finish生成续接均不证明观察新鲜。缓存观察早于claimed_at时必须重新观察，不能用请求的generation绕过；补记旧命令 finish 可使用它真实结束时的历史观察。已授予的命令先核对真实结果；有完整结果只补 finish，无明确未执行依据不得重放。新代不能重写旧请求或把旧文件的 generation 改成新值。

用户停止或 stop_queue_on_failure 停止整个 Run 的后续派发；策略停止不因小组 close 或切换成员而解除，禁止建立后续小组、创建新调用和授予资源。确认在途角色／工具后保存真实状态；只对未开始任务 skipped。已完成结果的过程收尾和有真实证据的历史派发补记仍按原规则办理，不产生新的工程执行。无法确认工具或残留状态时保留未完成组。list/report 从日志派生等待原因、排队序号、时间、候选与恢复点；没有命令结束证据时不虚构验证耗时。

排队时间按请求登记至授予计算；授予至finish是验证资源占用时长，实际命令开始／结束与耗时以真实工具日志为准，不混为纯模型时间或构建CPU时间。

原请求尚未授予、普通文件申请未满足或验证尚未 finish 时，原 call 必须保持未闭合，不能把请求返回当成正式交付，也不能替换 checkpoint.last_delivery。验证命令已 finish 后，若阶段只剩本任务过程交付、没有业务写入，可核验真实 handoff 并闭合原 call；finish 派生的文件续接记录以 resume_of 关联原验证，可在进入 finalization 时按上述条件取消。后续工程阶段仍需完整租约。

# run

通过 $cadra run 调用；与 [公共流程](workflow.md) 一起执行。建立一次 Run，并按既定顺序无人值守串行推进队列内的 Task。

## 调用

```text
$cadra run
范围：<task-slug 列表，或“全部 ready”；可空取全部 ready>
恢复：<本次明确要求恢复的 blocked/failed slug 列表；可空>
补充：<本次限定条件，可空>
```

修订后的终态任务经 `ready` 放行后由范围选中（按第 6.3 节重启），不写进恢复列表；恢复列表只收 blocked/failed 状态的任务。

## 建立 Run

1. 先做 [公共流程](workflow.md) 第 6.1 节的两项前置检查：目标绝对路径明确、可安全写入、是 Cohestra 可初始化的 Git 工作区（从子目录取 Git 工作区根，worktree 取自身根），非 Git 目录、目标不明确或指向技能源仓库时停止，不建 Run、不入队，也不自行 `git init` 或代建 `.cohestra`（缺容器由 Cohestra 在首个阶段调用时最小初始化）；再核对本次加载的 Cohestra 技能可用性与不存在未完成 Run。缺依赖或已有未完成 Run 时停止，给出缺口或准确的 resume 调用，不建 Run、不逐任务判 failed。
2. 校验范围与恢复参数（[公共流程](workflow.md) 第 6.2 节）：恢复列表非空时范围必须是显式 slug 列表，且恢复列表是其子集；其中不存在或非 blocked/failed 的任务一律拒绝本次参数，不自动扩大选择。
3. 只读取范围内 Task、相关依赖状态、归属 Run 与必要 checkpoint。普通任务按第 4 节准入；恢复项按第 2.1、6.2 节核对，记录来源 Run、解除证据、授权与首个动作；带未消费修订记录 `rev-<N>` 的 ready 任务按第 2.1、6.3 节做修订重启准入，记录原终态与重启起点。未通过恢复或修订重启核对的保持原状态（修订项保持 `ready`、不入队），其余不满足准入的逐条说明原因；没有合格任务时停止。
4. 对合格候选执行第 6.1 节分类，确定每项是首次启动、正常接续、恢复重试、恢复核对收尾、修订重启或修订收尾。任何前置检查未过或契约未就绪时停止本次 run；所有前置检查均发生在建 Run/入队前。
5. 生成 run-id `run-<YYYYMMDD>-<NN>`，按 [公共流程](workflow.md) 第 4 节第 7 条的三步写入完成入队，按 [Run 骨架](../assets/run.md) 写本次定义快照、逐 Task checkpoint、首个动作与来源（恢复来源或修订记录 `rev-<N>`）：先写 Run 文件并记入队操作编号 `enq-<run-id>-<NN>` 与写入进度，回读后再更新 Task 状态（普通任务与修订重启任务 ready → queued，恢复任务 blocked/failed → queued），最后追加 [队列清单](../assets/project/queue/order.md) 行并回读。保留原 Run 的结果与队列行，修订项两代定义快照分别保留。无可执行或核对收尾的项不空建 Run。**入队过程中断留下部分写入时**（Run 已存在而 Task 未更新或队列缺行），不重写、不新建 Run：如实报告中断点，交由 `resume` 按同一编号幂等补齐（第 4 节第 7–9 条）。

## 串行执行

1. Run 以 `execution_mode: unattended` 向下游声明，随后逐个执行：同一时间至多一个 Task 处于 `running`（`parallelism = 1`）。
2. 对每个 Task：queued → running，按前置检查记录的首个动作进入；开始前重读相关状态，若较前置检查发生变化则重新核对，不能沿用失效的首次启动、恢复或修订重启授权。重核含 Ready Gate 第 6 条依赖口径：任一依赖落盘状态非 `completed`（含被修订回 `draft`/`ready`）时，不调用任何阶段，按 [公共流程](workflow.md) 第 4 节第 4 条记 `blocked`（依赖未满足）并出队；`stop_queue_on_failure` 照常生效。
   - 恢复核对收尾与修订收尾不调用阶段，保存核实来源、`rev-<N>`（如适用）及本 Run 的结果快照；修订收尾落盘回读后关闭对应修订记录，中断时只补齐同一收尾。
   - 需要调用时按第 6 节「本次结果核对」先落盘调用原因、拟调用阶段、本次声明的 execution_mode 与调用前阶段/轮次，回读后调用 `$cohestra <阶段>`。后附 cohestra_task 目录、Task 绝对路径、execution_mode: unattended，并声明该 Task requirement 为本次上游依据；恢复或修订重启时同时传递本次补充、原因解除证据与 `rev-<N>`。一次只调用一个阶段，不把中链起步当作缺 need 输入。
   - 先核对本次索引同步结果、阶段/轮次与 execution_mode，再读取结构化控制状态并闭合该 Task 的 checkpoint，追加本次调用记录：交付阶段及结果、轮次、当前候选、findings、acceptance 与来源。失败、旧结果或执行模式不符按第 6 节停止该 Task，不消费旧 next。
   - 先按第 6 节终态映射确定**是否还需要再调用**（完成、受阻、失败与正常 flow 边界在此终止，收尾结论不因上限改判）；确需调用时，才在调用前检查并落盘三项上限的消费：任务调用预算（每次调用）、整改轮（原因是 `blocking_findings` 的 `fix` 调用）、逐阶段失败重试预算（可重试失败后的重试调用）。新结果按调用标识只计入一次并写入 checkpoint；任一上限达到即记 `failed`（重试上限耗尽／整改轮上限耗尽／调用预算耗尽），不无限重试、不无限整改，也不让后续任务无限等待。
   - 无进展按第 6 节已收窄的判据执行：validate 的本阶段补证出口不判无进展（改由调用预算兜底），其余同阶段连续两次结构化状态全未变时即刻停止并记 `failed`。
   - 不机械执行 preset 的全部阶段，也不自行发明阶段；推进与终态一律按 [公共流程](workflow.md) 第 6 节的**终态映射表**判定，不另设口径。
3. unattended 期间的 verify 按 [公共流程](workflow.md) 第 7 节跳过并在运行记录中注明理由。
4. 状态变化即时落盘并回读 checkpoint，保证中断后可从 [resume](resume.md) 恢复。
5. 默认 `blocked` / `failed` 记录后继续下一个 Task；该 Task 配置 `stop_queue_on_failure: true` 时停止队列：Run 记 `stopped` 并写明停止原因，队列内未执行任务出队回 `ready` 并记为报告口径的 `skipped`（[公共流程](workflow.md) 第 2 节调度回边）。重试上限耗尽、整改轮上限耗尽、调用预算耗尽与执行模式核对失败同样落到 `failed`，受同一策略约束。
6. 每项结束按 [公共流程](workflow.md) 第 4 节第 8 条的三步写入完成出队：先写该 Run 的结果快照与出队结论，再把 Task 写为对应终态（停止收尾时回退 `ready`），最后回写队列行的 `deq-` 编号、结论与时间，逐份回读。**Run 结果快照、Task 状态与队列行三者一致才算收尾**；写 Run 后中断时由 `resume` 按同一编号补齐 Task 与队列行，不放行新 Run。队列走完（全部 Task 到达终态）→ Run 记 completed，即使其中含 blocked/failed 也保留此 Run 的结束事实；未变更定义的 blocked/failed 后续经显式恢复进入新 Run，终态任务变更定义则按第 2.2、6.3 节修订重启，不重开旧 Run。

## 边界

- 不修改 `.cohestra` 内容，不复制 handoff 正文进 `.cadra`；unattended 期间的交互与决策禁区见 [公共流程](workflow.md) 第 7 节，本入口不重复。
- 不做并行执行、DAG 调度、定时器、daemon 或 Agent 动态选择；执行者就是本会话的编排者，阶段工作由 Cohestra 协议承担。
- 未闭合的执行（会话中断、checkpoint 未写完）不宣告成功，如实报告中断点。

## 交付与停止

更新 `runs/<run-id>.md`、`queue/order.md` 与各 Task 状态；落盘规则见 [公共流程](workflow.md)。

未完成 Run 推荐 resume，已结束 Run 推荐 report。blocked/failed 需要恢复时给出 `$cadra run` 加显式范围、恢复列表与缺失前提，不推荐重开旧 Run；需求或 flow 已变时先 `$cadra add` 修订并由 `ready` 重新放行，再按修订重启入队。

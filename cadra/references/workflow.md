# 公共流程 · cadra v0.5

Cadra 管理多个待执行任务，并在无人值守场景下按既定顺序串行推进。本文件定义 Task 与 Run 的状态机、队列与顺序、Flow Preset、Cohestra 调用契约、unattended 规则和落盘规则；入口特有行为见各入口说明。先读本文件与所选入口说明，再按需读取任务或 Run 材料。

## 术语

- **Task**：待执行任务，落盘为 `.cadra/tasks/<task-slug>.md`，记录 title、slug、requirement、priority、dependencies、flow、execution policy 与状态。
- **Ready Gate**：Task 从 `draft` 进入 `ready` 的准入检查，八条全部满足才放行；恢复与修订重启入队同样复核，定义见第 2.1 节。
- **Queue**：待执行队列，清单落盘为 `.cadra/queue/order.md`，记录入队顺序、消费 Run 与出队结果。
- **Run**：一次串行执行，落盘为 `.cadra/runs/<run-id>.md`；run-id 形如 `run-<YYYYMMDD>-<NN>`，当日序号两位起、不截断。
- **flow preset**：候选阶段序列，只声明序列与 Cohestra 起始阶段，不拥有阶段业务语义，见第 5 节。
- **execution policy**：Task 级执行策略，V1 只含 `stop_queue_on_failure`，缺省 `false`。
- **checkpoint**：Run 文件中每个 Task 的执行进度记录（入队写入进度、拟调用阶段、调用前阶段/结果/轮次、最后交付阶段/结果/轮次、索引同步核对、当前候选引用、最近结构化状态、调用预算与整改轮、闭合标志），是 resume 的唯一恢复依据。「最后完成阶段」栏记录最近交付结束的阶段，不代表该阶段通过。
- **调用预算与整改轮**：Task 级执行上限，V1 固定为同一 Run 内单个 Task 的阶段调用总数不超过 16 次、由 `blocking_findings` 触发的 fix 交付不超过 3 轮；两者与逐阶段失败重试预算分别计算，见第 6 节。
- **入队／出队操作编号**：`enq-<run-id>-<NN>` 与 `deq-<run-id>-<NN>`，唯一标识一次入队或出队的写入；部分写入只按同一编号幂等补齐，见第 4 节。
- **结构化状态**：Cohestra 写在任务 README YAML Front Matter（Orchestrator 契约）中的机器可读状态；载体固定、逻辑字段与终态映射见第 6 节，Cadra 只读这些字段决定流程。
- **报告轮次**：同一 Run 的第几份执行摘要；与 Cohestra 的阶段轮次无关，编号两位起、不截断。
- **出队**：任务离开队列的动作：执行完毕记终态，或 Run 停止收尾时回退 `queued → ready`（第 2 节调度回边）；V1 不提供单项移出入口。
- **unattended**：无人值守执行模式，run 启动时向下游声明 `execution_mode: unattended`。
- **串行**：`parallelism = 1`。同一 Run 同一时间至多一个 Task 处于 `running`；不做并行执行、DAG 调度、定时器或 daemon。

## 1. 项目存储

```text
.cadra/
├── README.md          # 容器入口
├── tasks/
│   └── <task-slug>.md # Task 定义、状态与运行记录
├── queue/
│   └── order.md       # 队列清单
└── runs/
    ├── <run-id>.md          # Run 记录与 checkpoint
    └── <run-id>-report-<轮次>.md   # 执行摘要（report 入口生成）
```

职责划分：`.cadra` 保存多任务执行和调度状态；`.cohestra` 保存单任务流程与工程证据。不得把 Cohestra handoff 内容复制进 `.cadra`，一律通过引用关联：

```yaml
cohestra_task: .cohestra/handoffs/<task-slug>/
```

其中 `<task-slug>` 必须与该 Task 的 slug 一致，由 `add` 建立引用与 `run` 调用时校验；两技能的任务目录命名以此绑定，不另立对照表。队列清单的列定义见 [队列清单模板](../assets/project/queue/order.md)，由首次入队按模板创建（最小初始化已带表头），旧版清单按模板的升级规则追加新表块；`queue/order.md` 不存在表示尚无队列记录，不算缺口。

报告中的 findings 摘要、validation 结果等只写短摘要并标注来源文件，不搬运正文。容器缺项时按 [SKILL.md](../SKILL.md) 执行规则第 2 条最小补齐，不重写既有文件。

## 2. Task 状态机

```text
draft
  ↓
ready
  ↓
queued
  ↓
running
  ├── completed
  ├── blocked
  └── failed
```

状态回边（只经授权入口发生；定义修订另保留新旧两代事实）：

```text
queued  → ready    # Run 停止收尾，未执行任务出队
blocked → queued   # run 显式恢复，准入通过后进入新 Run
failed  → queued   # run 显式恢复，准入通过后进入新 Run
ready   → draft    # Ready Gate 复核失败，或影响准入的定义变更
completed → draft  # 终态任务的定义修订，重新执行见第 2.2 与 6.3 节
blocked   → draft  # 同上
failed    → draft  # 同上
```

| 状态 | 含义 | 进入方式 |
|---|---|---|
| draft | 已创建或编辑（含终态修订回退），尚未通过 Ready Gate | `add` 创建/编辑后，或终态定义修订回退（第 2.2 节） |
| ready | 已通过 Ready Gate，可被选入队列 | `ready` 放行 |
| queued | 已入队，等待串行执行 | `run` 选中普通任务、显式恢复任务或修订重启任务入队 |
| running | 正在执行 Cohestra 阶段 | `run`/`resume` 开始执行 |
| completed | 执行完成，Cohestra 流程闭合 | 结构化状态 `status = completed` 且按第 6 节终态映射表判为完成 |
| blocked | 任务本身无法继续 | 见下方定义 |
| failed | 执行发生异常 | 见下方定义 |

**blocked**：任务本身无法继续，例如缺人工决定、缺权限、缺输入、依赖未满足、Cohestra 明确禁止继续（`blocked.value = true`）。

**failed**：执行发生异常，例如 Agent 执行异常、工具调用失败、无法读取必要状态、协议输出不合法、无法恢复执行状态。

默认处理：

```text
blocked → 记录 → 继续下一个 Task
failed  → 记录 → 继续下一个 Task
```

Task 可显式配置 `stop_queue_on_failure: true`：该 Task 到达 `blocked` 或 `failed` 终态时停止队列，Run 记 `stopped` 并给出停止原因，队列内未执行的任务出队回退 `queued → ready`，并在该 Run 的报告中记 `skipped`（`skipped` 只是报告分类，不是 Task 状态；任务回到 `ready` 后可被后续 Run 重选）。

状态只由 Cadra 写入 Task 文件，Cohestra 不回写 Task 状态；转换必须即时落盘，保证中断后可恢复。`completed`、`blocked`、`failed` 在本轮 Run 内是终态，`resume` 不重开这些任务；`blocked`/`failed → queued` 只能由 [run](run.md) 的显式恢复选择触发，进入新 Run，不能覆盖原 Run 的结论；`completed`/`blocked`/`failed → draft` 只在定义修订时发生（第 2.2 节），其重新执行按第 6.3 节确定，不复用旧 `next`。

### 2.1 Ready Gate 与定义编辑

八条全部满足才放行；`ready` 的检查与 `run` 的恢复/修订重启准入共用下表，不重复定义：

| # | 检查项 | 判定口径 |
|---|---|---|
| 1 | 目标明确 | requirement 的目标可判定，不是待探索的方向 |
| 2 | 范围明确 | 做什么、不做什么清楚 |
| 3 | 验收条件明确 | 有可判定的验收条件，完成现象清楚 |
| 4 | 无必须由人类决定的问题 | 无待裁决的产品决策、取舍或授权问题 |
| 5 | 必要输入完整 | 输入、参考与环境前提齐备 |
| 6 | 依赖满足 | dependencies 中所有 Task 的落盘状态为 completed |
| 7 | Cohestra 起始阶段明确 | flow 首项为六阶段名之一；首次启动、接续、恢复与修订重启的首个阶段按第 6.1、6.2、6.3 节确定 |
| 8 | 执行流程明确 | flow 为已定义 preset，或按第 5 节校验通过的显式序列 |

定义字段含 title、slug、requirement、priority、dependencies、flow、execution policy、cohestra_task。`add` 在任何定义写入前核对 Task 的 Run 归属及未完成 Run 的队列记录；属于未完成 Run 时拒绝编辑，不写 Task、Run 或队列，提示先 `resume` 收尾。归属矛盾或 queued/running 无对应 Run 时也停止，不以改 Task 状态绕过问题。

不属于未完成 Run 的任务按用户明确要求编辑；改变 requirement、dependencies、flow 或 execution policy 必须回 draft，记录原结论与变更原因，重新 Ready Gate；终态任务的回退、两代定义绑定与重新执行见第 2.2 节。只改 title/priority 不使 Gate 失效，也不把 completed/blocked/failed 改为 ready，更不改写其执行结论。slug 与 cohestra_task 是稳定身份绑定，不通过编辑重命名或改绑。`ready` 复核 ready Task 失败时回 draft，追加本次检查结论；保留旧放行事实，不继续沿用旧通过状态。

### 2.2 终态后的定义修订与重新执行

`completed`、`blocked`、`failed` 已发生的执行事实不因编辑改写：定义变更走回退，重新执行走修订重启；两条路径按当前 Task 状态区分，不并行。

- **回退与记录**：终态 Task 的 requirement、dependencies、flow 或 execution policy 变更时，`add` 先按第 2.1 节核对 Run 归属（属于未完成 Run 时拒绝），再把 Task 记回 `draft` 并追加**修订记录**：修订序号 `rev-<N>`、变更字段与原因、时间、旧定义快照引用（原 Run 的入队定义快照）、原 Run 与原终态。原 Run、队列行、历史报告与旧结论不变。
- **绑定两代事实**：Task 文件同时保留旧定义（历史，只读引用）与新定义（本次执行依据），`requirement` 以新定义为准；报告与 Run 快照必须同时标注 `rev-<N>` 与原终态来源，不得用旧 `acceptance`、候选或 `next` 作为新定义的执行结论，也不得把旧 Run 的 blocked/failed/completed 改写成新结果。
- **未消费修订的继续编辑**：Task 已在 draft/ready 且带未消费 `rev-<N>` 时，后续定义编辑仍属于该修订。追加编辑历史，以原 Run 定义快照为基准累计变更字段并保存当前新定义快照；原 Run、原终态及旧定义引用保持不变，不能因当前状态不是终态而丢失修订身份。requirement/flow 曾在本修订中改变，就按新 flow 首项重启；不能只按最后一次 dependencies/policy 编辑选择收尾。影响准入的修改仍回 draft，重新 Gate。
- **重新 Gate**：修订后按第 2.1 节八条重新检查，通过才到 `ready`；slug 与 cohestra_task 不变，修订不删除也不降级旧的 Gate 与执行历史。
- **重新执行**：修订后的 `ready` 既不是普通 ready，也不是首次启动，更不进入 `run` 的恢复列表——该列表只收 blocked/failed 状态的显式选择（第 6.2 节）。它被 `run` 选中后按第 6.3 节做修订重启准入，首个动作由「改变了哪些字段 + 原终态」确定。
- **准入未通过**：Task 保持 `ready`、不入队，记录缺口与所需材料；补齐材料后重新请求 run，或继续修订（回 draft 重新 Gate）。ready 不进入显式恢复列表，也不回写为原终态以绕过准入。修订不是绕过旧受阻状态或旧验收结论的通道。

## 3. Run 状态机

```text
running
  ├── completed    # 队列内 Task 全部到达终态（completed/blocked/failed）
  ├── stopped      # stop_queue_on_failure 触发，或用户显式停止
  └── interrupted  # 会话或执行中断，checkpoint 未闭合
```

- `completed` 与已收尾的 `stopped` 是结束态，不重开；`resume` 只接管下条定义的未完成 Run，接管后回到 `running`。
- **未完成 Run**：状态为 `running` 或 `interrupted` 的 Run，以及 `stopped` 但 `queue/order.md` 中仍有未出队任务的 Run。是否出队按第 4 节第 8 条的**逐行完成判据与合并视图**判定，不看表块新旧：旧表块的行只要自身结论单元格非空即为已出队。只有未完成 Run 会阻止建立新 Run。
- 同一项目同时至多一个未完成 Run；`run`（含恢复建新 Run）与 `resume` 推进前均核对。存在其他未完成 Run 时停止，不并行续跑。
- **入队／出队部分写入**：Run 已建立但入队写入未走完（Task 仍为入队前状态或队列缺行），或 Run 已保存结果快照但队列行未回写时，**不按记录矛盾处理、不新建 Run、不绕开归属限制**。只有 `resume` 能按第 4 节第 7–9 条的同一操作编号判定为同一次写入并幂等补齐；判定依据不足、编号缺失或与实际状态不相容时停止并报告，不补写、不猜测进度。`add` 对未完成 Run 的归属拒绝（第 2.1 节）继续有效，不因补齐需求放宽。
- **Run 收尾**：用户明确不再续跑时由 `resume` 执行。先核对 running Task 的 checkpoint：结果能确认时按第 6 节映射记录实际结论；仍可推进但用户要求停止时记 blocked（用户停止，保留合法 next），不再调用阶段；无法确认本次结果时记 failed 并保留恢复条件。queued Task 出队回 ready，报告口径 skipped，注明“用户放弃/停止”。逐 Task 结果快照与出队结论落盘回读后，Run 记 stopped 并标注“已收尾”与时间；未能写完时如实报告未收尾，不放行新 Run。
- Run 状态与 Task 状态独立记录，不由一方推导另一方。
- 每个 Task 的 checkpoint 在阶段完成、进入终态或中断前必须写盘并回读；checkpoint 未闭合（最后阶段结果未记录）即视为中断点，`resume` 按 [resume](resume.md) 重新核对实际进度。
- `report` 可对未完成 Run 生成阶段性摘要，须标注 Run 当前状态。

## 4. 队列与顺序

1. **串行**：`parallelism = 1`。同一 Run 同一时间只能有一个 Task 处于 `running`。
2. **入队条件**：三类任务分开判定——普通任务为 ready 且依赖全部满足；恢复任务必须为用户在 `run` 恢复列表中明确选择的 blocked/failed，并通过第 2.1 节 Gate 与第 6.2 节恢复核对；修订重启任务为带未消费修订记录的 ready（第 2.2 节），并通过第 2.1 节 Gate 与第 6.3 节准入。三类任务均在所有前置检查结束后才入队；不把恢复检查或修订重启准入当作调用 `ready` 入口。
3. **顺序**：按 `priority` 排序（`high` > `medium` > `low`），同优先级按 slug 字典序稳定排序，结果可复现。同一 Run 不含任务与其未完成依赖（第 2.1 节第 6 条与本节第 2 条要求入队时依赖全部 `completed`），依赖链按层级逐 Run 推进：一层全部 `completed` 后，下一层才能通过 Gate 并入队。
4. 任务开始或续跑前重核依赖落盘状态：任一依赖不是 `completed`（含被修订回 `draft`/`ready`、`blocked`、`failed` 或本轮 `skipped`）时，本任务不调用任何阶段，记 `blocked`（依赖未满足）并按默认规则继续下一个 Task。正常流程不会出现此情形（依赖未 `completed` 的任务不得入队），本条在状态被外部改写、恢复矛盾，或依赖任务原 Run 已结束、在本 Run 排队期间被 `add` 修订时兜底。本任务记 `blocked` 后，由依赖任务先经新 Run 回到 `completed`，用户再在 `run` 恢复列表显式恢复本任务。
5. 普通任务与修订重启任务入队即 ready → queued，恢复任务入队即 blocked/failed → queued；开始执行即 queued → running。队列按 run-id + slug 关联，每次新 Run 追加新行（恢复与修订重启行同时记来源 Run），不覆盖旧行；出队时回写该 Run 行的编号、结论与时间，停止收尾按第 2 节回退 queued → ready。写入步骤与幂等补齐见第 7–9 条。
6. 不提前设计 DAG scheduler；依赖只影响入队判定（第 2.1 节第 6 条），不产生并行分支，也不在同一 Run 内串行链接。
7. **入队写入协议（三步、带操作编号）**：一次入队有唯一操作编号 `enq-<run-id>-<NN>`（NN 两位起、同一 Run 内递增），写入顺序固定，每步回读后才进下一步：
   ① **Run 文件**：写 Run 骨架与该项 checkpoint，其中记录 `enq-<run-id>-<NN>`、入队写入进度 `run-written`、完整入队定义快照与首个动作；回读。
   ② **Task 文件**：状态置 `queued`（恢复任务为 blocked/failed → queued），记所属 Run 与同一编号；回读，并在 Run checkpoint 记入队写入进度 `task-queued`。
   ③ **队列清单**：按 [队列清单模板](../assets/project/queue/order.md) 追加一行，「入队操作编号」列写同一编号；回读后在 Run checkpoint 记入队写入进度 `complete`。
   队列行存在且带该编号即入队完成，进度标记只是恢复用的辅助信息。**Run 文件先写、队列清单后写**：队列清单缺失或落后于 Run 记录时，以 Run 中保存的编号与定义快照为唯一依据补齐，不反向覆盖 Run、不凭文件修改时间推断。
8. **出队写入协议（三步、同编号方向）**：出队有唯一操作编号 `deq-<run-id>-<NN>`，写入方向与入队一致——先写靠前的文件、后写队列清单，每步回读：
   ① **Run 文件**：写该项的结果快照与出队结论（Task 终态，或调度回退「回 ready（本轮 skipped，原因）」）并回读；**该结果快照写入即表示该 Task 进入出队阶段**。
   ② **Task 文件**：状态写为快照结论——终态 completed／blocked／failed，或停止收尾时回退 `queued → ready`；回读。
   ③ **队列清单**：**按行就地写入该行自己的结论列**——定位一律以**消费 run-id + slug** 为基准键，`enq-<run-id>-<NN>` 只在存在时用于区分同一键下的多行：新表块的行写其「出队操作编号与结论」列，旧表块（无 `enq-` 列）的行**就地写入它既有的「出队结论与时间」单元格**（这是旧协议本来就有的写入，不新增列、不迁移、不改写已出队的行）；逐行回读。v0.4 及更早的 Run 与队列行没有编号，不因此停止。
   出队完成的判据**按行自身**：新表块的行带该 `deq-` 编号，旧表块的行其结论单元格非空；旧行不因缺 `deq-` 编号被判为未出队。**放行新 Run 前，Run 结果快照、Task 状态与队列行三者必须一致**；不一致时先按第 9 条判定是部分写入还是记录矛盾，不放过、不猜测。
9. **补齐范围（先分阶段，再按阶段补齐）**：幂等补齐**只允许「补齐尚未写入的步骤」**——不重复追加队列行、不重写已有结论、不动其他 Run 的行。
   - **先判定阶段**：读 Run 中该 Task 有无结果快照。无结果快照 → 处于**入队阶段**，按入队规则；有结果快照 → 已进入**出队阶段**，按出队规则。不得只凭 Task 状态的字面值判断：`blocked`／`failed` 既可能是恢复任务入队前的原状态，也可能是本 Run 的终态。
   - **入队阶段补齐**：Run checkpoint 中该 Task 的 `enq-<run-id>-<NN>` 与定义快照存在，且与实际读到的 Task 定义（slug、cohestra_task、requirement、flow）一致时，判为同一次入队——Task 仍为入队前状态且本 Run 无该 Task 的阶段调用记录时补第 7 条 ②③；Task 已是 `queued`/`running` 而队列缺行时只补 ③。
   - **出队阶段补齐**：以 Run 的结果快照为唯一依据——Task 状态与快照不符（仍为 `queued`/`running`，或快照为 `skipped` 回退而 Task 尚未回到 `ready`）时补第 8 条 ②；该行结论列为空时补 ③（新表块补 `deq-` 编号与结论，旧表块就地补它既有的结论单元格）。
   - **旧记录例外**：v0.4 及更早的 Run 与队列行没有 `enq-`／`deq-` 编号，**编号缺失本身不是停止条件**——定位用消费 run-id + slug，核对用 Run checkpoint 的「入队定义快照」与结果快照，回写落在该行自身既有的结论列。只有既拿不到编号、又无法用 run-id + slug 唯一定位时才停止。
   - **停止情形**：同一 run-id + slug 匹配到多行且无法用 `enq-` 编号区分、定义快照与实际 Task 不一致、入队阶段出现「入队前状态却已有阶段调用记录」、Task 状态与 Run 结果快照互不相容（如快照为 completed 而 Task 为 `ready` 且无 `skipped` 回退记录）、Run 快照与队列结论互相矛盾——一律停止并报告，不补写、不猜测。
   部分写入未补齐前不调用任何阶段、不新建 Run、不改 Task 定义。

## 5. Flow Preset

Cadra 只声明阶段序列。首版 preset：

```yaml
full:
  - need
  - design
  - code
  - review
  - fix
  - validate

feature:
  - design
  - code
  - review
  - fix
  - validate

small-change:
  - code
  - review
  - fix
  - validate

bugfix:
  - fix
  - review
  - validate

review-only:
  - review
```

- preset 序列的第一项是**声明的期望起始阶段**；第 6.1 节确认首次启动时调用首项一次，修订重启按第 6.3 节也以新 flow 首项为起点，已有任务以结构化状态接续，恢复按第 6.2 节选择首个动作。
- preset 的末项即声明的终点范围：需要在 validate 之前收尾的任务选用 `review-only` 或显式序列，不依赖 Cohestra 的「用户声明终点」——该声明不进契约，Cadra 无从核对（第 6 节终态映射表第 7、8 行）。
- Task 的 `flow` 可写 preset 名，也可写显式阶段序列；显式序列同样只是候选序列。**preset 名与等价显式序列必须得到相同的准入结果**，校验口径统一为：显式序列必须是 `need → design → code → review → fix → review → validate` 的**非空子序列**——整体按链序单调前进，其中 `review` 至多出现两次且第二次必须落在某个 `fix` 之后（Cohestra 的必要复审路径，`bugfix` 即此形状），其余阶段各至多一次；此外的逆序、乱序与重复一律由 [add](add.md) 拒绝。因此 `flow: bugfix` 与 `flow: [fix, review, validate]` 等价，`[need, design, code, review, fix, review, validate]` 与 `[review, fix, review]` 同样合法；序列含某阶段名即允许 `next.stage` 指回该阶段（如 `[code, review, fix, validate]` 可承接验收失败后的 fix），不要求序列位置与当前进度一一对应。
- **Cadra 不拥有这些阶段的业务语义**，也不得依据 preset 机械执行全部阶段。首次启动、显式恢复与修订重启的首个动作分别按第 6.1、6.2、6.3 节；此后的阶段调用仅在 next.allowed = true 且 next.stage 在 flow 内时发生。
- `next.stage` 不在 flow 序列内、`next.allowed = false`，或 `status = completed`（Cohestra 流程闭合）时，按第 6 节的终态映射表与 [run](run.md) 的规则处理，不自行发明阶段。
- 阶段名与 Cohestra 入口一致：need、design、code、review、fix、validate。

## 6. Cohestra 调用契约

Cadra 只依赖机器可读的结构化状态决定流程。**载体固定为 `cohestra_task` 目录下任务 README 的 YAML Front Matter**（Cohestra 称“Orchestrator 契约”），由 Cohestra 写入与维护，Cadra 只读不写。**字段名与取值逐字采用 Cohestra 公共流程第 7.2 节「字段」的原文，Cadra 不另立别名、不做同义改写**，只声明自己读取其中哪些字段：

```yaml
contract: "0.8"  # 必填；当前支持的 Cohestra 契约版本
task:            # 任务标识，必须等于本 Task 的 slug
status:          # 任务状态：in_progress | completed | blocked | failed
execution_mode:  # attended | unattended；必填，核对本次声明
stage_result:    # 刚结束的阶段与其结果
  stage:         # need | design | code | review | fix | validate
  status:        # completed | blocked | failed
  round:         # 阶段轮次，整数；用于本次结果核对与中断恢复
candidate:       # 必填映射，报告与候选核对来源；无候选时两叶为 null
  commit:        # sha 或 null
  snapshot:      # 可复核快照来源（handoff 路径）或 null
findings:        # 未关闭问题计数（review/fix 交付后维护，可省）；报告素材
  blocking:      # 未关闭必做数，整数
  non_blocking:  # 非必做数，整数
  unresolved:    # 待核实未裁决数，整数，可省
acceptance:      # 验收结论（validate 交付后维护，可省）
  status:        # passed | failed | pending | blocked
next:            # 下一阶段与是否允许执行
  stage:         # 六阶段名 或 null
  allowed:       # true | false
  reason:        # stage_completed | blocking_findings | acceptance_failed | stage_failed | task_completed | human_decision_required | blocked | other
blocked:         # 受阻标志与原因
  value:         # true | false
  reason:        # human_decision_required | missing_input | missing_permission | dependency_unavailable | environment_blocked | candidate_unavailable | other | null
```

- **版本同步**：契约版本随 Cohestra 协作协议演进。Cohestra 协议升级后、Cadra 发布支持新契约的版本前，既有任务按新协议交付的契约将判为契约未就绪（第 6.1 节）。两技能在同一仓库维护，协作协议版本变更时同步发布。

- 读取规则：`stage_result` 决定刚完成阶段的结果；`next.stage` + `next.allowed` 决定下一阶段；`blocked.value = true` 时本 Task 记 `blocked` 并记录 `blocked.reason`；`task`、`status`、`acceptance.status` 用于一致性校验与终态判定（见下表），不单独驱动阶段。
- 读取的 `status` 是 Cohestra 的任务状态，**不是** Cadra 的调度状态：Cohestra 契约中没有 draft／ready／queued／running，两类状态不互相推导、不混写。
- 报告素材字段（只读）：`candidate`（被审查／验收的固定候选）、`findings`（未关闭问题计数）；二者不单独决定阶段。`acceptance` 同时用于下表的终态／边界判定与报告。报告与 list 的候选、findings、验收摘要优先取这些结构化字段，正文只作补充。
- `execution_mode`：核对 Cohestra 记录的执行模式与本次声明一致，核对结果纳入「本次结果核对」。**核对失败即停止分支**：声明 `unattended` 而契约记为 `attended`，或该字段缺失、取值非法时，本次结果不成立——不消费本次 `next`、不推进、不判 `completed`，按终态映射表第 1 行记 `failed`（执行模式核对失败），保留调用前记录、契约原值与恢复条件并列入需人工介入；即使 `next.allowed = true` 且阶段落在 flow 内也不得继续。
- **Cadra 不解析 Cohestra 自然语言正文来决定流程。** 例如禁止解析 README 中“建议下一步进行 fix”这类句子来选阶段；正文只可作为报告中的短摘要素材。
- 结构化状态缺失、无法读取、字段不合法，或 `task` 与本 Task 的 slug 不一致时，本 Task 记 `failed`（无法读取必要状态／协议输出不合法），不猜测、不用正文倒推。
- **本次结果核对**：每次调用前把拟调用阶段、本次声明的 `execution_mode` 与已读取的 `stage_result.stage/status/round`（尚无结果时记无）写入 checkpoint 并回读，闭合标志记未闭合。调用后先确认索引发布与回读成功，再读取契约：`stage_result.stage` 必须等于拟调用阶段；若调用前也是该阶段，`round` 必须严格增加，阶段不同则不比较轮次大小（各阶段独立编号）；`execution_mode` 必须与本次声明一致。首次结果须含合法轮次并同样核对执行模式。执行返回 `index sync failed`、不能确认同步完成、仍为旧结果、阶段不匹配或执行模式不符时，该 Task 记 `failed` 并保留调用前记录及恢复条件，不读取旧 `next` 推进。同步失败是执行结果信号，不是对 README 正文的控制流解析；即使回读到了新版也不能忽略失败信号。恢复时先核对完整 README 与本轮 handoff（是否完整交付、阶段/轮次、候选与执行模式是否一致），不自动重跑已交付阶段；无法确认则停止。

**终态映射（穷尽，行序即优先级）**：用于调用后的本次结果、正常接续与恢复核对收尾；首次启动、显式恢复重试与修订重启的调用前准入分别见第 6.1、6.2、6.3 节，不先把其旧受阻结果再次判终态。先核对协议与本次结果，再处理失败、受阻和已完成状态，**并据此先确定是否还需要再调用**：完成、受阻、失败与正常 flow 边界都在这一步终止。**只有确定仍需继续调用时**，才检查逐阶段重试预算、整改轮上限、任务调用预算与无进展判据，最后执行该次调用。上限只约束「继续调用」，不改变已经成立的收尾结论——第 16 次交付恰好到达正常边界时按边界收尾，不因预算判 `failed`。正常 flow 边界可以收尾，必做后续超出 flow 不能收尾。

下表的**必做后续**仅指机器字段可确定的情况：`next.reason` 为 `blocking_findings`／`acceptance_failed`／`stage_failed`；或 `stage_result.stage` 为 fix／validate 且 `next.stage = review`（必要复审）；或本轮为 validate 且 `acceptance.status = pending`（验收证据仍不齐）。已知 `acceptance.status` 原值保留在 checkpoint、Run 与报告中，仅字段缺失或为 null 时写 `unknown`，不因 flow 截断抹去失败或未决结论。

Cohestra 的 `task_completed` 可能由「用户声明的终点」触发，该声明只存在于对话与交付记录、不进契约（Cohestra 公共流程第 7.3 节）；Cadra 无从核对声明，第 7、8 行按本 Task flow 是否含 validate 分流即此推断。需要以 validate 之前收尾的任务，flow 应不含 validate（如 `review-only` 或显式序列，见第 5 节）。

| # | 结构化状态 | 判定 |
|---|---|---|
| 1 | 结构化状态缺失、无法解析、字段不合法（`next.allowed = true` 时 `next.stage` 必须是六阶段名，为空或非法即不合法）、`task` 与 slug 不一致，或本次结果核对失败（含索引同步失败、`execution_mode` 与本次声明不符） | `failed`（记录错误、调用前状态与恢复条件，不消费旧 `next`；执行模式不符时列入需人工介入） |
| 2 | Agent 执行异常、工具调用失败、无法恢复执行状态 | `failed`（记录错误与恢复条件） |
| 3 | `status = failed`，或 `next.reason = stage_failed` 且 `next.allowed = false` | `failed`（记录错误与恢复条件） |
| 4 | `status = blocked`，或 `blocked.value = true` | `blocked`（记录 `next.reason` / `blocked.reason`） |
| 5 | `status = completed` 且 `acceptance.status = passed` | `completed` |
| 6 | `status = completed` 且 `acceptance.status = failed` | `blocked`（验收未通过，缺人工决定后续处置） |
| 7 | `status = completed` 且验收非 passed／failed（缺失、`pending`、`blocked`），本 Task flow 序列含 validate | `blocked`（验收无结论，缺人工决定） |
| 8 | `status = completed` 且验收非 passed／failed，本 Task flow 序列不含 validate | `completed`；保留已知验收结论，无结论才标注 `unknown`，列入需人工介入 |
| 9 | `next.allowed = false` | `blocked`（含 Cohestra 明确禁止继续与需人类决定，不把禁止继续当作正常边界） |
| 10 | `next.allowed = true` 且 `next.stage` 在本 Task flow 内 | 非终态：执行下一阶段（含可重试的本阶段失败与 `blocking_findings` 触发的整改，受本节「重试、整改循环与调用预算上限」约束） |
| 11 | `next.allowed = true` 且 `next.stage` 是六阶段名但不在 flow 内，且属于上述必做后续 | `blocked`（必做阶段超出 flow，记录缺失阶段与实际验收结论，交用户调整 flow 或决定处置） |
| 12 | `next.allowed = true` 且 `next.stage` 是六阶段名但不在 flow 内，且不属于上述必做后续 | `completed`，以正常 flow 边界为终点；Run 与报告必须标注被截断及未执行阶段，保留已知验收结论、无结论才写 `unknown`，列入需人工介入 |

**重试、整改循环与调用预算上限**：可重试不等于无限重试，整改也不等于无限整改。同一 Task 在同一 Run 内同时受三个上限约束，任一耗尽即不再调用并停止该项。**三个上限都只在「确定仍需继续调用」之后检查**：先按终态映射表得出「需要再调用一次某阶段」的结论，再检查对应上限；不产生继续调用结论的收尾（completed／blocked／failed／flow 边界）不受上限影响，也不把已成立的收尾改判为耗尽：

1. **逐阶段失败重试预算**：按阶段分别保存，因**可重试失败**（`stage_result.status = failed`，或 `next.reason = stage_failed` 且 `next.allowed = true`）最多追加 2 次调用。首个失败后的两次重试仍失败，即该失败链的第 3 次调用仍失败时，不再调用，该 Task 记 `failed`（重试上限耗尽）。预算不因穿插其他阶段或某次成功而返还；同一阶段本 Run 已耗尽 2 次失败重试预算，后来再失败也不得追加重试。
2. **整改轮上限**：跨阶段整改循环单独计数——本次调用为 `fix`，且其调用原因是上一步 `review` 判定的必做问题未关闭（`next.reason = blocking_findings`）时，整改轮加一。同一 Task 在同一 Run 内不超过 **3** 轮；该原因的第 4 次 `fix` 不再调用，Task 记 `failed`（整改轮上限耗尽）。只按该原因累计：`acceptance_failed`、`stage_failed` 与正常新增修复不计入整改轮，也不因此获得额外额度。`review → fix → review` 每次交替各记一次调用与一轮整改，逐轮保留候选、findings 与原因。上限只拦该原因的第 4 次 `fix`：**第 3 轮 fix 交付后仍按 `next` 正常调用必要复审**，复审本身不消耗整改轮，随后按终态映射表收尾或再判。
3. **任务调用预算（兜底）**：同一 Task 在同一 Run 内**已发起**的 Cohestra 阶段调用总数（按调用计，不按成功计；不调用阶段的恢复核对收尾与修订收尾不计）不超过 **16**。达到 16 次后不再调用任何阶段，Task 记 `failed`（调用预算耗尽）。该预算覆盖第 2 条管不到的重复路径：`acceptance_failed` 引发的往复、`fix → review` 的必要复审往复，以及 validate 的本阶段补证重复。

消费时机：第 1 项在重试调用前消费（普通调用不消费失败重试预算），第 2 项在该原因的 `fix` 调用前消费，第 3 项在**每次**调用前消费。耗尽时逐次记录轮次、原因、错误与恢复条件，列入需人工介入；该 Task 配置 `stop_queue_on_failure: true` 时按第 2 节停止队列，后续任务不再排队等待。

**无进展判据（已收窄）**：同一阶段被连续调用两次后，比较 `stage_result.stage/status`、`candidate`、`findings`、`acceptance` 与 `next`；全部未变时按出口形状区分：

- 本次 `stage_result.status = completed`、`next.allowed = true`、`next.stage` 等于 `stage_result.stage`、`next.reason = stage_completed`，且本阶段为 `validate`——即 Cohestra 第 7.3 节「仅缺本阶段能够补足且已有执行条件的验收证据」的补证出口——**不判无进展**。补证可以只增加证据而不改变候选、findings、`acceptance: pending` 与 `next`，第二轮补证不是停滞。Cadra 不解析 handoff 正文核对证据是否真的增加；该出口的重复调用改由第 3 项调用预算兜底，因此不会无界。
- 其余全部未变 → 判为**无进展**，不等上限即刻停止并记 `failed`（无进展）。

本阶段自循环的豁免只此一例：将来若需按证据进度判进展，须由 Cohestra 契约新增可核对的机器字段，Cadra 不凭正文推断、不自行放宽判据。仅 `stage_result.round` 增加不构成进展；可选字段缺失与 null 等价（缺失与显式 `null` 视为同一取值，与写有内容的映射不等价）。

本判据是**加速停止**，与第 1 项重试预算可能同时适用，此时取先到者：同一阶段连续两次结果的比较字段完全相同，即按无进展停止，不再消费剩余重试额度；只有比较字段确有变化的重试才继续占用失败重试预算。因此「最多追加 2 次」是重试的**许可上限**，不是必须用满的额度。先按终态表第 1–9 行处理协议失败、受阻和完成；只有仍需继续调用时才应用本检查，不把已经完成的任务改判失败。

checkpoint 按阶段保存已追加的失败重试次数、已消费的整改轮数与调用总数、上一份核实结果、无进展判定，以及已计入的调用标识（run-id + slug + 调用序号，并关联阶段/轮次）。每次新结果只计入一次，调用前先落盘预算消费；`resume` 回读同一交付或补闭合同一调用时不重复计数、不重新消费预算，计数缺失或矛盾时停止并说明缺口。显式恢复与修订重启各自的首次调用另按第 6.2、6.3 节限制为一次，该次调用同样计入新 Run 的调用预算与整改轮；新 Run 使用自身预算，不重置同一未完成 Run 的预算。预算耗尽而落 `failed` 的任务要重新获得额度，只能由用户在 `run` 的显式恢复列表中重新选择并通过第 6.2 节核对，unattended 期间不自动重置。

### 6.1 契约前置检查与首次启动

建 Run 或入队之前先完成两项前置检查，任一项不通过即停止本次 run，不建 Run、不入队、不逐任务判 failed：

1. **目标与初始化前提**：固定目标项目绝对路径；从子目录定位 Git 工作区根目录，worktree 用自身根目录；目标必须是 Cohestra 可初始化的 Git 工作区，且可安全写入、不是技能源仓库。非 Git 目录、目标不明确或无法安全写入时停止——Cadra 不自行执行 `git init`、不代建 `.cohestra`，也不把该失败留到入队之后。缺 `.cohestra` 容器本身不是停止条件：由 Cohestra 在首个阶段调用时按最小范围初始化，Run 与 Task 记录标注“本轮需先初始化”。
2. **技能与契约**：从本次实际加载的 Cohestra 技能版本与规则确认支持契约 `0.8`、unattended 及单阶段交付；不得用源仓库的新规则替代实际选定的旧安装副本。

再对候选 Task 分类：

- **首次启动**：cohestra_task 没有 README、没有六阶段正式 handoff，且 Task 和关联 Run 记录没有既往调用。三项必须同时成立；任务目录尚不存在可以成立。只允许调用 flow 首项一次，调用原因记“首次启动”，调用前 stage_result 记无。首次交付后必须产生完整合法契约，并通过本次结果核对，之后只读新状态推进。
- **已有任务**：读取 README Front Matter 并检查必填字段、task/slug、契约版本与取值一致性，并做**收养核对**——读取 README 正文「任务目标」与本 Task requirement 对照，明显不对应时不接续、不入队，报告既有任务主题并请用户选择（确认接续 / 更换 slug / 先人工处理该目录）。该核对是建 Run 前的一次性收养防护，不是逐次调用的控制流解析，不违反本节「不解析正文决定流程」。可接续时按终态表确定动作（定义修订任务除外，见下条）；候选没有可执行动作时说明实际终态或 flow 缺口，不空建 Run。
- **定义修订任务**：Task 文件带未消费修订记录 `rev-<N>`（第 2.2 节）时按第 6.3 节确定首个动作，不按「已有任务」接续旧 `next`（旧 next 属于旧定义），也不按「首次启动」提交（存在既往调用与交付）。
- **契约未就绪**：已有正式交付/调用却缺 README、旧 README 无契约、版本不支持、状态损坏或无法读取。报告具体路径与缺口并停止本次 run，不建 Run、不入队、不把任务逐个判 failed；不存在“用户选择继续后忽略缺口”的分支。修复索引由 Cohestra 或人工完成，Cadra 不补写契约。

前置检查不改变 Task 状态；调用以后出现契约缺失、非法、错阶段、旧轮次、同步失败或执行模式不符，才按终态表记该 Task failed（修订重启的准入核对除外，见第 6.3 节）。

### 6.2 在新 Run 中显式恢复

`run` 的恢复列表必须包含在显式范围内，不能与空范围或“全部 ready”组合；只接受 blocked/failed，不接受 completed。定义已修订而处于 draft/ready 的任务不进入恢复列表，按第 6.3 节的修订重启处理；同一任务不同时走恢复与修订重启两条路径。恢复前原 Run 必须已结束、无其他未完成 Run；读取该 Task 所属原 Run 的逐任务 checkpoint 和结果快照，不按最新文件或聊天猜测来源。

1. 逐条复核第 2.1 节 Gate、受阻/失败原因解除证据、本次补充及已有授权；缺项保持原 Task 状态，停止该恢复项。旧协议缺必要 checkpoint 或记录矛盾时同样停止，不补造历史。只有用户在恢复列表中明确指定才构成此次重试选择，不产生新的产品或工具权限。
2. 先核对原调用前状态、拟调用阶段、README 与对应 handoff。未闭合或同步失败的调用必须先确认是否已完整交付；已交付的补记核对结论在**新 Run**，不重跑，不改原 Run。仍无法确认则停止恢复。若明确尚未调用且无新 handoff，可沿用原已核对的待调用动作；有半份交付则不能按“尚未调用”处理。
3. 状态合法且 next 允许、阶段在 flow 内时正常续接；旧契约仍为 blocked/failed，且 stage_result.status 为 blocked/failed 时，只有原因解除、对应阶段与原 checkpoint 一致并位于 flow 内，才允许**恢复重试一次**。调用前记录原状态、本次授权来源和已选阶段；向 Cohestra 传递解除依据，由其重新交付状态，Cadra 不清除 blocked 或伪造 next。
4. 核对证明阶段已完整交付且终态表判 completed 时，可在新 Run 中作“恢复核对收尾”，不调用阶段，保留验收与候选来源；其他无合法动作的状态（如必做阶段仍在 flow 外、completed 却缺验收）停止恢复，说明需先补足或调整的事项，不猜测重跑阶段。
5. 恢复准入通过后才在新 Run 入队，追加队列行与恢复来源。首个调用落盘前标记恢复授权已消费；此后只消费本次合法输出，不能反复用原恢复授权绕过 next.allowed=false。中断时按调用前记录核对，不能再次当作首次恢复调用。

原 Run 结束结果、checkpoint 与历史报告不因恢复改变；Task 文件的所属 Run 更新为新 Run 并追加历史引用。普通 ready 任务即使曾被编辑，也不能忽略其既往调用：Gate 放行不清除执行历史、不授予绕过旧 blocked/failed 的权利。定义已修订的终态任务按第 2.2 节回退、按第 6.3 节重启；未修订定义的任务只能先通过 Cohestra 明确阶段调用修复状态，或保持 blocked/failed 并使用本节的显式恢复路径；已完成的任务不重跑，确需重做时先按第 2.2 节修订定义。

### 6.3 定义修订后的重新执行（修订重启）

终态 Task 经第 2.2 节修订并重新 Gate 后，首个动作按下表确定。它不是首次启动（存在既往调用与交付），也不消费旧 `next`（旧 next 属于旧定义），更不绕过旧受阻状态的解除核对。

| 本次修订改变的字段 | 原终态 | 首个动作 |
|---|---|---|
| requirement 或 flow | completed | 调用**新 flow 首项**一次，调用原因记「修订重启 rev-N」 |
| requirement 或 flow | blocked/failed | 先核对受阻/失败原因解除与原 checkpoint（第 6.2 节第 1、2 条），通过后调用新 flow 首项一次 |
| 仅 dependencies 或 execution policy | blocked/failed | 上游依据未变：按第 6.2 节核对后重试原 checkpoint 中尚未完成或结果为 blocked/failed 的待调用阶段一次；已完整交付且 completed 的阶段不重跑，使用核实后的合法 next 或核对收尾；无合法动作时停止该项 |
| 仅 dependencies 或 execution policy | completed | 不调用阶段：按第 6 节终态映射核对后作修订收尾，旧验收结论继续有效，新策略只对后续执行生效 |

1. 入队前核对修订记录完整（`rev-<N>`、累计变更字段、当前新定义快照、旧定义快照引用、原 Run 与原终态），且本次实际读取的定义与记录一致；缺记录或矛盾时停止该项，Task 保持 `ready` 不入队。仅 dependencies/policy 变更的收尾允许引用未变 requirement/flow 对应的旧候选与验收，须明确标为沿用来源，不冒称本次执行或新验收。收尾没有本次阶段调用，旧交付的 execution_mode 按原调用记录核对，不用新 Run 的 unattended 声明反判原本合法的 attended 交付。
2. 原终态为 blocked/failed 时，原因必须已解除或有本次新增证据；未解除、无法核实或原 checkpoint 缺失、矛盾时停止该项，不把修订当作绕过旧受阻状态的通道。
3. 调用时向 Cohestra 传新 requirement（本次上游依据）、修订记录与原因解除证据；阶段轮次由 Cohestra 继续递增，不复用旧轮次，交付物引用旧结论时只作对比。Cadra 不清除 blocked、不伪造 next。
4. 调用后按第 6 节「本次结果核对」与终态映射表处理。重启授权在首个调用落盘前标记「已消费」，一次修订只提供一个重启起点；中断后按调用前记录核对，不再当作新的重启调用，也不回退为「首次启动」。不调用阶段的修订收尾在结果快照落盘并回读后也标记该修订「已消费」，记录新 Run 与收尾来源；中断后只补齐同一收尾记录，不另建 Run 重复收尾。尚未调用且 queued 收尾回 ready 的修订仍为未消费。
5. 新 flow 首项即重启起点：用户通过修订 flow 选择起点（例如改用从 code 起步的 preset），不需要也不允许用手工阶段调用绕过准入。

**接口现状声明**：Cohestra v0.8 起提供 Orchestrator 契约与 attended / unattended；Cadra 只消费接口，不修改另一技能的协议、阶段定义或 handoff 语义。实际加载版本不支持时停止自动执行，人工阶段调用仍归 Cohestra。

## 7. Unattended 执行规则

`run` 启动自动执行时向下游声明：

```text
execution_mode: unattended
```

无人值守期间：

- 不等待交互式问题；
- 不替用户做产品决策；
- 不扩大任务范围；
- 不获得新的隐含授权。

向 Cohestra 同时声明执行模式 `unattended`，并要求其在该模式下不等待交互提问、把需人类决定的事项表达为受阻（`blocked.value = true` 或 `next.allowed = false` 附原因），而不是留空等待——这是第 6 节接口要求的一部分，由 Cohestra 实现。

**模式核对失败**：本次声明 `unattended` 而契约记为 `attended`（或该字段缺失、非法）时，本次交付不构成无人值守结果。按第 6 节停止该 Task：不消费本次 `next`、不继续调用任何阶段，记 `failed`（执行模式核对失败）并列入需人工介入；该情形不按下面的 blocked 清单处理，也不因 `next.allowed = true` 而继续。

**verify 处置**：无人值守下 Cadra 不调用 `$cohestra verify`。Cohestra 协议中的 verify 提议在该模式下按跳过处理：在 Task 运行记录与报告中记“verify 跳过 + 理由（unattended）”，并列入需人工介入清单；该记录不降低也不替代 review、复审与验收要求。

遇到上述任一情况（需要人类决定、缺权限、缺输入、依赖未满足、Cohestra 明确禁止继续）时，本 Task 记 `blocked`，记录原因后按默认规则继续下一个 Task。`resume` 的续跑段沿用原 Run 的 `execution_mode` 与各 Task 的 execution policy，不切换模式。

## 8. 落盘与共享写入

1. 每份文件只有一个写入者。Task 文件由负责该 Task 的执行者写；Run 文件、`queue/order.md` 与 `<run-id>-report-<轮次>.md` 由 Run 的执行者串行维护。所有权不明或冲突时保留各自记录并报告“待同步”，不覆盖未知更新。
2. 状态变化、checkpoint 更新必须即时写盘并回读；中断后这些文件是唯一恢复依据，不凭文件修改时间或文件编号推断进度。
3. 不把 Cohestra handoff 内容复制进 `.cadra`：候选、findings、验收证据以引用加短摘要记录，标注来源文件。
4. 不反复改写 `.cadra/README.md`；普通入口只写本入口的交付物。写入失败如实报告“未完成”及错误与待写内容，不宣称事务回滚。
5. 交付物写入顺序：先 Task/Run/报告文件，再队列清单，逐份回读。更新前重读，避免覆盖并发写入。入队与出队的操作编号、三步写入与幂等补齐范围见第 4 节第 7–9 条。
6. 回复交付物绝对路径、状态结论、必要待办、需人工介入事项，以及 `$cadra <下一入口>` 加准确输入（可直接执行）；推荐下一步不等于执行授权。

7. 每个 Task 独立保存 checkpoint 与追加调用记录，不能用一个全局“最后完成阶段”覆盖前一任务。入队时保存本次定义快照（身份、requirement、flow、依赖、策略与 Gate 依据）与入队操作编号及写入进度；修订重启项同时保存 `rev-<N>`、旧定义快照引用与原终态，两代定义分别保留不合并。结束时保存该 Run 的 Task 状态、候选、findings、acceptance、下一步及来源阶段/轮次，并记录逐阶段重试次数、已消费的整改轮数与调用总数、出队操作编号与回写状态。后续 report 以该 Run 快照为准，当前 Task 或 Cohestra 状态只能标为另一次执行的补充信息。旧 Run 无快照时只引用其可核实的历史记录，缺失项写 unknown，不拿当前状态填充或批量迁移。

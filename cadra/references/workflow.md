# 公共流程 · cadra v0.8

本文件定义存储、状态来源与共同写入规则；详细判定按需读取。

## 存储与术语

```text
.yuzio/cadra/
├── README.md
├── tasks/<slug>.md
└── runs/
    ├── <run-id>.md
    └── <run-id>-report-<轮次>.md
```

- **Task**：任务定义、定义修订与 Ready Gate；`preparation` 仅为 draft / ready。
- **Run**：一次串行执行，`tasks` 数组的次序就是执行顺序；已有条目不重排，仅 append 可增加后缀。每项保存定义快照、执行状态、checkpoint、调用记录与结果。没有独立队列文件。
- **展示状态**：由 Task 准备状态与关联 Run 推导出的 draft / ready / queued / running / completed / blocked / failed，解析规则见下文。
- **checkpoint**：Run 中待调用动作、授权消费、预算与未闭合调用的恢复依据。阶段交付 completed 不等于整个任务验收通过。
- **flow**：起始阶段与允许阶段范围；preset 或显式列表的含义见 [Flow](flow.md)。
- **结构化状态**：Cohestra 任务 README Front Matter 的契约；Cadra 只读其控制字段，不凭自然语言决定推进。

Task 的 slug 与 `cohestra_task: .yuzio/cohestra/handoffs/<slug>/` 稳定绑定，不通过编辑重命名或改绑。单任务工程证据归 Cohestra；Run 只存契约值、引用和短摘要。

## 状态解析

1. 先按 [版本边界](compatibility.md) 区分 0.8 与只读历史 0.6/0.7，再读取目标 Task、Run 头部身份与任务标识，再读取涉及该 slug 的条目；list 全量查询可汇总全部条目。报告文件不是 Run，不参与来源链。不要通读无关调用正文。
2. 每个 Run 内 slug 唯一。该 slug 的首次 Run 条目 `previous_run: null`；后续条目引用该 slug 上一次 Run，不限于同一修订。所有条目必须形成唯一无环链，引用必须存在且包含该 slug；缺失、分叉、重复、版本不明或相互矛盾时停止相关推进，list/report 标明未知与缺口。不能用文件时间或 run-id 大小替代来源关系。
3. 未完成 Run 归属优先核对：同一项目有多个未完成 Run，或未完成 Run 中该 slug 的修订/定义与 Task 不符，停止并报告。任何归属未完成 Run 的 Task 都不能编辑，包括其条目已经结束的情况。
4. 来源链尾条目若属于当前 `revision`：queued/running 或 completed/blocked/failed 直接作为展示状态；skipped 表示本轮未执行，展示 Task 的准备状态（正常为 ready）。若链尾属于旧修订或尚无 Run，展示 Task 的 preparation。Run 修订不得大于 Task 修订，也不得沿链倒退。
5. `ready` 复核失败可使 preparation 回 draft；对尚未执行的 skipped 条目，显示 draft，不继续沿用旧 Gate。终态不能被准备状态覆盖，必须由 add 建立新定义修订。
6. 依赖只认可上述**当前定义的展示状态**为 completed。旧修订的成功不放行新定义；开始或续跑每项前重核依赖。

执行依据是沿来源链最近一条已记录调用意图，或已核实契约并保存无需调用收尾结果的条目。authorization_consumed 只表示一次性恢复/修订授权消费；普通调用或普通核对收尾可为 false，不影响其执行依据资格。既无调用意图也无有效核对收尾的条目不构成执行依据，包括首调用前 blocked/failed 和 skipped；它们的受阻原因、未消费动作与修订变更仍须核对。字段缺失、无执行证据却标记已消费等矛盾时停止，不能推定未调用；prepared 或派发不明的调用也不能跳过。

再次选入新 Run 时重新通过相应准入，不自动继承旧授权。没有执行依据且无 Cohestra 正式交付时可按首次启动核对；有交付则先核实来源与契约，不能只凭 Run 是否存在判断。

## 规则索引

| 规则 | 读取条件 |
|---|---|
| [Task 与 Ready Gate](task-rules.md) | add、ready、run、append；resume 需复核准入时 |
| [Run 与持久化](run-rules.md) | run、append、resume；归属、来源链或收尾核对 |
| [Flow](flow.md) | add、ready、run、append；解释 flow 时 |
| [任务执行者](agents.md) | run/resume 派发与恢复；预检角色能力 |
| [Cohestra 契约与预算](contract.md) | 调用或核对阶段；收养已有交付 |
| [显式恢复](recovery.md) | run 恢复列表非空，或 skipped 来源为恢复 |
| [定义修订](revision-rules.md) | 编辑已入 Run 的定义，或修订重启 |

## 共同写入

- 存储和正式总结遵循 [存储约定](storage.md)。新建文件记录实际发行版、协议和带时区时间；run-id 使用 `run-YYYYMMDD-NN`，报告轮次两位起、不截断，编号只保证唯一，不推断进度。
- 0.8 Run 的创建、更新、追加与报告链接登记必须使用 [执行归属写入器](executor.md)，不直接覆盖；下列临时文件/回读规则由该工具落实。Task 与报告正文仍按本节原子更新。
- Run 执行字段只有当前主 agent 可写；append/report 通过各自受限操作修改允许字段，不获得执行权。其他每份文件单写入者。更新前重读并核对未被其他写入改变；未知更新或所有权冲突时保留现场并报告，不覆盖。
- Task、Run 更新：在同目录写临时文件，检查文档完整及必填字段、定义/状态约束后替换目标文件，回读成功后才继续。创建 Run 时不得覆盖已有同名文件。临时文件不参与状态解析。
- 写入失败如实报告待完成内容，不声称事务回滚，不调用下一阶段。替换后回读失败时先恢复并核实原文件；临时文件不证明某次调用已经发生。
- run/resume 只修改当前 Run，不回写 Task 的执行状态。结果快照固定本轮结论；后续执行与 Task 编辑不能改写旧结果。报告登记链接属于元数据更新，不改变旧执行事实。
- 结果缺失只能记 unknown 并说明证据缺口，不能用当前 Cohestra 状态补造旧 Run 结论。

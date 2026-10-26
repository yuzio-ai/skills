# run

读 [公共流程](workflow.md)、[Task/Gate](task-rules.md)、[Run 规则](run-rules.md)、[Flow](flow.md)、[契约](contract.md)。存在恢复选择或 skipped 恢复来源时读 [恢复](recovery.md)；定义修订时读 [修订](revision-rules.md)。

```text
$cadra run
范围：<slug 列表，或全部 ready；缺省全部 ready>
恢复：<本次显式恢复的 blocked/failed slug 列表，可空>
补充：<本次输入、解除证据或限定条件，可空>
```

先读 [预检](preflight.md)、[执行归属](executor.md)、[任务执行者](agents.md)；含旧记录时读 [版本边界](compatibility.md)。旧未完成 Run 存在则只报告，不接管或迁移。

## 建立 Run

1. 固定目标，确认 Git 工作区、可安全写入、非技能源仓库，实际 Cohestra 支持契约及 unattended，项目协议可用且无未完成 Run。Cadra 不 git init、不代建 Cohestra 容器；缺容器由首次 Cohestra 阶段最小初始化。
2. 校验范围与恢复参数，按状态解析选择候选。只恢复 ready 的 skipped 恢复来源时，要求显式 slug 选择；普通 blocked/failed 必须出现在恢复列表。
3. 对候选复核 Gate、定义快照及首个动作，分别按首次/接续、恢复或修订准入。普通 Gate 或个别恢复条件未满足时保留原状并说明；全局前提或任一候选契约损坏时停止本次 run。所有前置检查在写 Run 前完成；无合格动作不空建 Run。
4. 对合格项完成项目及任务只读预检；项目级失败不建 Run，任务级失败明确排除。重读定义、授权和关键输入，变化则重检。保存 preflight 证据，不要求未来阶段产物已存在。
5. 按 priority 与 slug 排序；新 Run 内为每项引用该 slug 的来源链尾，并保存当前 revision、完整定义、首个动作与依据。按 Run 规则构造 [骨架](../assets/run.md)，初始化 executor/ownership_history/append_history 和每项 agents，经 guard create 发布并回读后开始执行。

## 串行执行

每项开始前核对当前执行实例和代次，重核相关预检前提，重读定义与依赖，和保存的快照核对。定义被外部修改或来源矛盾时停止并报告；依赖不再 completed 时该项 blocked，不调用阶段。

需要调用时先按任务执行者规则创建或复用本任务的 worker/reviewer，保存实际角色绑定，再按 Run 规则持久化调用意图、agent_ref 和预算，派发给该角色一次 `$cohestra <阶段>`，附目标、cohestra_task、Task 绝对路径、当前 requirement/修订依据及 `execution_mode: unattended`，附 Run、call id、执行实例和代次、预检引用、独立评审安排及项目适用评审要求。主 agent 不亲自执行工程阶段；子 agent 不写 Run、不自动继续下一阶段。一次一个阶段；中链起步不补造 need。

调用后按契约核对结果，闭合调用记录，再使用唯一终态映射确定收尾或下一阶段。必要调用受三项预算限制；核对收尾不发起调用。结果与状态即时写入当前 Run，不更新 Task。

blocked/failed、策略停止与用户停止按 Run 规则处理。阶段边界重读最新队列，保存结果和收尾前按执行归属规则处理合法追加，不能用旧快照覆盖。全部项结束后收尾 Run；写入中断交 resume，不建立替代 Run。

## 交付

给出 Run 路径与结果。未完成先按执行者观察区分活跃、确认停止和未知；仅确认停止并具备恢复核对条件时推荐 `$cadra resume`；已结束推荐 `$cadra report`。失败恢复须显式范围与恢复选择；定义变化先 add/ready，不重开旧 Run。

# 任务执行者与独立评审

run/resume 在首次派发或恢复前读取本页。宿主必须能创建干净上下文的子 agent、取得实际身份、分阶段继续会话，并核实其执行和工具状态。缺少能力时预检受阻，不退回主 agent 实施或自审；槽位暂不可用时等待可用或报告受阻，不提前记调用、计费。

## 分工与生命周期

- Cadra 主 agent 只做准入、调度、Run 写入、契约核对与恢复。每次只允许一个 Task 执行，一个阶段派发；不跨任务并行。
- 每个 Task 的 worker 执行 code/fix/validate，reviewer 执行 review。角色按需创建；review-only 不创建闲置 worker，仅核对历史结果的收尾不创建 agent。
- 同一任务优先复用原 worker 和 reviewer，不同 Task 不复用身份。reviewer 不得兼任本任务任何实现或整改作者；原作者不明时不能凭“新建了 agent”宣称已核实独立性，应核查候选来源。
- agent 使用干净上下文，不继承主聊天完整历史。只传 Task 定义快照、有效决定和授权、项目规范、实际技能路径、必要上游交付与固定候选证据。共享接口变化通过交付和当前候选传递，不依赖主 agent 摘要代替源码。
- 子 agent 不自行调用下一个阶段，不再委派其他 agent，不写 Cadra Run。Cohestra 阶段交付和任务索引由当次执行者发布；上一阶段完成、工具停止、发布核对成功后才向另一角色移交。
- reviewer 独立核查源码、调用路径和证据，期间不得派发修改候选的阶段。fix 回原 worker，复审优先原 reviewer；validate 核对独立评审针对当前候选且必做 findings 已闭合。
- 每个任务结束后确认子 agent 和工具均停止，再使用宿主实际支持的释放方式释放不再需要的会话；没有释放工具不伪造关闭。后续任务新建身份，不把旧会话改名复用。

## 绑定、派发与交付

Run 每个 tasks 条目新增 `agents: []`。每条绑定为：

```yaml
id: <本 Task 内唯一绑定标识>
role: worker                 # worker / reviewer
agent_id: <宿主返回的真实 agent 身份>
host_id: null                # 实际可取得值，否则 null
created_at: <带时区时间>
source: <创建调用与身份核实来源>
supersedes: null             # 同角色被替换的上一绑定 id
stop_observation: null       # 替换时记录被替换者停止证据
```

`stop_observation` 为 `{agent_id, host_id, state: stopped, tools_stopped: true, observed_at, source}`，指向被替换者，时间不早于其绑定创建、最后调用准备/派发及当前 executor progress。没有替换时两字段均为 null。绑定记录只追加、不回写；跨 Task 与角色不得复用相同宿主/agent 身份。当前角色取其连续替换链尾，保留所有历史绑定。

1. 先创建只确认身份、不得执行工程阶段的子 agent，核实真实身份与角色，使用 guard update 每次单独保存一个绑定并回读。创建失败、身份不明或创建响应丢失时不派发；先核查已创建但未登记的会话，不能猜身份或重复创建正在工作的 agent。
2. 选择本阶段角色，核对其绑定及独立性，按预算持久化单次调用意图；call 增加 `agent_ref`（绑定 id）、`dispatch_evidence: null`。绑定必须先于调用落盘。
3. 再回读归属及最新 Run，向该角色派发一次 `$cohestra <阶段>`，附完整准确材料和独立评审安排。真实派发后记录 `dispatch: dispatched` 与 `dispatch_evidence: {agent_id, source, at}`；source 引用实际工具调用，at 带时区。不用 prepared 或子 agent 返回的自述替代派发证据。
4. 等待阶段交付和工具停止。主 agent 核对同步、候选、阶段轮次、实际执行者与契约后闭合原 call；先单独闭合落盘，才准备下一次调用。

子 agent 在准备阶段不消耗阶段预算；真正调用意图仍按原预算预占。角色替换不重置预算、不增加可绕过的重试额度。

## 恢复与角色替换

恢复必须核查主执行者、全部历史绑定的子 agent 及其工具。父 agent 已停止不意味着子 agent 停止；任一仍 active 或 unknown 时不得 takeover、替换、重放。takeover 的 observation 增加 `children` 数组，为每个绑定提供上述实际身份停止观察，保留证据；新 executor.claimed_at 不早于父执行者及全部子 agent 的停止观察时间。

同一 call 已完整交付时只补记原调用；有明确未派发且无交付证据时，只能向该 call 原绑定 agent 继续，沿用 call id 和预算。原 agent 不可恢复时将该项记 failed，保留未闭合调用及证据，后续由显式新 Run 恢复；不能改写 agent_ref 或把同一调用交给替代者。

只有当前任务没有未闭合调用，并确认被替换者和工具停止时，才可追加同角色新绑定及 stop_observation。新角色加载原 findings、有效交付和候选差异，不继承其他任务聊天。角色绑定或停止证据矛盾时保持现场，不用新的 agent 绕过恢复门禁。

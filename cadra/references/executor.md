# 执行归属与活性

run/resume 写入前、append 受限写入前及 list 推荐后续动作时读取本页。子 agent 规则见 [任务执行者](agents.md)。Run 状态和执行者活性是不同维度；running、prepared、长时间无更新均不能证明需要恢复。

## 记录与观察

0.8 Run.executor 必填：instance_id（本次执行实例唯一标识，不是 PID）、generation（从 1 开始）、host_id/thread_id/turn_id（实际可取得身份，否则 null）、claimed_at、progress={at,event}。仅真实派发、交付、收尾事件更新 progress；不用定时心跳伪造进展。ownership_history 保存交接前 executor 和核实的 observation；不另设活性控制状态。

用宿主当前可用的正式工具查询记录指向的执行聊天及调用状态；不猜工具接口、不编辑内部数据库、不把别的聊天当同一执行者。观察输入为 {instance_id,generation,host_id,thread_id,turn_id,observed_at,source_kind,source,state,tools_stopped,children}。身份字段必须逐项匹配原 executor，不得用本次恢复者的身份替代。

source_kind=host 时，宿主三个身份字段必须完整且经正式工具核实；拿不到准确 turn 时为 unknown。source_kind=human_handoff 仅用于用户明确确认该实例及其工具已停止的交接证据，source 引用原消息；已知身份仍须匹配，未知字段保持 null。一般“继续/resume”授权不等于停止证据，不得自行改标 human_handoff。source 不是权限或真实性证明，调用者仍须核实。

| 观察 | 展示和动作 |
|---|---|
| 对应执行者或子 agent 明确 active | 正在执行；不推荐 resume、不接管或中断；仅允许 append/report 的受限写入 |
| 原执行、全部绑定子 agent 及其工具调用均明确结束 | 待核对恢复；仍需检查未闭合调用和交付 |
| unavailable/notLoaded/idle 但工具状态不明、身份缺失、仅时间过久 | 活性未知；不自动接管、重跑或改判失败 |

list 不落盘、不加锁、不发送消息。明确 resume 授权后也必须先核对归属和派发事实；观察未知时报告缺口并保持 Run。当前实例连续推进可沿自身归属执行；新的 turn 不冒用上一次实例。检查后发现新的活跃证据则停止接管。`children` 必须覆盖每个历史绑定的实际宿主/agent 身份，字段和核验见任务执行者规则；不能以父执行结束代替子 agent 观察。

## 写入与交接

使用包内 [run_guard.py](../scripts/run_guard.py)，只依赖 Python 标准库及 POSIX 文件锁。它不调用 Agent、不执行项目命令、不证明观察证据真实性；调用者负责上述核实和完整契约/Gate/来源链核验。工具不具备安全锁支持时停止写入，不退化成直接覆盖。

新 Run 使用 JSON 映射作为 YAML Front Matter，便于无外部 YAML 依赖的完整读写；正文仍为 Markdown。[Run 骨架](../assets/run.md) 展示字段，落盘时将头部转换为合法 JSON，不写占位符。Task 仍可使用 YAML。

脚本接口：`python3 -B <安装目录>/scripts/run_guard.py <inspect|create|update|append|takeover|report> --run <绝对路径>`。
- inspect 可加 `--observation <JSON 文件>`；只读返回摘要、协议、executor 与 active/stopped/unknown，不写入观察。
- 写操作提供 `--proposal <完整 Markdown 文件>`；除首次 create 外，提供上次 inspect 的 `--expected-sha256`。create/update/takeover 同时提供 `--instance` 和 `--generation`。临时提案放 Run 的 scratch 目录，不参与状态解析。
- create 在项目 runs 目录的短时 `.writer.lock` 下检查既有 Run、目标不存在和完整初态；先准备 queued 数组，再创建。锁不保存执行状态，进程退出由内核释放，锁文件不能删除重建。
- update 只接受当前身份/代次与预期摘要；冻结定义、闭合调用、终态条目及既有预检不得改写；普通 update 不得增删、重排队列或改 append_history。角色绑定仅按任务执行者规则追加，原 pending 未闭合时不得替换。一次只追加一个 prepared、未闭合且无结果的调用；原 pending 必须先单独核实闭合落盘，再追加下一意图。调用前保存意图后回读归属，再派发；写入保护不是外部调用的 exactly-once 保证。
- append 不要求执行 owner 身份，只接受 running Run；仅追加 tasks 后缀、对应新增任务的 preflight 和一条 append_history，保留其他字段及正文。具体准入见 [append](append.md)。
- takeover 仅在原执行、全部绑定子 agent 与工具明确停止、获得本次 resume 授权，并完成只读协议/来源/唯一 Run/快照核验后使用。新 instance、generation+1，claimed_at 不早于父执行者和全部子 agent 的停止观察；仅替换 executor 并追加 `{previous: 原 executor, observation: 本次核实观察}`，保留正文、任务、预算与调用。脚本核对 observation 后发布，再按 resume 核实同一调用，不能先清 pending_call。
- report 仅追加 reports 链接，保留其他字段与正文；不接管执行者、不改执行事实。仍需摘要比较和短时锁。

短时锁保护检查和发布，预期摘要避免两个恢复者都获得同一代次。它不能排除绕过技能的任意文件编辑；每次派发前重读身份/代次，未知外部更新保持现场。不得抢占仍在执行的阶段；已发生但未登记的副作用仍按恢复证据核对，不盲重试。

## 追加与执行写入竞争

每次派发、结果落盘和 Run 收尾前都重读最新头部。普通 update 的摘要失效时，先比较变化：仅当是合法任务后缀追加及对应审计/预检，或报告链接追加时，才基于最新 Run 重建本次尚未发布的更新，保留所有新增内容。不得直接重交旧提案或任意合并其他修改。最多重试三次；持续冲突或不明变化时停止写入并报告现场。已派发阶段不能因写入冲突重新派发；先按原 call 核对并保存交付。

追加与收尾使用同一锁：追加先成功则原收尾摘要失效，执行器处理新增条目；收尾先成功则 append 拒绝已结束 Run。追加不改变 executor progress，不构成接管授权。

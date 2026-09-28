# Cadra 验证场景

这是维护者的验收清单，不是每次入口执行的必读文件。不创建自动安装器或将模拟结果冒充实际智能体执行。

## 文件与路由

- SKILL.md 前置元数据有效，发行版与任务/Run 协议版本明确，六个入口（add、ready、list、run、resume、report）均能定位对应说明文件；只加载公共流程、所选入口说明与对应模板，不预读其他入口。
- Markdown 相对链接存在，模板占位符可识别，技能包无脚本和测试运行时依赖；无失效路由或模板管理清单。
- 公共流程含 Task 状态机、Run 状态机、Ready Gate 引用、串行与队列规则、Flow Preset、Cohestra 调用契约、unattended 规则与落盘规则，且入口说明不复述公共规则。
- 任务骨架、Run 骨架与 `.cadra` 容器模板可以定位全部契约字段：title、slug、requirement、priority、dependencies、flow、execution policy、status、cohestra_task、checkpoint。
- 根 README 为双语版（`README.md` 英文、`README.zh-CN.md` 中文），顶部语言切换行双向可达；两版的标题层级、表格行列、代码块内容与相对链接目标一致，改一版必须同步另一版。
- `cohestra/` 目录零改动：本技能不修改 Cohestra 协议、阶段定义、README schema 或 handoff 语义；缺失接口只在 Cadra 文档中声明。

## 项目容器与状态机桌面推演

| 场景 | 预期结果 |
|---|---|
| 目标项目缺 `.cadra` 时调用任意入口 | 先报告目标绝对路径并执行一次最小初始化（README、tasks/queue/runs/ 与忽略规则），再继续本入口；不生成任务、不建 Run、不提交 |
| 目标不明确或指向技能源仓库 | 不初始化，先澄清或报告 |
| add 新任务 | `tasks/<slug>.md` 落盘，status 为 draft，七项定义字段齐全，默认 priority=medium、flow=full、stop_queue_on_failure=false，并记录 cohestra_task 引用 |
| add 同 slug | 视为编辑，仅改用户明确指示的字段并记录修改来源与时间；重大变更建议回 draft 重新 Ready Gate |
| 依赖悬空或成环 | 拒绝创建/修改并列出问题，不建立引用 |
| Ready Gate 八条全过 | draft → ready，记录逐条结论与放行时间；不入队、不建 Run |
| Ready Gate 任一条不过 | 保持 draft，逐条列缺口与补足建议，不降级放行、假设不当已决 |
| 依赖未满足时执行 ready | 第 6 条不通过，保持 draft 并指出依赖状态 |
| list | 只读展示七种状态、priority、dependencies、flow、当前执行状态与 Run 一览，不写任何文件 |
| run 建立 | 选 ready 且依赖满足的任务入队，生成 run-id，写 Run 文件与 queue/order.md；无可入队任务时报告并停止 |
| 已有未完成 Run 时再 run | 报告未完成 Run，请先 resume 或显式停止，不并行开新 Run |
| 排序 | 依赖优先于优先级；同优先级按 slug 字典序稳定排序，结果可复现 |
| 串行 | parallelism=1，同一时间至多一个 running Task，不做 DAG/并行/定时器/daemon |
| flow preset 执行 | preset 只是候选序列；仅当 next.allowed=true 且 next.stage 在序列内才执行下一阶段，不机械执行全部阶段 |
| next.stage 不在 flow 内或 allowed=false | 不执行、不发明阶段，按终态或契约规则处理并记录 |
| run 启动 | 向下游声明 execution_mode: unattended |
| unattended 遇需人类决定/缺权限/缺输入/依赖未满足 | 该 Task 记 blocked 并记录原因，继续下一个 Task |
| unattended 边界 | 不等待交互提问、不替用户做产品决策、不扩大范围、不获得新隐含授权 |
| Cohestra blocked.value=true | Task 记 blocked，记录 reason |
| 结构化状态缺失、不可读或不合法 | Task 记 failed（无法读取必要状态／协议输出不合法），不解析自然语言正文倒推 |
| 契约就绪探测失败 | run 启动前报告现状并请用户决定继续或中止，不静默逐个判 fail |
| 禁止解析正文 | 不依据 README 中“建议下一步进行 fix”之类的句子选阶段 |
| blocked/failed 默认 | 记录后继续下一个 Task |
| stop_queue_on_failure: true 且任务 blocked/failed | 队列停止，Run 记 stopped 并写原因；剩余入队任务报告记 skipped，Task 状态保持 queued |
| 队列走完 | Run 记 completed，queue/order.md 出队结果回写 |
| 中断（会话断开、checkpoint 未闭合） | Run 记 interrupted，状态即时落盘可恢复，不宣告成功 |
| resume 选取 Run | 取唯一未完成 Run；多个候选列出请用户指定，不凭时间或“最新”猜测 |
| resume 不重复已完成 Task | completed/blocked/failed 不重跑，按原记录计入 |
| resume 不重复已完成阶段 | 以 checkpoint 与 Cohestra 结构化状态核对后从下一阶段继续，不凭修改时间推断 |
| resume 重新核对 running/blocked/failed | 中断点回读结构化状态判定阶段实际进度；blocked 原因解除回 queued 排尾，未解除保持并跳过；failed 不自动重试，显式要求才回 queued 并记重试轮次 |
| resume 续跑 | 沿用原 Run 的 unattended 与各任务执行策略；不新建 Run；Run 已 completed 时指向 report |
| report 汇总 | completed/blocked/failed/skipped 四类计数与清单齐全 |
| report 逐任务 | 七项齐全：最终状态、最后完成阶段、当前候选引用、findings 摘要、validation 结果、是否需人工介入、下一步 |
| report 材料边界 | 只写引用加短摘要，不复制 handoff 正文进 .cadra；契约缺口如实标注 |
| report 轮次 | 每次新增 `<run-id>-report-<轮次>.md` 并引用旧版，不覆盖历史 |
| 状态所有权 | Task 状态只由 Cadra 写；`.cohestra` 内容零写入 |
| 写入失败或状态矛盾 | 如实报告未完成/缺口与待写内容，不宣称事务回滚、不猜测补齐 |

## 安装

安装走通用技能管理器（如 skills CLI），Cadra 不提供自研安装器。安装副本须包含 references、assets 与隐藏模板文件；安装本身不创建 `.cadra`。没有对应实测时标明未实测，不能用文件复制代替 CLI 安装证据。

交付检查结果时分开标注：文档静态检查、文件/CLI 实测、桌面推演、独立智能体实测。未执行项如实列出。

## 0.1.0 本地验证记录

- 变更：首个版本。新增 `cadra/`（SKILL.md、release.json、LICENSE、references/workflow.md 与 add/ready/list/run/resume/report 六份入口说明、assets/task.md、assets/run.md、assets/project/ 容器模板）与 `tests/cadra-scenarios.md`；根双语 README 增加 cadra 导航、调用示例与安装命令。发行版 0.1.0，任务/Run 协议 v0.1。
- 已执行（文档静态检查）：全包 Markdown 相对链接解析（137 条、0 断链）、SKILL.md 路由表与 references 六文件一一对应、release.json 与各文档版本字样一致（0.1.0 / v0.1）；本轮写入范围核对——`cohestra/` 零改动（该目录工作区中另有此前遗留的未提交改动，与本技能无关，未触碰）。
- 已执行（桌面推演）：上表场景按公共流程、入口说明与模板逐行推演，规则间无冲突；Task/Run 状态机转换、排序口径与 resume 核对规则在推演中可闭合。
- 未执行（如实列出）：未用 skills CLI 做安装实测；六入口均未在独立智能体会话中实跑；Cohestra 结构化状态接口尚未就绪，run 的无人值守闭环未实测；未做远程安装验证。
- 待补证据：一次真实项目中 add → ready → run → report 的完整记录；一次中断后 resume 的实际恢复记录（覆盖不重复已完成阶段与 blocked 解锁两个分支）；契约就绪后的 unattended 串行实测。
- 未做替代：未用桌面推演冒充智能体实测或 CLI 实测；未修改 `cohestra/` 或真实用户安装，未把模拟输出写成执行证据。

# 测试与场景清单

本目录保留当前自动化测试、行为场景与可复用测试输入，也保留被当前测试复用的旧模型及部分冻结验证报告。历史报告、快照和日志只证明记录时的结果，不代表当前环境已经复测；旧模型的复用范围见下表，不表示技能运行时支持旧协议。一次性审查与发布验证记录见 [output/](../output/)。

## 目录

```text
tests/
├── cadra/      # 模型、回归测试、包检查、场景、夹具和冻结验证报告
├── cohestra/   # 包检查、场景、输入生成器和产物核对器
├── relatra/    # 包检查、离线回归测试、场景和周期报告样例
├── vistra/     # 包检查和行为场景
└── shared/     # 通用包检查工具、版本检查、存储与路径测试和场景
```

## 自动化检查

在仓库根目录执行：

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

单独运行一个 skill 的测试时，指定对应目录并保留 `-t tests`，例如：

```sh
python3 -B -m unittest discover -s tests/cadra -t tests -p 'test_*.py'
```

统一入口已包含 Cadra 静态检查和四个技能包的元数据、链接与隔离副本资源检查。单技能命令也包含对应包检查。

各子目录的 `__init__.py` 用于递归发现和包内导入；新增测试放在对应目录并沿用 `test_*.py` 命名。

| 文件 | 检查范围 |
|---|---|
| [test_cadra.py](cadra/test_cadra.py)、[model.py](cadra/model.py) | Cadra v0.6 测试模型的流程、修订、预算和恢复约束；不是技能运行时 |
| [test_flow_current.py](cadra/test_flow_current.py)、[model_current.py](cadra/model_current.py) | 当前流程的测试模型：新预设、人工阶段受阻与必要复审；不替代真实 agent 验证 |
| [test_append_agents.py](cadra/test_append_agents.py) | 直接测试写入器的原子追加、进程竞争、角色绑定、派发证据、子 agent 停止与旧协议拒绝 |
| [test_review_current.py](cadra/test_review_current.py) | review 闭环、按需创建 worker、当前协议与 Gate 校验 |
| [test_cutover.py](cadra/test_cutover.py)、[一次性切换工具](../tools/cutover_cadra_010.py) | 历史 0.10 环境的本地归档、摘要、Gate 失效、安装切换、链接修复与回滚；工具要求匹配的 0.10 来源包，不用于当前 0.12 迁移；离线旧 YAML 读取需 macOS 系统 Ruby |
| [test_run_guard.py](cadra/test_run_guard.py) | 直接执行包内写入器；进程竞争、归属交接、预检约束、调用及历史保护；不执行真实工程阶段 |
| [test_guard_safety.py](cadra/test_guard_safety.py) | 停止与 skipped、计费依据及上限、合法恢复、复审旧轮次的真实文件回归；跨 Run 轮次另用当前模型核对 |
| [test_scheduler.py](cadra/test_scheduler.py) | 直接调用包内 reducer 与真实 CAS 发布：小组范围、FIFO、阶段内等待、验证窗口、失败取消、候选刷新及跨代恢复；工具观察为合成输入 |
| [test_closeout.py](cadra/test_closeout.py) | 0.12 收尾门槛、整改闭环、继承权限、候选与实际字节、追加、恢复、历史与隔离查询；工具观察和交付为合成输入 |
| [test_list_summary.py](cadra/test_list_summary.py) | 保留原 0.11 语义的列表摘要状态、来源链、折叠、详情与只读快照；含未闭合小组的 completed 条目显示 unknown |
| [test_list_legacy.py](cadra/test_list_legacy.py) | 0.10 原协议只读查询：原语义、混合版本、跨协议链拒绝、独立安装副本与文件/时间不变；执行写入器仍拒绝旧记录 |
| [test_list_optimization.py](cadra/test_list_optimization.py) | 列表成本与生命周期：前驱闭合、异常保留、身份去重、摘要/原文等价、预检索引与调度视图复用 |
| [test_process_view.py](cadra/test_process_view.py) | 包内只读过程视图：多轮整改、未闭合交付、同步缺口、验证先失败后通过、恢复来源、输入不变、独立包运行与旧协议拒绝；不模拟真实 agent 决策 |
| [test_review_full_fixture.py](cohestra/test_review_full_fixture.py)、[review_full_fixture.py](cohestra/review_full_fixture.py) | 扩展单独 review 实测输入与实际发布故障：原子替换拒绝、竞争写入保留和解除故障后的发布；不模拟 agent 决策 |
| [test_review_fixture.py](cohestra/test_review_fixture.py)、[review_fixture.py](cohestra/review_fixture.py) | 单独 review 实测输入：固定候选、真实缺陷、工具不可用及明确自审；unittest 只校验夹具与隔离，不模拟 agent 决策 |
| [test_validate_check.py](cohestra/test_validate_check.py) | 用隔离合成产物核对旧任务拒绝、损坏契约、正常发布与解析故障，以及汇总和 CLI 退出码；不执行真实 agent 阶段 |
| [test_closeout_concurrency_fixture.py](cohestra/test_closeout_concurrency_fixture.py)、[closeout_concurrency_fixture.py](cohestra/closeout_concurrency_fixture.py) | closeout 并发实测的隔离输入、受控 Cadra 记录与真实进程探针；回归验证两个进程等待后互斥执行，并拒绝重叠占用日志，不模拟 agent 决策 |
| [Cadra](cadra/test_package.py)、[Cohestra](cohestra/test_package.py)、[Relatra](relatra/test_package.py) | 各包结构、元数据与资源完整性；Cadra/Cohestra 另检查路由、模板与契约 |
| [test_relatra.py](relatra/test_relatra.py) | 合成历史的采集、统计、账本复用、更正和隔离包调用 |
| [test_reports.py](relatra/test_reports.py)、[周期报告样例](relatra/examples/README.md) | 重点正文与完整明细、日周月归纳、锚点、资源覆盖及可复现样例 |
| [test_vistra.py](vistra/test_vistra.py) | 包内引用、元数据、来源、许可证与可移植性 |
| [package_checks.py](shared/package_checks.py)、[test_package_checks.py](shared/test_package_checks.py) | 通用链接与资源检查、缺失及越界回归、仓库文档链接、双语 README 导航一致性 |
| [test_local_storage.py](shared/test_local_storage.py)、[test_project_data_paths.py](shared/test_project_data_paths.py) | 临时 Git 仓库中的存储语义、维护路径 |
| [test_release_versions.py](shared/test_release_versions.py)、[release_checks.py](shared/release_checks.py) | 对照完整 Git 历史检查同号变更、新增未跟踪文件与版本回退；无历史或浅克隆时明确跳过 |

包检查只依赖 Python 标准库。共享工具留在 `tests/shared/`，不会成为已安装技能的依赖。隔离检查完整复制单个技能包（含隐藏模板文件），核对资源可达性、包内边界及逐文件内容；不等于通过安装器安装、宿主发现入口或实际技能执行。链接检查验证内联 Markdown 链接的文件/目录目标，不验证章节锚点和外部网址。

[Cadra 修订夹具](cadra/fixtures/pre-call-blocked-revision.json)保留当前回归所需输入，不包含历史错误输出；期望结果由测试断言维护。

固定小组、列表汇总、旧协议查询与列表成本测试直接调用包内 reducer、写入器和只读脚本；工具观察是明确的合成输入，不代表真实工程阶段已执行。YAML 列表夹具使用系统 Ruby/Psych，JSON 夹具及包结构检查只用 Python 标准库。千级/万级队列、密集异常和真实历史详情的对照验证见 [独立验证脚本](../output/cadra-list-scaling-20261030/verify.py)；合成身份不是实际工程执行证据，耗时和 token 计数分别报告。

## 版本检查

[版本规则](../AGENTS.md#版本管理)由 [release_checks.py](shared/release_checks.py) 和 [回归测试](shared/test_release_versions.py) 支持，并通过各包测试纳入统一入口。检查工作区内容与当前版本首次提交的内容是否一致，覆盖未跟踪资源、已提交的同号修改及版本回退。完整 Git 历史是必要条件；无历史或浅克隆会显示跳过，发布前必须补齐历史并确认没有跳过。版本增量级别和协议语义兼容性仍需人工判断。

## 行为场景与辅助工具

- [Cohestra](cohestra/scenarios.md)：阶段、契约、索引发布与只读报告。
- [Cadra](cadra/scenarios.md)：任务编排、修订与恢复。
- [Relatra](relatra/scenarios.md)：目标、证据、统计、复用与更正。
- [Vistra](vistra/scenarios.md)：静态图片流程、预算、配置与交接。
- [本机资料与正式文档](shared/scenarios.md)：存储与跨技能交付边界。

Cohestra 的报告输入生成器、validate 故障驱动和产物核对器见对应场景清单；它们辅助隔离验证，不代替实际阶段执行。场景清单定义验收要求，不记录一次性通过数量。结构检查、模型测试、实际调用和视觉验收分别报告。

真实宿主与冻结验证记录单独保存，只证明记录时的版本和环境；普通 unittest 不启动这些会话，也不把历史实测当作当前环境已经复测：

| 日期 | 记录 | 当时版本 | 内容 |
|---|---|---|---|
| 2026-10-25 | [Cadra 跨会话接管](cadra/reports/2026-10-25-live-handoff.md) | Cadra 0.7.0 / 协议 0.7；Cohestra 0.12.0 / 契约 0.8 | 两个实际中断点、完成后重复 resume 与旧协议拒绝 |
| 2026-10-25 | [两个真实会话竞争接管](cadra/reports/2026-10-25-live-race.md) | 同上 | 同时 resume 的实际竞争、唯一所有者、失败方调用审计与预算保护 |
| 2026-10-26 | [add 规则读取量核对](cadra/reports/2026-10-26-add-reading-scope.md) | Cadra 0.9.0 / 协议 0.8 基线 | 静态字符计数对比，不是实际 agent 运行证据 |
| 2026-10-26 | [0.10 流程统一与本地切换](cadra/reports/2026-10-26-flow-unification.md) | Cadra 0.10.0 / 协议 0.10；Cohestra 0.13.1 / 契约 0.8 | 0.10 切换、网站检查和真实 live smoke；已被 0.11 取代 |
| 2026-11-02 | [add 真实会话附件留存](cadra/reports/2026-11-02-add-real-attachment.md) | Cadra 0.17.0 / 协议 0.12 | 真实上传图片与采用确认留存、独立只读交接；宿主自动提供附件临时路径，未执行 ready/run 或工程验收 |
| 2026-11-04 | [单任务 closeout 前向验证](cohestra/reports/2026-11-04-closeout.md) | Cohestra 0.16.0 草稿 / 协议 0.8 | 隔离项目实际独立初审、整改、复审、验收与收尾；最终草稿重复调用复用证据，未实测全部异常路径 |
| 2026-11-04 | [closeout 跨会话并发实测](cohestra/reports/2026-11-04-closeout-concurrency.md) | Cohestra 0.16.0 草稿 / 协议 0.8 | 两个实际执行会话与未完成 Run 夹具共存、真实验证进程互斥、已知同文件冲突停止及安全接续；占用信息和项目锁为明确输入 |
| 2026-11-05 | [need/design 共用澄清真实会话](cohestra/reports/2026-11-05-clarification.md) | Cohestra 0.16.1 草稿 / 协议 0.8 | 四个隔离项目实际澄清、拒答受阻和授权代决；核对真实交付、YAML 与输入摘要，未覆盖 unattended |
| 2026-11-06 | [最终整体确认独立真实会话](cohestra/reports/2026-11-06-overall-confirmation.md) | Cohestra 0.17.0 草稿 / 协议 0.8 | 六个执行会话覆盖整体确认、拒答/认可、修订、免除、复用及无人值守；另有独立终态裁决，保留核对器误报与修正证据 |
| 2026-11-06 | [单独 review 独立审查实测](cohestra/reports/2026-11-06-standalone-review.md) | Cohestra 0.18.0 草稿 / 协议 0.8 | 默认独立派发、受控子 agent 禁用、明确自审例外、复用原 reviewer 复审；核对候选、发布与阶段停止边界 |
| 2026-11-06 | [单独 review 完整验证](cohestra/reports/2026-11-06-standalone-review-full.md) | Cohestra 0.18.0 草稿 / 协议 0.8 | 独立规则审查、真实 CLI 安装/迁移、10 个新增行为场景、发布失败与同轮恢复、竞争写入保留、closeout 实际验收 |
| 2026-11-07 | [确认交接与运行过程](cadra/reports/2026-11-07-preparation-process.md) | Cohestra 0.19.0／Cadra 0.18.0 草稿，协议不变 | 三个独立会话实测确认收敛、直接／重复 ready、拒绝路径、同步恢复、真实 Task 并发更新及旧 Run 逐任务报告；主会话回读核对，未升级实际安装副本 |

当前验收要求以各[场景清单](#行为场景与辅助工具)为准；报告中的通过数量只对应所列版本。

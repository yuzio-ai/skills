# 测试与场景清单

本目录保留当前自动化测试、行为场景与可复用测试输入，也保留被当前测试复用的旧模型及部分冻结验证报告。其他历史资料可从 Git 历史查阅。历史报告、快照和日志只证明记录时的结果，不代表当前环境已经复测；旧模型的复用范围见下表，不表示技能运行时支持旧协议。

## 目录

```text
tests/
├── cadra/      # 模型、回归测试、包检查、场景和夹具
├── cohestra/   # 包检查、场景、输入生成器和产物核对器
├── relatra/    # 包检查、离线回归测试和场景
├── vistra/     # 包检查和行为场景
└── shared/     # 通用包检查工具、存储与路径测试和场景
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
| [test_cutover.py](cadra/test_cutover.py)、[一次性切换工具](../tools/cutover_cadra_010.py) | 历史 0.10 环境的本地归档、摘要、Gate 失效、安装切换、链接修复与回滚；工具要求匹配的 0.10 来源包，不用于当前 0.11 迁移；离线旧 YAML 读取需 macOS 系统 Ruby |
| [test_run_guard.py](cadra/test_run_guard.py) | 直接执行包内写入器；进程竞争、归属交接、预检约束、调用及历史保护；不执行真实工程阶段 |
| [test_guard_safety.py](cadra/test_guard_safety.py) | 停止与 skipped、计费依据及上限、合法恢复、复审旧轮次的真实文件回归；跨 Run 轮次另用当前模型核对 |
| [test_validate_check.py](cohestra/test_validate_check.py) | 用隔离合成产物核对旧任务拒绝、损坏契约、正常发布与解析故障，以及汇总和 CLI 退出码；不执行真实 agent 阶段 |
| [Cadra](cadra/test_package.py)、[Cohestra](cohestra/test_package.py)、[Relatra](relatra/test_package.py) | 各包结构、元数据与资源完整性；Cadra/Cohestra 另检查路由、模板与契约 |
| [test_relatra.py](relatra/test_relatra.py) | 合成历史的采集、统计、账本复用、更正和隔离包调用 |
| [test_reports.py](relatra/test_reports.py)、[周期报告样例](relatra/examples/README.md) | 重点正文与完整明细、日周月归纳、锚点、资源覆盖及可复现样例 |
| [test_vistra.py](vistra/test_vistra.py) | 包内引用、元数据、来源、许可证与可移植性 |
| [package_checks.py](shared/package_checks.py)、[test_package_checks.py](shared/test_package_checks.py) | 通用链接与资源检查、缺失及越界回归、仓库文档链接、双语 README 导航一致性 |
| [test_local_storage.py](shared/test_local_storage.py)、[test_project_data_paths.py](shared/test_project_data_paths.py) | 临时 Git 仓库中的存储语义、维护路径 |

包检查只依赖 Python 标准库。共享工具留在 `tests/shared/`，不会成为已安装技能的依赖。隔离检查完整复制单个技能包（含隐藏模板文件），核对资源可达性、包内边界及逐文件内容；不等于通过安装器安装、宿主发现入口或实际技能执行。链接检查验证内联 Markdown 链接的文件/目录目标，不验证章节锚点和外部网址。

[Cadra 修订夹具](cadra/fixtures/pre-call-blocked-revision.json)保留当前回归所需输入，不包含历史错误输出；期望结果由测试断言维护。

固定小组的 [test_scheduler.py](cadra/test_scheduler.py) 直接调用包内 reducer 和真实 CAS 发布，覆盖文件范围、FIFO、阶段内等待、验证窗口、失败取消、候选刷新及跨代恢复；另覆盖输入路径别名、明确不存在与缺失记录的区别、停止策略下已完成阶段的收尾，以及无新调用仍须经过小组 close。工具观察是明确的合成输入，不代表真实工程阶段已执行。

[列表汇总](cadra/test_list_summary.py)检查状态、来源链、折叠、详情与只读快照，包括未属于已 close 小组的 0.11 completed 条目显示 unknown；[0.10 历史查询](cadra/test_list_legacy.py)覆盖原协议语义、混合版本、跨协议链拒绝、独立安装副本和文件/时间不变，并直接验证 0.11 执行写入器仍拒绝旧记录。YAML 列表夹具使用系统 Ruby/Psych，JSON 夹具及包结构检查只用 Python 标准库。

[列表成本与生命周期](cadra/test_list_optimization.py)覆盖未闭合前驱、合法闭合前驱、过滤后的异常保留、身份去重、结果摘要/原文等价性、预检索引及调度视图复用。千级/万级队列、密集异常和真实历史详情的对照验证见 [独立验证脚本](../output/cadra-list-scaling-20261030/verify.py)；合成身份不是实际工程执行证据，耗时和 token 计数分别报告。

## 版本检查

[版本规则](../AGENTS.md#版本管理)由 [release_checks.py](shared/release_checks.py) 和 [回归测试](shared/test_release_versions.py) 支持，并通过各包测试纳入统一入口。检查工作区内容与当前版本首次提交的内容是否一致，覆盖未跟踪资源、已提交的同号修改及版本回退。完整 Git 历史是必要条件；无历史或浅克隆会显示跳过，发布前必须补齐历史并确认没有跳过。版本增量级别和协议语义兼容性仍需人工判断。

## 行为场景与辅助工具

- [Cohestra](cohestra/scenarios.md)：阶段、契约、索引发布与只读报告。
- [Cadra](cadra/scenarios.md)：任务编排、修订与恢复。
- [Relatra](relatra/scenarios.md)：目标、证据、统计、复用与更正。
- [Vistra](vistra/scenarios.md)：静态图片流程、预算、配置与交接。
- [本机资料与正式文档](shared/scenarios.md)：存储与跨技能交付边界。

Cohestra 的报告输入生成器、validate 故障驱动和产物核对器见对应场景清单；它们辅助隔离验证，不代替实际阶段执行。场景清单定义验收要求，不记录一次性通过数量。结构检查、模型测试、实际调用和视觉验收分别报告。

真实宿主验证单独保存：[2026-10-25 Cadra 跨会话接管](cadra/reports/2026-10-25-live-handoff.md)及其机器可读证据覆盖两个实际中断点、完成后的重复 resume 与旧协议拒绝。普通 unittest 不启动这些会话，也不将历史实测当作当前环境已经复测。

[2026-10-25 两个真实会话竞争接管](cadra/reports/2026-10-25-live-race.md)补充同时 resume 的实际竞争、唯一所有者、失败方工具调用审计与预算保护；保留首轮测试驱动中止及修正后重跑的边界。

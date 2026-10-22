# 测试与场景清单

本目录保留当前自动化测试、行为场景与可复用测试输入。历史模型、一次性验证报告、执行快照和日志从 Git 历史查阅，不作为当前通过依据。

## 目录

```text
tests/
├── cadra/      # 模型、回归测试、静态检查、场景和夹具
├── cohestra/   # 场景、输入生成器和产物核对器
├── relatra/    # 离线回归测试和场景
├── vistra/     # 包检查和行为场景
└── shared/     # 跨技能的存储、路径测试和场景
```

## 自动化检查

在仓库根目录执行：

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
python3 -B tests/cadra/static_checks.py
```

单独运行一个 skill 的测试时，指定对应目录并保留 `-t tests`，例如：

```sh
python3 -B -m unittest discover -s tests/cadra -t tests -p 'test_*.py'
```

各子目录的 `__init__.py` 用于递归发现和包内导入；新增测试放在对应目录并沿用 `test_*.py` 命名。

| 文件 | 检查范围 |
|---|---|
| [test_cadra.py](cadra/test_cadra.py)、[model.py](cadra/model.py) | Cadra v0.6 测试模型的流程、修订、预算和恢复约束；不是技能运行时 |
| [static_checks.py](cadra/static_checks.py) | 当前 Cadra 包结构、契约、版本与文档链接 |
| [test_relatra.py](relatra/test_relatra.py) | 合成历史的采集、统计、账本复用、更正和隔离包调用 |
| [test_vistra.py](vistra/test_vistra.py) | 包内引用、元数据、来源、许可证与可移植性 |
| [test_local_storage.py](shared/test_local_storage.py)、[test_project_data_paths.py](shared/test_project_data_paths.py) | 临时 Git 仓库中的存储语义、维护路径及链接检查器 |

[Cadra 修订夹具](cadra/fixtures/pre-call-blocked-revision.json)保留当前回归所需输入，不包含历史错误输出；期望结果由测试断言维护。

## 行为场景与辅助工具

- [Cohestra](cohestra/scenarios.md)：阶段、契约、索引发布与只读报告。
- [Cadra](cadra/scenarios.md)：任务编排、修订与恢复。
- [Relatra](relatra/scenarios.md)：目标、证据、统计、复用与更正。
- [Vistra](vistra/scenarios.md)：静态图片流程、预算、配置与交接。
- [本机资料与正式文档](shared/scenarios.md)：存储与跨技能交付边界。

Cohestra 的报告输入生成器、validate 故障驱动和产物核对器见对应场景清单；它们辅助隔离验证，不代替实际阶段执行。场景清单定义验收要求，不记录一次性通过数量。结构检查、模型测试、实际调用和视觉验收分别报告。

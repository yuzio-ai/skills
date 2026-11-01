# 历史验证与审查产物

本目录保存一次性验证、审查和发布前检查的原始记录，不是技能运行依赖，也不是当前行为说明。目录名中的日期是记录日期；技能行为以各包 `SKILL.md`、`release.json` 和 [测试场景](../tests/README.md) 为准。

| 目录 | 状态 | 说明 |
|---|---|---|
| `cadra-flow-unification-20261026` | 已跟踪，历史 | Cadra 0.10 切换、网站检查和 live smoke；被 [2026-10-26 流程统一记录](../tests/cadra/reports/2026-10-26-flow-unification.md)引用 |
| `cadra-list-scaling-20261030` | 纳入版本管理，历史 | 列表成本验证脚本、性能结果和真实历史只读查询记录；`verify.py` 被 [测试说明](../tests/README.md)引用 |
| `skills-release-preflight-20261030` | 纳入版本管理，历史 | 0.14.0 发布前检查、提交与推送核对，以及宿主验收摘要；完整演练工作区不在 Git 中 |

约定：新增记录应在目录内保留可复核的原始输出，并注明日期、对应包版本、结果和是否被维护文档引用；已被后续发布取代的记录只在有独立证据价值时保留。历史产物只证明记录时的版本和环境，不代表当前环境已经复测。

## 2026-11-01 清理

- 移除旧审查目录 `cadra-full-review-20261026`、`cadra-review-fixes-20261026`、`skills-review-20261026`；完整内容保留在 Git 历史提交 `6b3d452` 中。
- 移除 `cadra-flow-unification-20261026/live-smoke/fixture/.yuzio/` 解压副本；75 个文件已与保留的 [fixture-evidence.tar.gz](cadra-flow-unification-20261026/live-smoke/fixture-evidence.tar.gz) 逐字节核对。
- 移除重复的 `cadra-flow-unification-20261026/cutover-plan.json`，相同内容保留在 `cutover-preflight.json`；移除空的 `cutover-preflight.log`。
- 移除 `cadra-list-scaling-20261030/yaml-report.json`，完整结果保留在同目录 `report.json` 的 `yaml_validation` 字段。

保留被测试说明或历史报告引用的证据、性能验证脚本及结果，以及本次纳入 Git 的发布核对记录。

## 版本管理与临时产物

提交目录索引、可复用验证脚本、被文档引用的原始结果及必要日志和验收归档。临时工作目录使用 `tmp/` 或 `.tmp/`；仅供本机使用的资料放在 `output/.local/`。这些目录、嵌套的 `.yuzio/` 解压副本和 `.tmp`、`.bak` 文件由根 `.gitignore` 定向忽略。报告、日志、JSON 结果和归档不整体忽略；新增内容仍需检查保留价值与敏感信息。

历史记录中的机器绝对路径、临时目录和项目相对文件名用于标识当时的输入与来源，不是当前可用路径或复现前提。原始时间、文件摘要和测量数据保持原样，不通过改写记录伪装重新验证。

发布检查按记录时间读取：`validation.json` 是发布前状态，`pushed.json` 是后续核对记录，两者不代表当前远端状态。[宿主验收摘要](skills-release-preflight-20261030/host-acceptance.json) 是从原临时目录逐字节归档的历史摘要，包含校验结果、Run 摘要及命令观察；它不包含完整演练工作区和全部候选文件。`pushed.json` 中的原绝对路径保留为来源标识。

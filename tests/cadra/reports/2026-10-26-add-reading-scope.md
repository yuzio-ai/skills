# add 规则读取量核对

日期：2026-10-26。基线为同次交付中 add 精简前的未提交 Cadra 0.9.0，协议 0.8；保留 list 与自动收尾报告改动。

## 计数口径

- 统计 Unicode 字符数（Python `len(text)`，含空白及换行），同一路径中每份规则只计一次。仅统计技能规则与模板，不含项目规范、Task/Run 数据、工具输出、推理或最终回复。
- 调整前按入口范围计数：普通路径整读入口明确要求的文件；绑定路径按其显式链接的契约前置检查章节计数，包含下属完成前置核对。另列整文件读取参考量，避免将可能的全文加载当作必读。
- 调整后遵循 add 明确指定的章节范围；同次调用已读规则可复用。计数不代表实际模型读取行为、token、时间或资源消耗，不能据此声称实际加速。
- 编辑示例为已有合法 Run 链、无既有交付绑定的新定义修订；新建示例无旧协议、异常、依赖及初始化。异常、绑定与迁移按条件增读，项目数据量不在本表内。

## 对比

| 路径 | 调整前按入口范围 | 调整前整文件参考 | 调整后指定范围 |
|---|---:|---:|---:|
| 普通新建 | 10104 | 10104 | 8053 |
| 编辑已进入 Run 的定义 | 11480 | 11480 | 8053 |
| 新建并绑定已有交付 | 11453 | 16626 | 8616 |

## 文件与章节范围

调整前共同范围：`SKILL.md`、`release.json`、`references/workflow.md`、`references/storage.md`、`references/add.md`、`references/task-rules.md`、`references/flow.md`、`assets/task.md`。编辑额外读取 `references/revision-rules.md`；绑定额外读取 `references/contract.md#前置检查与首个动作`。

调整后共同范围如下。编辑的修订维护已经包含在任务定义中；绑定另增 `references/binding.md`（563 字符）。不沿链接预读 Gate、Flow 执行、终态映射、预算、恢复或迁移规则。

| 规则范围（相对 cadra 包根） | 字符数 |
|---|---:|
| `SKILL.md` | 1923 |
| `release.json` | 133 |
| `references/add.md` | 1410 |
| `references/task-definition.md` | 1332 |
| `references/flow-config.md` | 773 |
| `assets/task.md` | 771 |
| `references/workflow.md#身份与归属` | 690 |
| `references/workflow.md#共同写入` | 674 |
| `references/storage.md#本机容器与忽略` | 347 |

## 安全与验证边界

- [add](../../../cadra/references/add.md) 保留归属、目标来源链、可达依赖图、写前重读、原子保存与回读；现有检查只延后到其负责入口，不凭缩小上下文放行执行。
- [Ready Gate](../../../cadra/references/task-rules.md) 继续核对依赖完成情况；既有交付或执行依据的起点项加载完整契约，run/append 继续复核。Task/Run schema 与协议没有变化。
- 人工路由核对涵盖新建、编辑、绑定及旧协议分支；完整仓库检查涵盖链接、独立包资源、协议模板和版本历史。没有新增匹配文案措辞的测试。
- 真实 agent 行为、错误恢复、首次/复用上下文耗时及 token 节省尚未实测。人工场景见 [验收清单](../scenarios.md#add-读取与校验验收)。

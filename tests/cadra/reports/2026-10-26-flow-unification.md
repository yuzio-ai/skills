# Cadra 0.10 流程统一与本地切换

## 交付

- 主预设统一为 `code`（默认）、`fix`、`review`；仅评审使用 `[review]`。code 覆盖开发、重构和清理。
- Cadra 包 0.10.0 / 协议 0.10，仅接受当前协议，删除运行时旧协议解析和旧预设别名。Cohestra 包 0.13.1 / 契约 0.8，更新交叉说明。
- 原有独立 worker/reviewer、整改复审、预算、CAS、原子追加、停止观察、恢复及报告登记保护保留。
- 同步仓库中英文说明及网站中英文文案、类型化页面内容和采用说明。未提交、推送或部署。

## 验证

| 检查 | 结果 | 证据 |
|---|---|---|
| 完整技能测试 | 299 项通过，无跳过 | [日志](../../../output/cadra-flow-unification-20261026/skills-tests.log) |
| 完整 Git 历史版本检查 | Cadra / Cohestra 均无问题，仓库非浅历史 | 由完整测试及 release_issues 核对 |
| 源码与安装副本 skill-creator quick_validate | 两包均通过 | PyYAML 仅临时安装至 /tmp，用于验证器，不进入技能运行依赖 |
| 网站 lint / typecheck / build | 通过 | [构建日志](../../../output/cadra-flow-unification-20261026/site-build.log) |
| 网站中英文页面、响应式、键盘、复制和语言切换 | 28 项通过 | [浏览器日志](../../../output/cadra-flow-unification-20261026/site-playwright.log) |
| 一次性切换工具 | 16 项隔离测试通过；独立复核无剩余可操作缺陷 | [测试](../test_cutover.py) |
| Mewoo 文档结构与本地链接检查 | 通过 | Scripts/check_document_ownership.py；不代表原生运行或视觉验收 |

Chromium 首次启动被 macOS 沙箱拒绝；获工具授权后在沙箱外完成相同本地浏览器检查，未修改权限配置。回滚在临时夹具中验证，未对真实切换执行回滚。

## 本地切换

原 `run-20261026-04` 后续正常闭合，原聊天经官方状态查询确认为 idle，最后工具已完成；现场复核全部 Run 已结束且无未闭合调用后才执行切换。

- Mewoo 37 项 Task 的最新结果均为 completed，无待办需要转换或重新入队。
- 原容器 103 个文件逐字节归档；10 个旧 Run 不进入新版运行时来源链。
- 当前容器仅保留新版上下文与空 tasks/runs；185 处本机证据和 5 处项目文档引用完成路径修复，共 190 个文件。
- 原件与修复链接的阅读副本分开保存；原件摘要与切换前一致。
- 已备份并同步 ~/.agents/skills/cadra、cohestra 共 55 个文件；安装副本与源码逐文件摘要一致。
- 归档、安装、引用和空队列均已回读核对，[机器结果](../../../output/cadra-flow-unification-20261026/cutover-verification.json)。

归档及回滚清单：`/Users/zhubowen/Documents/yuzio-ai/mewoo-ios/.yuzio/cadra-archive/20261026T123127459548Z/manifest.json`。原始容器与安装副本在同目录 original/，当前源码和新证据保留在各自仓库。切换工具位于 [tools/cutover_cadra_010.py](../../../tools/cutover_cadra_010.py)，不随技能包安装。回滚会拒绝覆盖切换后的新增工作或修改。

## 真实阶段验证

[真实派发记录](../../../output/cadra-flow-unification-20261026/live-smoke/README.md) 与 [结构化结果](../../../output/cadra-flow-unification-20261026/live-smoke/result.json) 已冻结；Run 副本经父执行者重新调用当前 guard 校验通过，全部调用已派发、已闭合，自动报告已登记。

| 配置 | 实际阶段 | 结果 |
|---|---|---|
| code | code → review → validate | completed / passed |
| fix | fix → review → validate | completed / passed |
| review | review → fix → review → validate | completed / passed；1 轮整改 |
| [review] | review | 按预期 blocked；发现必做整改但不扩大范围 |

共 11 次真实阶段调用、7 个独立角色身份。实现与评审串行，同任务复用原角色，跨任务不复用。[review] 无 worker、源文件摘要未变，全部测试文件未变。控制器只建立夹具、调度并核对契约；各阶段由实际子 agent 发布交付。

交付范围限于临时 Python 项目，不代替生产项目、原生运行或宿主恢复/追加竞争验收。完整夹具、索引、handoff、候选、发布/停止证据和报告均有冻结副本。宿主没有会话释放 API，仅确认已完成及工具停止，不伪造释放。控制器夹具曾在记录 task02 调用之前修正一次 int(None) 辅助错误，无阶段重放或重复计费；这不是技能源码缺陷。

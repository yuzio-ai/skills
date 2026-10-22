# YUZIO Skills

[English](README.md) · **中文**

集中维护可复用的智能体技能。各技能目录是完整安装单元；仓库中的测试与维护文档不随技能运行。

## 技能概览

| Skill | 用途 | 入口 | 版本与协议 |
|---|---|---|---|
| cohestra | 初始化项目上下文，按需执行工程阶段、偏差核对和只读报告 | [SKILL.md](cohestra/SKILL.md) | [release.json](cohestra/release.json) |
| cadra | 准备任务、串行调用 Cohestra，并管理执行状态与恢复 | [SKILL.md](cadra/SKILL.md) | [release.json](cadra/release.json) |
| relatra | 汇总指定项目的 agent 成果、遗留与已观测资源 | [SKILL.md](relatra/SKILL.md) | [release.json](relatra/release.json) |
| vistra | 评审、探索、比较和交接移动端、桌面端及品牌静态视觉 | [SKILL.md](vistra/SKILL.md) | [release.json](vistra/release.json) |

执行规则以各包内文档为准。Cohestra 每次调用执行一个阶段；Cadra 的工程阶段执行需要可用的 Cohestra。Relatra 需要 Python 3.9+，仅使用标准库；Vistra 生成或编辑图片需要宿主提供图像能力。

## 安装

在目标项目根目录执行所需技能的安装命令：

```sh
npx skills add yuzio-ai/skills --skill cohestra
npx skills add yuzio-ai/skills --skill cadra
npx skills add yuzio-ai/skills --skill relatra
npx skills add yuzio-ai/skills --skill vistra
```

默认项目级安装；用户级加 `-g`，指定工具加 `-a <tool-a> <tool-b>`。本地未发布内容可使用源仓库绝对路径。也可把完整技能目录复制到宿主支持的位置，包含包内引用、模板、脚本及隐藏文件。安装不自动初始化业务项目。

安装、更新与排查见 [安装说明](cohestra/references/installation.md)。

## 调用

以下是在智能体中输入的调用示例，不是终端命令。占位符替换为实际任务内容；其他宿主使用各自入口。

```text
$cohestra code
需求：<目标、范围、验收条件>

$cadra add
任务：<任务名称>
需求：<目标、范围、验收条件>

$relatra 周报
项目：<明确项目集合>
报告目录：<绝对路径>

$vistra review
对象：<页面、素材或源码>
范围：<评审问题>
```

| 详细说明 | 入口 |
|---|---|
| Cohestra 阶段、交接与契约 | [公共流程](cohestra/references/workflow.md) |
| Cadra 准备、执行与恢复 | [公共流程](cadra/references/workflow.md) |
| Relatra 数据调用与统计口径 | [数据与调用](relatra/references/data.md) · [统计口径](relatra/references/metrics.md) |
| Vistra 模式、项目规范与配置 | [模式](vistra/references/modes) · [项目适配](vistra/references/project-adapter.md) |

## 本机资料与正式文档

`.yuzio/` 保存当前工作区的本机执行资料，根 `.gitignore` 使用 `/.yuzio/` 排除它。忽略不等于可丢弃或已有备份。需要共享的正式结论和附件进入项目文档目录，并可脱离本机资料读取。

各包独立携带具体约定：[Cohestra](cohestra/references/storage.md) · [Cadra](cadra/references/storage.md) · [Relatra](relatra/references/storage.md) · [Vistra](vistra/references/storage.md)。

## 维护与检查

仓库根目录运行全部自动化检查：

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

测试布局、单技能命令与验收场景见 [测试说明](tests/README.md)。检查覆盖包元数据、文档链接、隔离副本资源完整性及离线回归；实际安装器行为、智能体执行和视觉验收单独验证。

版本与协议在各包 `release.json` 维护，根 README 不重复记录版本值。Cohestra 协议变更须同步检查 Cadra 兼容性。保持中英文 README 同步；流程语义变化另行更新协议。提交、推送和发布标签需明确授权。许可证：[MIT](LICENSE)。

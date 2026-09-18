# YUZIO Skills

集中维护可复用的智能体技能。安装方式交给通用工具，任务上下文保留在各项目中。

| Skill | 用途 | 入口 |
|---|---|---|
| cohestra | 初始化项目上下文，按六阶段或 quick 模式执行并落盘交接 | [SKILL.md](cohestra/SKILL.md) |

## 安装 cohestra

在目标项目根目录执行，默认项目级安装：

```sh
npx skills add yuzio-ai/skills --skill cohestra
```

用户级安装可跨项目使用；也可以指定多个工具：

```sh
npx skills add yuzio-ai/skills --skill cohestra -g
npx skills add yuzio-ai/skills --skill cohestra -a codex codebuddy
```

远程命令需要源仓库已发布相应内容。尚未推送时，可从目标项目使用源仓库的本地路径：

```sh
npx skills add /absolute/path/to/skills --skill cohestra -a codex
```

技能目录、链接/复制和安装记录由 [skills CLI](https://github.com/vercel-labs/skills) 管理。安装不自动初始化项目；不想使用该 CLI 时，也可将完整 [cohestra 目录](cohestra/) 放入工具支持的技能位置。

## 调用

以下是在智能体中输入的技能调用示例，不是终端命令；其他工具使用各自入口。先初始化项目，再选择阶段，每次只读取对应说明。

```text
$cohestra init

$cohestra need
需求：<目标、范围、约束和参考>

$cohestra design
.cohestra/handoffs/<task-slug>/need-01.md

$cohestra code
.cohestra/handoffs/<task-slug>/design-01.md

$cohestra review
.cohestra/handoffs/<task-slug>/code-01.md

$cohestra fix
.cohestra/handoffs/<task-slug>/review-01.md

$cohestra validate
.cohestra/handoffs/<task-slug>/fix-01.md

$cohestra quick
问题：<原始症状、预期行为、范围和参考>
```

handoff 也可替换为对应任务目录，由任务 README 定位有效输入。六阶段代表职责，不要求机械走完；没有整改就不产生 fix。标准阶段交付后停止，quick 在既有授权内组合低风险修复；不自动分派智能体、提交或发布。

## 更新与职责

```sh
npx skills update cohestra -p
npx skills update cohestra -g
```

- 技能包保存规则、阶段说明和交付骨架；`.cohestra` 只保存项目入口、任务交付和复盘，不复制提示词。
- 没有 `$cohestra update` 项目同步命令；更新技能后，后续调用使用实际加载版本，历史决定和交付不回写。
- 用户级更新影响后续调用。项目需要独立固定版本时使用项目级安装，记录安装文件和 CLI 的锁文件，通过 Git 审查更新；锁文件不等于所有安装器都保证固定到同一 commit。
- `npx skills init` 用来创建一个新技能的 SKILL.md，不会初始化项目 `.cohestra`。
- 旧项目兼容与调用入口冲突处理见 [init](cohestra/references/init.md)；不默认删除旧提示词和历史记录。更多安装细节见 [安装说明](cohestra/references/installation.md)。

## 维护与验证

发行版 **0.4.0**，协作协议 **v0.3**。流程与提示词由 [公共流程](cohestra/references/workflow.md) 和对应阶段说明共同定义。技能本身只有 Markdown、模板和元数据，不依赖 Python，也不提供自研安装器。

修改后按 [验证场景](tests/cohestra-scenarios.md) 检查路由、文档链接、临时安装及交接流程。文件完整性检查和实际智能体调用分别报告；无独立智能体验证时，不把桌面推演写成实测。

发行版本在 release.json 维护；流程语义变化时另行更新协议版本。提交、推送和发布标签仍需明确授权。许可证：[MIT](LICENSE)。

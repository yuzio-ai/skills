# Relatra 推送前验收

日期：2026-10-15，Asia/Shanghai。版本 `0.1.0`，协议 `1`。本轮仅作本地准备，不暂存、提交、推送或发布。

## 公开记录

两份既有验收记录已去除本机用户名、临时目录绝对路径及仅本机可用的链接。保留历史日期、脱敏判断、统计、结果哈希和验收限制。原始日志与包含本机路径的详细运行记录保留在执行者的本地隔离目录，不纳入仓库。

## 最低运行版本

| 运行环境 | 结果 |
|---|---|
| Python 3.9.6 | 实际执行 63 项离线回归，全部通过 |
| Python 3.14.8 | 实际执行 63 项离线回归，全部通过 |

Python 3.9.6 的验证使用隔离模式 `-I -B`，未注入第三方 Python 包。继续声明 Python 3.9+；两个已测试版本不代表所有 Python 版本与操作系统均已验收。原生技能校验器自身的 PyYAML 依赖与 Relatra 运行依赖分开。

## 隔离安装与调用

- 使用本机已缓存的 skills CLI `1.7.1`，Node.js `24.12.0`；执行真实 CLI，不用文件复制代替安装。
- 在新建临时项目中仅选择 `relatra`、`codex`、项目作用域及 `--copy`。关闭安装遥测，将安装器状态目录指向隔离目录。
- 安装成功，`list --agent codex --json` 返回项目作用域的 `relatra`；七个安装文件与源包逐文件哈希一致。没有安装其他技能。
- 新的 Codex CLI `0.154.0` 进程通过 `$relatra` 加载项目安装目录的 SKILL.md、两份引用文档及脚本，完成配置、采集、账本审定、首版日报、correct 追加更正及第二版日报，最终退出码为 0。
- 合成输入只有一个咨询目标：交付 1、验收 0、业务轮次归属 1/1。用户授权更正后类型变为 documentation；目标 id/revision、交付证据和日期不变，第二版自带更正记录。首版所有文件及输入来源哈希未变。
- 主 agent 重新计算两版统计及 Markdown，均与产物一致；再用 Python 3.9.6 执行已安装脚本的原版与更正版报告入口，两版结果分别与 Python 3.14.8 逐字节一致。
- 模型连接初始超时，重连后恢复；受限环境内 CLI 初始化也曾被拒绝，允许测试进程初始化后完成。未修改用户配置来绕过问题，不将安装或列出成功当成实际调用通过。

可移植安装复现（将项目与源仓库路径替换为自己的隔离路径；命令可能需要下载该版本 CLI）：

```sh
cd /path/to/isolated-project
DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 XDG_STATE_HOME=/path/to/isolated-state npx --yes skills@1.7.1 add /path/to/skills --skill relatra --agent codex --copy --yes
npx --yes skills@1.7.1 list --agent codex --json
```

完整调用使用独立合成来源，覆盖配置、采集、目标审定、报告及显式更正；不读取真实用户历史，不把合成结果称为新的真实历史语义验收。真实历史验收见 [独立使用记录](relatra-forward-acceptance.md)。

## 最终内容核对

本轮允许范围为 `relatra/`、双语 README、Relatra 回归及验收记录。版本 `0.1.0`、协议 `1`、MIT 许可与 UI 元数据一致；原生 quick_validate.py 输出 `Skill is valid!`。相对链接、公开路径、差异空白和范围隔离通过最终检查。其他技能、原始日志、生成报告、隔离安装、锁文件及依赖不进入待提交内容。

最终允许提交的文件范围（仅核对，没有暂存）：

- `README.md`、`README.zh-CN.md`。
- `relatra/SKILL.md`、`relatra/LICENSE`、`relatra/release.json`、`relatra/agents/openai.yaml`、`relatra/scripts/relatra.py`、`relatra/references/data.md`、`relatra/references/metrics.md`。
- `tests/test_relatra.py`、`tests/relatra-scenarios.md`、`tests/relatra-forward-acceptance.md`、`tests/relatra-prepush.md`。

源脚本 SHA256：`67d51284f09c0e60a4e155865f611714b69289e2a0edaeab55bec1270d00afba`。合成输入、安装锁、执行事件和报告只存本地隔离目录；本公开记录不包含账号信息或原始业务日志。最终待提交范围为上述 13 个文件；Git HEAD 与暂存区保持本轮开始时状态，范围外 43 个已跟踪文件字节未变。用户级技能安装与原有安装锁未改变。

## 文档依据

安装参数已核对 [skills 官方文档](https://github.com/vercel-labs/skills) 及实际 CLI help；发现入口已核对 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills)。外部文档用于确定调用方法，是否通过以本轮实际产物与返回结果为准。

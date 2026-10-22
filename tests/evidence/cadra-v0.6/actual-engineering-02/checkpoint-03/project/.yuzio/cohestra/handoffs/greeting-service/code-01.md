# 问候服务 · code-01

## 身份与输入

- 协议：cohestra v0.8；Skill 发行版本：0.10.1。
- 技能来源：/Users/zhubowen/Documents/yuzio-ai/skills/cohestra/SKILL.md。
- 执行者及唯一业务/索引写入者：engineering_resume_first。
- 时间：2026-10-22T13:19:23.805741+08:00。
- 执行模式：unattended；阶段状态：已结束（completed）；阶段 code，轮次 1。
- 输入与上游依据：/private/tmp/cadra-engineering-recovery-kvs3043i/.yuzio/cadra/tasks/greeting-service.md revision 1；原始 Requirement、AC-1 至 AC-4 及既有实施授权；/private/tmp/cadra-engineering-recovery-kvs3043i/AGENTS.md；本次用户明确 $cadra resume run-20261022-02。
- 调用：run-20261022-02 / greeting-service / call 1；实际派发证据 /private/tmp/cadra-engineering-recovery-kvs3043i/verification/dispatch-call-01.json。
- 基线：Git 工作区尚无 HEAD，无提交；调用前 greeting.py 与 test_greeting.py 不存在。既有 prefix.py、test_prefix.py 哈希在候选清单中固定。
- 固定候选：[candidate-01/manifest.json](scratch/candidate-01/manifest.json)，含完整源码、依赖副本及新文件相对 /dev/null 的精确差异。

## 有效上下文

任务目录：/private/tmp/cadra-engineering-recovery-kvs3043i/.yuzio/cohestra/handoffs/greeting-service/。流程从 code 起步，small-change 允许 code/review/fix/validate；不补造 need/design。受控检查点仅中断 Cadra 记账，不声明任务终点。

有效需求：greet(name: str) 调用 greeting_prefix() 获取前缀。非空字符串原样保留（包括空白、Unicode）；仅空字符串使用 world，格式为 Hello, <name>!。不处理非字符串。实施与测试由原 Task 和本次恢复授权，范围未变。依赖 prefix-source 当前 revision 1 已完成，本次只读复用。

本任务为局部函数实现和恢复验证，无共享文档要求；本轮无需新增正式文档。

## 本阶段结果

新增 greeting.py 的 greet；新增 test_greeting.py 的三项测试，覆盖非空及边界输入、空串回退、运行时获取共享前缀。prefix.py 和 test_prefix.py 保持原哈希。

实现完成。作者自审已完成：逐项核对 AC、空白字符串未裁剪、Unicode 未归一化、空串分支及共享前缀调用；没有范围偏差或已知必做缺陷。作者自审不作为独立审查；本轮尚未执行 review 或 validate。

## 证据与限制

在固定快照目录执行 Python 3.14.8 标准库命令 `python3 -B -m unittest -v test_prefix test_greeting`，5 tests passed，退出码 0，其中既有依赖测试 2 项、本次新增 3 项；非空测试含 6 个子案例。

[实际测试记录](scratch/code-test-evidence.json) 保存准确解释器、时间、环境、命令、输出和候选清单摘要。默认沙箱执行，无网络、安装或提交。测试前复制并固定四个源码文件，测试后逐个校验工作区与快照哈希一致。AC-1 对应非空输入及空白/Unicode 子案例；AC-2 对应空串；AC-3 对应替换前缀的两次调用断言及源码导入；AC-4 对应本次实际通过日志。

当前没有 commit，使用可复核快照交接。独立审查、正式验收与提交发布未执行，不把测试通过等同整体验收 passed。

## 下一步交接

建议 `$cohestra review /private/tmp/cadra-engineering-recovery-kvs3043i/.yuzio/cohestra/handoffs/greeting-service/code-01.md`，附固定候选 manifest 与 test evidence，execution_mode: unattended。审查重点：字符串原样保留、空串边界、共享前缀依赖及 AC 覆盖。候选及测试环境变更需重新核对证据适用性。

按本次受控检查点要求，本阶段发布完整索引后停止；由后续 Cadra resume 核实同一 call 1 交付并补记结果，不重跑 code。

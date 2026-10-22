# 问候服务 · code-01

## 身份与输入

- 协议：cohestra v0.8；Skill 发行版本：0.10.1。
- 技能来源：/Users/zhubowen/Documents/yuzio-ai/skills/cohestra/SKILL.md。
- 执行者及唯一业务/索引写入者：engineering_resume_first。
- 时间：2026-10-22T13:19:23.805741+08:00。
- 执行模式：unattended；阶段状态：已结束（completed）；阶段 code，轮次 1。
- 输入与上游依据：/private/tmp/cadra-crash-recovery-xjhbj4gn/handoff_partial/.yuzio/cadra/tasks/greeting-service.md revision 1；原始 Requirement、AC-1 至 AC-4 及既有实施授权；/private/tmp/cadra-crash-recovery-xjhbj4gn/handoff_partial/AGENTS.md；本次用户明确 $cadra resume run-20261022-02。
- 调用：run-20261022-02 / greeting-service / call 1；实际派发证据 /private/tmp/cadra-crash-recovery-xjhbj4gn/handoff_partial/verification/dispatch-call-01.json。
- 基线：Git 工作区尚无 HEAD，无提交；调用前 greeting.py 与 test_greeting.py 不存在。既有 prefix.py、test_prefix.py 哈希在候选清单中固定。
- 固定候选：[candidate-01/manifest.json](scratch/candidate-01/manifest.json)，含完整源码、依赖副本及新文件相对 /dev/null 的精确差异。

## 有效上下文

任务目录：/private/tmp/cadra-crash-recovery-xjhbj4gn/handoff_partial/.yuzio/cohestra/handoffs/greeting-service/。流程从 code 起步，small-change 允许 code/review/fix/validate；不补造 need/design。受控检查点仅中断 Cadra 记账，不声明任务终点。

有效需求：greet(name: str) 调用 greeting_prefix() 获取前缀。非空字符串原样保留（包括空白、Unicode）；仅空字符串使用 world，格式为 Hello, <name>!。不处理非字符串。实施与测试由原 Task 和本次恢复授权，范围未变。依赖 prefix-source 当前 revision 1 已完成，本次只读复用。

本任务为局部函数实现和恢复验证，无共享
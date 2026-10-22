# 问候前缀 · code-01

## 身份与输入

- 协议：cohestra v0.8；Skill 0.10.1。
- 执行者：engineering_initial；时间：2026-10-22T13:14:38.603484+08:00；execution_mode: unattended。
- 阶段状态：已结束。
- 输入与上游依据：/private/tmp/cadra-crash-recovery-xjhbj4gn/handoff_partial/.yuzio/cadra/tasks/prefix-source.md，revision 1 Requirement 及本次用户授权。
- 基线：unborn main，无提交；任务文件此前不存在。
- 初始化：本轮实际建立 .yuzio/cohestra 最小容器。

## 有效上下文

任务目录为本目录。flow small-change 从 code 起步，允许 code/review/fix/validate。AC-1：greeting_prefix() 恒返回字符串 Hello；AC-2：标准库 unittest 通过。仅实现 prefix.py 及必要测试。用户明确授权两任务实施、验证和记录。本任务低风险纯函数，无独立审查硬性要求；后续 review 由同一执行者审查，须明确不是独立审查。没有正式共享文档需要。

## 本阶段结果

新增 prefix.py 的 greeting_prefix()，恒返回 Hello；新增 test_prefix.py，覆盖返回类型和值及重复调用稳定性。无其他业务修改。作者自审检查函数无状态、无参数、无外部副作用，范围符合要求。

## 证据与限制

候选固定为 scratch/candidate-01/，manifest.json 记录 SHA-256，逐文件 .diff 保存相对空基线精确差异。候选含 prefix.py、test_prefix.py 两个未跟踪文件；保留原有 AGENTS.md/.gitignore。命令 python3 -m unittest -v test_prefix：Python 3.14.8，受限本机环境，退出 0，2 tests OK。记录 scratch/code-test-evidence.json。无提交，无独立审查声明。

## 下一步交接

$cohestra review /private/tmp/cadra-crash-recovery-xjhbj4gn/handoff_partial/.yuzio/cohestra/handoffs/prefix-source/code-01.md
输入为本 handoff 与固定候选 scratch/candidate-01；审查函数契约及测试覆盖。Cadra 按 Front Matter 消费下一动作。

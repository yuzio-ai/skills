# beta-square · code-01

## 身份与输入

- 协议：cohestra v0.8；Skill 0.10.1，来源 /Users/zhubowen/Documents/yuzio-ai/skills/cohestra。
- 执行者：forward_validation，唯一索引维护者。
- 时间：2026-10-22T11:28:07.829612+08:00
- 执行模式：unattended。
- 阶段状态：已结束，completed。
- 输入与上游依据：/private/var/folders/2q/s5d5ttp9495_8f42knmdq69r0000gn/T/cadra-independent-resume-4h6ml3bw/.yuzio/cadra/tasks/beta-square.md；显式指定任务目录 /private/var/folders/2q/s5d5ttp9495_8f42knmdq69r0000gn/T/cadra-independent-resume-4h6ml3bw/.yuzio/cohestra/handoffs/beta-square。
- 固定候选：/private/var/folders/2q/s5d5ttp9495_8f42knmdq69r0000gn/T/cadra-independent-resume-4h6ml3bw/.yuzio/cohestra/handoffs/beta-square/scratch/code-01；manifest.json 记录全部任务文件 SHA-256；candidate.diff 保存精确差异。Git 无 HEAD；初始所有业务文件未跟踪，原内容保存在 verification/baseline。

## 有效上下文

流程起点 code，small-change 允许 code/review/fix/validate。用户授权对应模块与必要测试；无提交、无网络、仅标准库。当前定义 revision 1：实现 beta.py square(value)，返回整数输入的平方。仅修改 beta.py 与必要 tests/test_beta.py。AC1 负整数、零、正整数得到精确整数平方。不增加非整数输入校验或外部依赖。

## 本阶段结果

实现 square(value)，直接整数乘法，保留任意精度。作者自审负数、零、正数均得到非负平方。只修改 beta.py；已有 test_beta.py 可覆盖三个输入，无需增加镜像测试。

## 证据与限制

运行 python3 -m unittest discover -s tests -v：3 tests OK，包括 alpha 的两例及 beta 三个输入的一个测试。日志 verification/beta-code-01-test.log。候选只包含 beta.py 与 tests/test_beta.py，alpha 工作区改动保留。
环境：本机 Python 3，标准库 unittest，无网络，无额外权限。原始 alpha/beta 均抛 NotImplementedError，基线测试失败已保存在 verification/baseline-test.log。

## 下一步交接

$cohestra review /private/var/folders/2q/s5d5ttp9495_8f42knmdq69r0000gn/T/cadra-independent-resume-4h6ml3bw/.yuzio/cohestra/handoffs/beta-square/code-01.md；execution_mode: unattended。

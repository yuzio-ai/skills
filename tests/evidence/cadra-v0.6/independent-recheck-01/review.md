# Cadra v0.6 独立复核 · 2026-10-22

## 结论

协议复核发现 1 项未解决问题：首调用前 blocked 的执行依据和未消费修订动作缺少明确规则；测试模型会丢失尚未执行的需求变更。该发现不等于已证明实际智能体会错误验收。

## P2：首次调用前受阻的修订可能丢失累计变更

场景：revision 1 已完成；revision 2 修改 requirement，但依赖检查失败，尚未调用任何阶段即 blocked；revision 3 仅修改 execution_policy。

`tests/cadra_v06_model.py:99–111` 只跳过 skipped，把 revision 2 当作执行依据，并只累计更高修订的 changed_fields。因此输出 `basis_revision=2`、`cumulative_fields=[execution_policy]`、`revision_action=check_recovery`；尚未执行的 requirement 变更消失。独立复核者和主会话分别重现了相同输出。

`cadra/references/revision-rules.md:9` 同时要求跳过未执行的 skipped、查找“执行或收尾依据”、累计未执行修订，未定义无调用的 blocked 是否构成收尾依据。`recovery.md:7–9` 也没有明确这种未消费修订起点与旧 completed 交付的优先关系。`revision-rules.md:13` 禁止将旧验收用于新 requirement，所以不能据此宣称技能明确允许错误验收。

建议：按实际调用或有效收尾确定依据；明确保留首调用前 blocked 的未消费修订动作，累计其 requirement/flow 变更；补充此场景的回归测试。无需增加新调度层。

最初“新任务首次调用前受阻后必然无法恢复”的判断已撤销：`recovery.md:8` 后半句可以覆盖有充分未派发证据的原待调用动作。保留问题仅为作用域和修订继承不明确。

证据：[复现输入与输出](protocol-reproduction.json)、[主会话复核](parent-checks.json)。其中旧 R1 契约被 `decision` 单独映射为 completed，是单函数结果，不是端到端错误收尾证明。

## 独立性与范围

两个独立智能体使用空上下文启动，分别读取仓库规则开展协议审查和恢复实测；未提供既定结论，未让执行者读取协议审查发现。协议复核者运行现有 55 项 Cadra 测试，全部通过；新增边界未被这些测试覆盖。

恢复实测使用上一轮真实中断现场的隔离副本，本轮未重新制造自然中断。复制时仅重定位绝对路径并重算受影响的哈希引用，原始状态与结果保留；重定位记录位于归档内 `verification/relocation.json`。

本轮不修改技能规则或测试模型，只保存复核报告和证据。47 个规则及测试文件前后哈希一致，见 [前清单](package-before.json)、[后清单](package-after.json)。

## 独立恢复实测

| 场景 | 结果 |
|---|---|
| code-02 已交付、索引尚未发布 | 校验后补发索引，闭合原 call 1，未重跑 code |
| 继续执行 | 新增 call 2 review-02、call 3 validate-02；completed / passed；累计调用预算 3，整改与重试 0 |
| 重复 resume 已结束 Run | 无调用、无写入，前后哈希一致 |
| revision 3 仅修改 stop_queue_on_failure | 新 Run 修订收尾；调用与预算均 0；沿用 code-02 候选及 validate-02 验收 |
| 业务验证 | 6 个 unittest 通过，固定候选 7 组断言通过 |
| 历史隔离 | 旧 Run 01、既有 handoff、业务文件不变；策略修订期间 Cohestra 全部文件与 Run 02 不变 |

主会话另行核对全部最终哈希、基线差异、调用记录、重复 resume 前后清单，以及策略修订前后 requirement / flow 一致性，均符合记录。上述实际场景未触发协议复核发现的首调用前 blocked 边界，不能用来排除该问题。

证据：[最终审计](actual-resume/verification/independent/final-audit.json)、[独立动作记录](actual-resume/verification/independent/actions.json)、[重复 resume](actual-resume/verification/independent/second-resume.json)、[策略修订前清单](actual-resume/verification/independent/before-policy-change.json)、[业务测试](actual-resume/verification/independent/review-02-unittest.log)、[候选断言](actual-resume/verification/independent/review-02-check.json)。

归档保留 88 个文件的原始内容与绝对路径，排除临时 Git 数据和 Python 缓存；[归档清单](actual-resume-manifest.json) 对应实际保存的文件。执行者审计含现场缓存的哈希，缓存未归档。无需将归档绝对路径解释为当前仓库路径。

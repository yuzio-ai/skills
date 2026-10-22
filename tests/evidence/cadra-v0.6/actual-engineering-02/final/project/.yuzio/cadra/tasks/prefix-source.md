---
{
  "protocol": "0.6",
  "slug": "prefix-source",
  "title": "问候前缀",
  "revision": 2,
  "preparation": "ready",
  "priority": "medium",
  "dependencies": [],
  "flow": "small-change",
  "execution_policy": {
    "stop_queue_on_failure": true
  },
  "cohestra_task": ".yuzio/cohestra/handoffs/prefix-source/",
  "revision_base": {
    "run": "run-20261022-01",
    "revision": 1
  },
  "changed_fields": [
    "execution_policy"
  ]
}
---


# 问候前缀

## Requirement

在 prefix.py 实现 greeting_prefix() 恒返回字符串 Hello。用标准库 unittest 验证；不做其他业务改动。AC-1：每次无参数调用均返回字符串 Hello。AC-2：标准库 unittest 通过。

## 绑定与修订

- 绑定确认：无既有交付，无 Run 来源，首次定义。
- 创建：engineering_initial；2026-10-22T13:13:28.095844+08:00；Cadra 0.6.0 / 协议 0.6。
- 授权：本次用户明确授权实现、验证及技能记录。

## Ready Gate

尚未执行；revision 1。

Gate revision 1 通过：2026-10-22T13:13:36.503670+08:00。
- 目标：通过，恒返回 Hello。
- 范围：通过，仅 prefix.py 及必要 unittest。
- 验收：通过，AC-1/AC-2 可直接判定。
- 人类决定：通过，已明确授权，无产品取舍。
- 输入：通过，Python 3.14.8 与标准库可用。
- 依赖：通过，空列表。
- 起点：通过，无既有契约或正式交付，首次 code。
- 范围配置：通过，small-change 允许 code/review/fix/validate。
历史：首次 Gate，未替代旧放行。

## revision 2 修订记录

2026-10-22T13:27:29.109552+08:00，engineering_dependency_change；Cadra 0.6.0 / 协议 0.6。用户明确要求仅将 execution_policy.stop_queue_on_failure 从 false 改为 true。requirement、flow、dependencies、title、priority、slug 与 Cohestra 绑定保持不变。

当前 revision 1 已进入结束的 run-20261022-01，且 prefix-source 不属于唯一未完成 Run run-20261022-03，允许编辑并建立 revision 2。revision_base 指向 run-20261022-01 revision 1；旧定义来源为该 Run 的 prefix-source definition。绑定仍为 greeting_prefix() 恒返回 Hello 的同一任务，用户明确指定接续策略修改，现有契约 task=prefix-source / contract=0.8。

## Ready Gate · revision 2 失效

策略定义已变化，preparation=draft。revision 1 Gate 保留为历史，不放行 revision 2。本次未执行 ready、run 或 Cohestra 阶段；仅策略变化且原执行 completed 的后续修订收尾，仍需先重新 Gate 并核实旧契约和来源。

## Ready Gate · revision 2

2026-10-22T13:29:52.009863+08:00；Cadra 0.6.0 / 协议 0.6；engineering_continuous_revisions。
- 目标：通过，恒返回 Hello。
- 范围：通过，原业务范围不变，仅策略修订。
- 验收：通过，原 AC-1/AC-2 明确且未改。
- 人类决定：通过，用户明确授权本次 ready/run。
- 输入：通过，原代码、候选、验收与契约可读取且哈希一致。
- 依赖：通过，无依赖。
- 起点：通过，唯一来源 run-20261022-01 completed，完整契约相符；仅 execution_policy 变化，修订核对收尾，无需阶段调用。
- 范围配置：通过，small-change 未变。
本 Gate 只绑定 revision 2，旧 Gate 保留。

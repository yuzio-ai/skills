---
{
  "protocol": "0.6",
  "slug": "prefix-source",
  "title": "问候前缀",
  "revision": 1,
  "preparation": "ready",
  "priority": "medium",
  "dependencies": [],
  "flow": "small-change",
  "execution_policy": {
    "stop_queue_on_failure": false
  },
  "cohestra_task": ".yuzio/cohestra/handoffs/prefix-source/",
  "revision_base": null,
  "changed_fields": []
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

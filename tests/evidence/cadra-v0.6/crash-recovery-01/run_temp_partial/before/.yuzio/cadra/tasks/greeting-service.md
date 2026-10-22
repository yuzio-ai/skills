---
{
  "protocol": "0.6",
  "slug": "greeting-service",
  "title": "问候服务",
  "revision": 1,
  "preparation": "ready",
  "priority": "medium",
  "dependencies": [
    "prefix-source"
  ],
  "flow": "small-change",
  "execution_policy": {
    "stop_queue_on_failure": false
  },
  "cohestra_task": ".yuzio/cohestra/handoffs/greeting-service/",
  "revision_base": null,
  "changed_fields": []
}
---

# 问候服务

## Requirement

在 greeting.py 实现 greet(name: str)，使用 prefix.py 的 greeting_prefix()。非空字符串按原样返回 Hello, <name>!，空字符串返回 Hello, world!。不处理非字符串；增加必要标准库 unittest，不做其他业务改动。AC-1：非空 name 完整保留，包括空白和 Unicode；AC-2：空串使用 world；AC-3：前缀来自 greeting_prefix()；AC-4：相关 unittest 通过。

## 绑定与修订

无既有交付，首次定义。创建：engineering_initial，2026-10-22T13:16:34.150821+08:00；Cadra 0.6.0 / 协议 0.6。授权来自本次用户明确要求。

## Ready Gate

尚未执行，revision 1。

Gate revision 1 通过：2026-10-22T13:16:45.259254+08:00。
- 目标：通过，greet 的输出确定。
- 范围：通过，仅 greeting.py 与必要测试，排除非字符串。
- 验收：通过，四项 AC 可观察。
- 人类决定：通过，已授权且无待裁决取舍。
- 输入：通过，prefix.py 已完成；Python 3.14.8 可用。
- 依赖：通过，prefix-source 当前 revision 1 在 run-20261022-01 为 completed/验收 passed。
- 起点：通过，无既有交付或调用，首次 code。
- 范围配置：通过，small-change 允许 code/review/fix/validate。
历史：首次放行。

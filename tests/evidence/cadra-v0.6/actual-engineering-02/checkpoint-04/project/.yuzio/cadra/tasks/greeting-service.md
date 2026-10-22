---
{
  "protocol": "0.6",
  "slug": "greeting-service",
  "title": "问候服务",
  "revision": 2,
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
  "revision_base": {
    "run": "run-20261022-02",
    "revision": 1
  },
  "changed_fields": [
    "requirement"
  ]
}
---




# 问候服务

## Requirement

在 greeting.py 的 greet(name: str) 中先对 name 执行 strip()，去除首尾空白；strip 后为空则返回 Hello, world!，非空则返回 Hello, <trimmed name>!，保留内部空白。继续调用 prefix.py 的 greeting_prefix() 获取前缀。仍仅处理字符串，不处理非字符串；只修改问候行为及必要标准库 unittest，不做其他业务改动。AC-1：非空裁剪结果使用裁剪后的名称，内部空白及 Unicode 保留；AC-2：空串或仅含空白的字符串均使用 world；AC-3：前缀仍来自 greeting_prefix()；AC-4：相关 unittest 通过。

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

## revision 2 修订记录

2026-10-22T13:24:46.603770+08:00，engineering_resume_delivered；Cadra 0.6.0 / 协议 0.6。用户明确提出局部新需求，仅改变 requirement：先 strip，空结果用 world，非空保留内部空白。覆盖 revision 1 的原样保留首尾空白条款及仅空串回退条款。dependencies、flow、execution_policy、title、priority、slug 和绑定均不变。

绑定确认：仍为同一 greeting-service 函数；用户明确指定在同一任务修订。来源为已结束 run-20261022-02 revision 1；旧验收仅属于旧需求。当前 Gate 失效，preparation=draft；后续重新 ready。修订重启需从 small-change start=code 调用一次；本 add 未执行阶段、未建立 Run。

旧定义来源：.yuzio/cadra/runs/run-20261022-02.md 的 greeting-service definition。revision_base 按任务模板仅保存 run 与 revision。

## Ready Gate · revision 2

Gate revision 2 通过：2026-10-22T13:25:11.207543+08:00。
- 目标：通过，strip 后的字符串对应确定问候输出。
- 范围：通过，仅问候行为与必要测试；限定字符串，内部空白保留。
- 验收：通过，AC-1 至 AC-4 可观察；首尾空白、仅空白、内部空白均有明确预期。
- 人类决定：通过，用户明确授权本修订 add/ready/run 与受控 queued 检查点，无待定取舍。
- 输入：通过，原实现、固定候选及标准库测试可用，Python 3.14.8。
- 依赖：通过，prefix-source 当前 revision 1 的唯一链尾 run-20261022-01 为 completed，验收 passed。
- 起点：通过，旧执行依据 run-20261022-02 revision 1 completed，契约与交付一致；requirement 变化需修订重启 code，一次性授权尚未消费。
- 范围配置：通过，small-change 允许 code/review/fix/validate，配置未改。
历史：保留 revision 1 Gate 与 revision 2 失效记录；本次仅放行 revision 2，不沿用旧验收作为新需求完成依据。

---
{
  "protocol": "0.6",
  "slug": "alpha-greeting",
  "title": "alpha-greeting",
  "revision": 2,
  "preparation": "ready",
  "priority": "medium",
  "dependencies": [],
  "flow": "small-change",
  "execution_policy": {
    "stop_queue_on_failure": false
  },
  "cohestra_task": ".yuzio/cohestra/handoffs/alpha-greeting/",
  "revision_base": {
    "run": "run-20261022-01",
    "revision": 1
  },
  "changed_fields": [
    "requirement"
  ]
}
---




# alpha-greeting

## Requirement

实现 alpha.py greet(name)：先对输入字符串首尾空白做 strip；strip 后非空返回 Hello, <name>!；strip 后为空返回 Hello, world!。仅修改 alpha.py 与必要 tests/test_alpha.py。输入为字符串，不扩展其他类型行为。AC1 Ada 保持问候；AC2 空串、纯空格、制表符与换行归 world；AC3 首尾空白被去除，内部空白保留。

## 绑定与修订

- 绑定确认：无既有交付。
- 创建：forward_validation；2026-10-22T11:26:03.789015+08:00；Cadra 0.6.0 / 协议 0.6。来源：用户明确 add 请求。

## Ready Gate

当前结论：revision 1 draft，待 ready。

### Gate revision 1 · 2026-10-22T11:26:03.855066+08:00
当前结论：通过。
- 目标：通过；函数行为可判定。
- 范围：通过；对应模块与必要测试，排除外部依赖及其他模块。
- 验收：通过；输入输出及 unittest 可判定。
- 人类决定：通过；无未决取舍，用户已授权实现及测试。
- 输入：通过；项目模块、测试及 Python 可用。
- 依赖：通过；空依赖。
- 起点：通过；small-change start=code；首次无既有交付。
- 范围配置：通过；small-change allowed=code,review,fix,validate。

### 定义修订 · 2026-10-22T11:29:31.277800+08:00
用户第二轮明确 add 要求 strip 首尾空白，覆盖 revision 1 非空名字原样插入约束。旧定义以 run-20261022-01 tasks[alpha-greeting].definition 为真源。revision 1 Gate 失效；当前 revision 2 draft，待 ready。变更字段 requirement。既有 Cohestra 主题对应本函数，绑定不变。

### Gate revision 2 · 2026-10-22T11:29:31.305570+08:00
当前结论：通过。
- 目标：通过；函数行为可判定。
- 范围：通过；对应模块与必要测试，排除外部依赖及其他模块。
- 验收：通过；输入输出及 unittest 可判定。
- 人类决定：通过；无未决取舍，用户已授权实现及测试。
- 输入：通过；项目模块、测试及 Python 可用。
- 依赖：通过；空依赖。
- 起点：通过；requirement 修订由 code 重启；旧 Run 已结束且契约合法。
- 范围配置：通过；small-change allowed=code,review,fix,validate。

---
{
  "protocol": "0.6",
  "slug": "beta-square",
  "title": "beta-square",
  "revision": 1,
  "preparation": "ready",
  "priority": "medium",
  "dependencies": [],
  "flow": "small-change",
  "execution_policy": {
    "stop_queue_on_failure": false
  },
  "cohestra_task": ".yuzio/cohestra/handoffs/beta-square/",
  "revision_base": null,
  "changed_fields": []
}
---


# beta-square

## Requirement

实现 beta.py square(value)，返回整数输入的平方。仅修改 beta.py 与必要 tests/test_beta.py。AC1 负整数、零、正整数得到精确整数平方。不增加非整数输入校验或外部依赖。

## 绑定与修订

- 绑定确认：无既有交付。
- 创建：forward_validation；2026-10-22T11:26:03.824421+08:00；Cadra 0.6.0 / 协议 0.6。来源：用户明确 add 请求。

## Ready Gate

当前结论：revision 1 draft，待 ready。

### Gate revision 1 · 2026-10-22T11:26:03.885614+08:00
当前结论：通过。
- 目标：通过；函数行为可判定。
- 范围：通过；对应模块与必要测试，排除外部依赖及其他模块。
- 验收：通过；输入输出及 unittest 可判定。
- 人类决定：通过；无未决取舍，用户已授权实现及测试。
- 输入：通过；项目模块、测试及 Python 可用。
- 依赖：通过；空依赖。
- 起点：通过；small-change start=code；首次无既有交付。
- 范围配置：通过；small-change allowed=code,review,fix,validate。

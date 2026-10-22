# 项目任务编排上下文

- 项目：cadra-engineering-recovery-kvs3043i
- 初始化发行版：0.6.0
- 任务/Run 协议：0.6
- 入口：实际加载的 cadra 技能；add / ready / list / run / resume / report。

[tasks/](tasks/) 保存定义、修订与 Ready Gate。[runs/](runs/) 保存固定执行顺序、逐任务状态、checkpoint 与历史结果；报告为 `<run-id>-report-<轮次>.md`。队列在 list 中展示，不单独存文件。

同一项目至多一个未完成 Run。Task 不保存执行状态；通过 Run 的明确来源链解析当前结论。中断使用 resume，结束后的失败恢复使用新 run 的显式选择；定义修改经 add/ready，不改旧 Run 结果。

单任务工程证据在 `.yuzio/cohestra`，只引用不复制。本目录是本机恢复资料，项目根 `/.yuzio/` 忽略规则不提供备份；正式总结按任务与项目规范写入正式文档。旧协议不自动迁移，不用新容器覆盖旧记录。

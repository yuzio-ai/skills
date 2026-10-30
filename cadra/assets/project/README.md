# 项目任务编排上下文

- 项目：<实际项目名>
- 初始化发行版：<实际 Skill 版本>
- 任务/Run 协议：0.11
- 入口：实际加载的 cadra 技能；add / ready / list / run / append / resume / report。

[tasks/](tasks/) 保存定义、修订与 Ready Gate。[runs/](runs/) 保存已有顺序不变、允许尾部追加的执行队列、逐任务状态、checkpoint 与历史结果；报告为 `<run-id>-report-<轮次>.md`。队列在 list 中展示，不单独存文件。

同一项目至多一个未完成 Run。Task 不保存执行状态；通过 Run 的明确来源链解析当前结论。运行中用 append 追加 ready 任务；每项使用独立 worker/reviewer，任务内阶段串行，固定小组最多两项并行且不补位。所有成功项（包括无需新调用的核对收尾）须经小组最终候选核验并 close 后，才将 Run 条目标为 completed。中断使用 resume，结束后的失败恢复使用新 run 的显式选择；定义修改经 add/ready，不改旧 Run 结果。

单任务工程证据在 `.yuzio/cohestra`，只引用不复制。本目录是本机恢复资料，项目根 `/.yuzio/` 忽略规则不提供备份；正式总结按任务与项目规范写入正式文档。写入、准入与执行仅接受 0.11；list 可只读查询 0.10 原记录，不迁移或授权执行。旧协议须先在技能运行外完成备份、原 Run 收尾及归档切换。归档不参与扫描、来源链、状态或准入，不在技能入口内迁移。

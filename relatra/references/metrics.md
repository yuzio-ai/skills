# 统计口径

## 任务与历史

独立目标是任务，不是聊天、轮次、文件或提交。稳定 id 标识目标，revision 标识实质范围变化；缺陷重开同一修订。一个 turn 可以属于多个目标，但任务级资源归属共享未知，总体只计一次。子 turn 通过 root_turn_id 跟随父 turn；父关联未知时保留候选。

状态：pending_confirmation/in_progress/delivered/accepted/blocked/failed/cancelled。候选默认待确认。状态事件按时间与记录顺序重放到截止；交付/验收分别按首次发生时间计数，同 id/revision 重开后的再次交付不新增交付。日期未知事件单列，不计本期流量或截止状态。

每个目标的最新修订计期末存量，旧修订保留独立的历史交付流量，不能同时累加成两个期末目标。任务构成按主项目和任务类型列出最新修订。已知开始但仍未结束的目标可以保留为遗留；没有本期观测的历史 open turn 不算本期执行活动，也不推测其持续运行。

交付引用实际产物、问题解决或目标终点证据；验收引用明确用户认可或满足既定条件的验证。咨询/审查/设计/文档可以独立交付。实现的静态、构建、运行时验证不能互相替代。交付、验收、失败是本期流量；进行中、受阻、待确认是期末存量，不能相加计算成功率。用户未授权部署不等于未交付。

Cadra 本 Run 快照不能被后续成功覆盖；Cohestra README 是 current_only，只用于定位，不能补造旧周期状态。handoff/Run 没有明确时间时通过 dated turn 关联，仍不能猜日期或修订。

## 时间与交互

完成周期是有证据的 started_at 至首次交付时间，跨周期保留全程；没有开始为未知。轮次执行时长是明确 task_started 至 task_complete/turn_aborted，含工具和轮内等待；仅计算与窗口相交部分，缺结束不估算。累计时长是各 turn 之和，占用时长是区间并集；两者不是人工时长。显式等待单列，不盲减执行时长。共享 turn 的任务级时间/token 为未知。

只有本期出现用户消息且 turn_trigger=明确用户触发才算已确认交互轮；已核实 composer/user/user_message/plan_feedback，包括用户在计划中的反馈。缺失或未识别 trigger 为候选交互，不能既不确认又静默漏记；候选不证明人工介入。子 agent 或 owner 不明的继承轮次不确认为用户交互。跨日执行按区间裁剪，交互归到消息出现周期，不在后续日期重复计数。人工介入单独引证。中位数附有效/缺失样本数，不以零补缺。

过程事件：reopened/rework/retry/scope_changed/validation_passed/validation_failed/intervention/wait。intervention.category 为 clarification/decision/authorization/manual_fix；wait.category 为 input/approval/environment/dependency；validation 分类 static/build/runtime/user_acceptance/other。分类由 agent 引证，脚本重放和计数，自述不等于独立验证。同一实际过程事件按稳定事件 id 全局去重；多目标共享事件不可重复算人工介入或返工。未记录不等于未发生。

提问工具中实际提交的用户答复也属于人工介入证据，不仅检查 user 消息。一次答复包含多个问题仍计一次介入；同轮多次真实答复各计一次，但确认交互轮只计一个 turn。coverage.user_feedback 单列本期已观测/已分类答复及未分类证据；有未分类答复时人工介入统计不完整，不能据此断言人工介入少。

## 资源与覆盖

优先 token_usage_record.usage 的 response_id 调用增量；跨 fork、归档、复制及重复记录按 response_id 去重，不与 token_count 相加。旧格式 total_token_usage 只取同 session 单调增量：首个累计值没有基线时未知，回退/缺 turn/继承归属不明的增量弃用并说明。last_token_usage 不补造调用。

缓存输入属于输入，推理输出属于输出，不再加到总量；每个字段可独立未知。仅保存已定义的数值字段，无效值标缺口。显示有效资源 turn/观察执行 turn 覆盖，并保存各字段的 turn 覆盖。不是账单，不换算额度、订阅/API费用。

范围是可读取本地记录，无法保证全部云端/删除历史。未映射 turn、截断/损坏行、未知格式、无父关联和未定日期事件单列。归并覆盖以发现的 turn 为分母，不推断未发现任务。时间窗口 `[start,end)`，按配置时区自然日历构造，DST 正确处理。未来状态不泄入旧周期，文件名/mtime 不作日期。facts/ledger/correction 哈希与版本保留；相同输入的 statistics.json 相同，生成时间放 manifest。

前期比较只用相同项目、类型、口径和覆盖的基础数据，附样本量及构成变化；没有前期数据不造趋势。

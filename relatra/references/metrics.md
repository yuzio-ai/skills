# 统计口径

## 普通模式

独立目标是任务，不是聊天、轮次或提交。状态为 pending_confirmation/in_progress/delivered/accepted/blocked/failed/cancelled。按有日期事件的时间与记录顺序重放到截止，reopened 恢复 in_progress。未定日期事件单列，不计本期流量或截止状态。

同 id/revision 的首次交付、首次验收各计一次；重开后再次交付不新增。只有每个目标最新修订计期末存量，旧修订保留历史交付流量。交付、验收、失败是本期流量，进行中、受阻和待确认是期末存量，不相加算成功率。用户未授权部署不等于未交付。

跨期目标保留有证据的起点及首次交付，完成周期取二者全程；未知起点不补零。复用后未闭合目标仍列遗留，即使本期没有活动；历史 open turn 不据此推测本期执行时间。证据失配目标保持待核实，不把重新发现的旧成果计为新交付。

轮次时长取明确 task_started 到 task_complete/turn_aborted，并裁剪至统计窗口；缺端点为未知。累计时长是各 turn 之和，占用时长是区间并集，包含工具及轮内等待，不是人工时长。共享 turn 的任务级资源未知，总体只计一次。子 turn 通过 root_turn_id 跟随父目标，父关联未知保留候选。

资源优先 token_usage_record 的 response_id 增量，跨 fork/归档/复制去重，不与 token_count 相加。旧累计只取同 session 可归属的单调增量；无基线、跨未知归属或回退弃用，零增量不制造调用覆盖。独立调用实测零值有效，last_token_usage 不补调用。

缓存输入属于输入，推理输出属于输出，不重复加到总量。每个字段可独立未知，保留字段覆盖与无效值缺口；不换算账单。正文末尾一行展示累计执行时间、token 总量及其中的缓存输入；时间用小时、分钟，token 用万、亿等短单位，舍入值标“约”，未知字段分别写未知。有采集诊断、相应字段覆盖不足或 token 记录不完整时，将已知数值标为部分观测值。明细保留准确时分秒与原始秒数、千位分隔的 token 整数，以及占用时长、计量说明及完成周期。格式化不改变 JSON 数值、采集或统计计算。

basic 的 process_reviewed 必须为 false；process_events、interventions、recorded_wait_seconds_union 及用户答复分类统计为 null，含义是未统计，不是零。普通模式仍记录影响状态的重开、验收及重要阻碍；发现个别事件不能推断完整过程总量。

## 深度模式

仅在 deep 时核读本期完整相关过程证据，再将账本 process_reviewed 设为 true。每次 collect 重置为 false，即使复用了深度报告；未完成时可生成报告，但过程汇总仍为 null。true 表示执行者已复核本期可读取记录，不保证未发现历史完整。

过程事件为 reopened/rework/retry/scope_changed/validation_passed/validation_failed/intervention/wait。同一真实过程事件使用同一 id 和内容，全局只计一次；不同介入或重试必须不同 id。正常范围补充不算返工，未记录不等于未发生。

分类：intervention.category 为 clarification/decision/authorization/manual_fix；wait.category 为 input/approval/environment/dependency；validation 的 category 与 basis 都为 static/build/runtime/user_acceptance/other，且必须一致。显式等待另给 until（未知 null），已知区间裁剪后取并集，不从执行时间盲扣；没有完整等待区间显示未知。

user_feedback 是按 call_id 配对到 request_user_input/request_user_input_async 的真实非空 answers，保留提问与答复引用。必须同时核读两者再分类，一次批答复计一次介入；默认选项、空答案或孤立结果不能证明选择，普通偏好不替代验收。coverage.user_feedback 保留已观测/已分类数量及未分类证据；有未分类答复时人工介入统计不完整。

确认用户交互轮必须有本期真实用户消息，且 turn_trigger 明确为 composer/user/user_message/plan_feedback。未知 trigger 保留候选；子 agent 或 owner 不明的继承轮次不确认为用户交互。跨日交互归消息所在周期，同轮多次答复只算一个交互轮，人工介入另计。

深度报告按基础数据计算周期趋势：周报按日、月报按七日片段、季报/年报按月；日报无趋势表。趋势表和详细过程统计放在明细，正文仅归纳有依据的关键判断。过程分析未完成时趋势的过程字段也为 null。长周期不平均短周期中位数或比例。

## 比较与覆盖

时间窗口为 `[start, cutoff)`，按配置时区自然日历构造并处理 DST。未知日期不猜，当前文档不能回填历史。相同 facts 和账本产生相同 statistics.json；生成时间与更正原因放 manifest，facts/ledger 哈希保留。

覆盖只针对可读取本地记录，不保证云端、删除历史完整。正文分别展示任务归属、时间及总 token 的已知轮数，不以其他 token 字段存在代替总量覆盖；另提示不完整资源记录和未定日期事件。明细与 JSON 保留全部采集诊断，不将任意警告统一解释为归属缺失。报告头的已发现活动首末日期是展示信息，由本期未排除轮次活动时间及明确执行区间计算，不是连续完整覆盖声明，不新增统计字段。归并覆盖以发现的 turn 为分母，不推断未发现任务。

前期比较从双方已封存基础输入重算，按相同项目与类型并列，并保存样本、构成和覆盖。项目、来源、版本、周期或时区不同，窗口重叠或阶段性窗口均不比较；自定义周期还要求天数一致。

成果、时间、资源沿用归属、时间区间、字段覆盖和诊断缺口检查；模式不同不单独禁止这些指标比较。除固定范围提示外，任一方存在采集诊断时仅并列观察值，不判断改善；相同的警告数量或都有警告不证明缺口相同。过程指标须双方 process_reviewed 为 true、覆盖检查满足且不存在未分类工具用户答复，否则不比较。覆盖或构成改变不能直接解释为效率改善，不推断因果或模型排名。

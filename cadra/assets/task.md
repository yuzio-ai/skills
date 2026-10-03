# <任务名称>

## 任务定义

- title：<任务名称>
- slug：<task-slug，稳定英文短横线名称>
- status：draft / ready / queued / running / completed / blocked / failed（附结论与原因）
- priority：high / medium / low（缺省 medium）
- dependencies：<task-slug 列表及其当前状态；无则写无>
- flow：<preset 名或显式阶段序列；缺省 full>
- execution policy：<stop_queue_on_failure: true/false；缺省 false>
- requirement：<目标、范围、排除项与验收条件>
- cohestra_task：.cohestra/handoffs/<task-slug>/
- 绑定确认：<cohestra_task 绑定时已有正式交付的主题摘要与用户确认记录；无既有交付写无（见公共流程第 6.1 节收养核对）>
- 创建：<执行者、实际时间及时区、Skill 发行版本、任务/Run 协议版本>
- 修改记录：<时间、来源、字段、影响范围；requirement/dependencies/flow/execution policy 变更必须回 draft；未完成 Run 禁止定义编辑>
- 修订记录：<终态任务的定义修订：rev-序号、累计变更字段与逐次编辑原因、当前新定义快照、旧定义快照引用（原 Run）、原 Run 与原终态、是否已消费及消费/收尾 Run；无则写无（见公共流程第 2.2 节）>

## Ready Gate

- 放行结论：<当前通过 / 未通过；时间与执行者；复核失败回 draft>
- Gate 历史：<追加各次放行、失败及定义变更使 Gate 失效的记录，不覆盖旧事实>
- 逐条结论（目标明确 / 范围明确 / 验收条件明确 / 无必须人类决定的问题 / 必要输入完整 / 依赖满足 / Cohestra 起始阶段明确 / 执行流程明确）：<逐条写结论与依据；未通过列缺口与补足建议>

## 运行记录

- 所属 Run：<run-id 或未入队>
- 历史 Run：<追加原 Run 引用及各轮结果，不覆盖旧结论>
- 恢复记录：<本次显式选择、来源 Run、解除依据与新 Run 引用；无则写无>
- 修订重启记录：<rev-序号、重启起点（新 flow 首项或原待调用阶段）、原因解除依据、新 Run 与旧终态引用；无则写无>
- 最后完成阶段：<最后交付的 Cohestra 阶段名、stage_result.status、round，或未执行；完整调用前记录与同步核对见 Run checkpoint>
- 当前候选：<cohestra_task 中的候选引用，不复制正文>
- 最近结构化状态：<task 的 status / stage_result / next / acceptance / blocked 的短摘要及来源文件（任务 README YAML Front Matter）>
- verify 处置：<unattended 跳过及理由 / 已执行 / 待人工>
- 状态结论：<blocked / failed 的原因与恢复条件；显式 run 恢复进入新 Run，resume 不重开终态>
- 下一步：<动作、前提、负责人或待指派>

Task 状态只由 Cadra 写入，Cohestra 不回写；状态变化即时落盘，作为中断恢复的依据之一，完整执行进度以 Run 文件的 checkpoint 为准。

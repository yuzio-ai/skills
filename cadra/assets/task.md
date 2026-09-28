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
- 创建：<执行者、实际时间及时区、Skill 发行版本、任务/Run 协议版本>
- 修改记录：<时间、修改来源、字段、影响范围；重大变更注明是否回 draft 重新 Ready Gate>

## Ready Gate

- 放行结论：<通过 / 未通过；通过记时间与执行者>
- 逐条结论（目标明确 / 范围明确 / 验收条件明确 / 无必须人类决定的问题 / 必要输入完整 / 依赖满足 / Cohestra 起始阶段明确 / 执行流程明确）：<逐条写结论与依据；未通过列缺口与补足建议>

## 运行记录

- 所属 Run：<run-id 或未入队>
- 最后完成阶段：<Cohestra 阶段名或未执行>
- 当前候选：<cohestra_task 中的候选引用，不复制正文>
- 最近结构化状态：<stage_result / next / blocked 的短摘要及来源文件>
- 状态结论：<blocked / failed 时写原因与恢复条件；resume 核对后补记>
- 下一步：<动作、前提、负责人或待指派>

Task 状态只由 Cadra 写入，Cohestra 不回写；状态变化即时落盘，作为中断恢复的依据之一，完整执行进度以 Run 文件的 checkpoint 为准。

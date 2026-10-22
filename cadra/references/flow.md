# Flow：起点与允许范围

flow 接受 preset 名或非空阶段列表。列表首项为 `start`，所有项去重后构成 `allowed`；后续项没有执行顺序语义。仅接受 need、design、code、review、fix、validate，不接受空列表或未知阶段。存储保留 preset 或规范化后的列表，不另外保存一份可漂移的展开结果。

| preset | start | allowed |
|---|---|---|
| full（缺省） | need | need, design, code, review, fix, validate |
| feature | design | design, code, review, fix, validate |
| small-change | code | code, review, fix, validate |
| bugfix | fix | fix, review, validate |
| review-only | review | review |

例如 `[review, fix, review]` 规范化为 `[review, fix]`；`[code, validate, review, fix]` 与 small-change 的起点和允许范围相同。preset 与等价列表必须得到相同判定。只有 start 与 allowed 均不变的排列或重复写法变化不使 Gate 失效；首项改变使 start 改变时，须按规范化 flow 变更重新 Gate，已入 Run 的任务建立修订并按新起点重启。

首次启动及改变 requirement/flow 的修订重启从 start 调用一次；其他入口的起点见 [恢复](recovery.md) 与 [修订](revision-rules.md)。后续仅按合法 `next.allowed`、`next.stage` 与 allowed 决定动作，不机械遍历列表。允许重复进入同一阶段，包括复审与补证，次数由 [预算](contract.md#调用预算) 约束。

末项不声明终点。正常 next 超出 allowed 时按 [终态映射](contract.md#终态映射) 收尾；必做后续超出范围则 blocked。是否要求 validate 结论以 allowed 是否含 validate 判定，不依赖 Cohestra 对话里的终点声明。阶段业务规则仍由 Cohestra 定义。

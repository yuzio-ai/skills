# Flow：起点与允许范围

flow 接受 preset 名或非空阶段列表。列表首项为 `start`，所有项去重后构成 `allowed`；后续项没有执行顺序语义。新版仅接受 code、review、fix、validate，不接受空列表或未知阶段。存储保留 preset 或规范化后的列表，不另外保存可漂移的展开结果。

| preset | start | allowed |
|---|---|---|
| implementation（缺省） | code | code, review, fix, validate |
| bugfix | fix | fix, review, validate |
| review-only | review | review |

例如 `[review, fix, review]` 规范化为 `[review, fix]`；`[code, validate, review, fix]` 与 implementation 的起点和允许范围相同。preset 与等价列表必须得到相同判定。只有 start 与 allowed 均不变的排列或重复写法变化不使 Gate 失效；首项改变时按规范化 flow 变更重新 Gate，已入 Run 的任务建立修订并按新起点重启。

need/design 在 Cadra 外由人工参与准备。已有确认继续有效，不重复索要确认，也不为小任务补造阶段文档。尚需定位的问题用 implementation；已有明确缺陷与整改依据时用 bugfix。历史配置仅按 [版本边界](compatibility.md) 读取，不作为新版入口别名。

首次启动及改变 requirement/flow 的修订重启从 start 调用一次；其他入口的起点见 [恢复](recovery.md) 与 [修订](revision-rules.md)。后续仅按合法 `next.allowed`、`next.stage` 与 allowed 决定动作，不机械遍历列表。允许重复进入同一阶段，包括复审与补证，次数由 [预算](contract.md#调用预算) 约束。

Cadra 向 Cohestra 明确传递本任务独立评审安排：实施后必须 review，fix 后必须复审；无必做整改且覆盖齐备后才进入 validate。显式列表不能免除这些要求，缺必要 review 范围时受阻。review-only 不自动修复。

末项不声明终点。正常 next 超出 allowed 时按 [终态映射](contract.md#终态映射) 收尾；必做后续超出范围则 blocked。next 指向 need/design 一律 blocked 并交回人工，不能按正常范围边界收尾。是否要求 validate 结论以 allowed 是否含 validate 判定。Cohestra 单独调用的阶段范围与授权规则保持不变。

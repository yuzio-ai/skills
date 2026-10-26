# Flow 配置

flow 接受 preset 名或非空阶段列表。列表首项为 start，所有项去重后构成 allowed；后续项没有执行顺序语义，末项不声明终点。新版仅接受 code、review、fix、validate，拒绝空列表、未知阶段和错误类型。存储保留 preset 或规范化列表，不另存展开结果。

| preset | start | allowed |
|---|---|---|
| implementation（缺省） | code | code, review, fix, validate |
| bugfix | fix | fix, review, validate |
| review-only | review | review |

例如 `[review, fix, review]` 规范化为 `[review, fix]`；`[code, validate, review, fix]` 与 implementation 的起点和允许集合相同。preset 与等价列表同判定。只有 start 与 allowed 均不变的排列或重复写法变化才等价；首项改变属于定义变更，修订和 Gate 失效按 [任务定义](task-definition.md) 处理。

need/design 在 Cadra 外由人工参与准备。已有确认继续有效，不重复索要确认，不为小任务补造阶段文档。尚需定位的问题用 implementation；已有明确缺陷与整改依据时用 bugfix。历史配置仅按 [版本边界](compatibility.md) 读取，不作为新版别名。

add 只校验配置；后续阶段、必要独立评审与范围边界见 [Flow 执行](flow.md)，在 ready 核对首动作或实际执行时读取。

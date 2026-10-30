# Flow 配置

flow 接受 preset 名或非空阶段列表。列表首项为 start，所有项去重后构成 allowed；后续项没有执行顺序语义，末项不声明终点。仅接受 code、review、fix、validate，拒绝空列表、未知阶段和错误类型。存储保留 preset 或规范化列表，不另存展开结果。

| preset | start | allowed |
|---|---|---|
| code（缺省） | code | code, review, fix, validate |
| fix | fix | fix, review, validate |
| review | review | review, fix, validate |

code 表示执行已明确的工程变更，包含功能开发、重构、清理及删除；清理后的 review 核对误删、漏删、引用破坏与行为回归。fix 用于已有明确缺陷与修复依据的任务。review 用于已有固定候选、需要评审并完成必要整改与验证的任务。明确只评审、不修改时用 `[review]`，不创建闲置 worker；发现必做整改时受阻并报告问题，不扩大授权。

例如 `[review, fix, review]` 规范化为 `[review, fix]`；`[code, validate, review, fix]` 与 code preset 的起点和允许集合相同。preset 与等价列表同判定。只有 start 与 allowed 均不变的排列或重复写法变化才等价；首项改变属于定义变更，修订和 Gate 失效按 [任务定义](task-definition.md) 处理。

Task/Run 仅使用协议 `0.11`。旧预设 implementation、bugfix、review-only 以及 full、feature、small-change 均不是别名，拒绝保存与执行。need/design 在 Cadra 外由人工参与准备；已有确认继续有效，不重复索要确认，不为小任务补造阶段文档。仍缺定位依据时先在 code 范围核对，不能凭空认定具备 fix 输入；需要新的产品或工程决定时交回人工准备。

add 只校验配置；后续阶段、必要独立评审与范围边界见 [Flow 执行](flow.md)，在 ready 核对首动作或实际执行时读取。

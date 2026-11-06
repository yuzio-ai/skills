# 单独 review 独立审查实测

本文件保留首轮验证事实；后续新增覆盖与完整汇总见[完整验证](2026-11-06-standalone-review-full.md)。

- 日期：2026-11-06（Asia/Shanghai）。
- 被测版本：Cohestra 0.18.0 未提交候选，协议 0.8；完整包摘要、基线和包差异见[证据记录](2026-11-06-standalone-review.json)。
- 输入由[夹具](../review_fixture.py)建立在临时目录。它只生成原始需求、固定 Git 候选和请求，不生成审查结论或阶段交付。
- 调用主会话：`/root/review_forward_test`；独立 reviewer：`/root/review_forward_test/default_reviewer`，通过 `fork_turns=none` 创建。身份来源包含实际创建返回值与会话列表观察，不仅依据 reviewer 自述。

## 结果

| 场景 | 实际执行 | 结果 |
|---|---|---|
| 单独 review 默认调用 | 主会话完成最小初始化，派发独立 reviewer；reviewer 未再次委派 | 找到纯空白名称未回退的 R1 必做缺陷；6 个函数用例中 2 个失败；发布 review-01，建议 fix 后停止 |
| 子智能体受限 | 请求明确声明环境禁止子智能体，且不是自审例外；主会话只核对前提 | 发布 review blocked，reason=dependency_unavailable，next.allowed=false；未执行自审或创建 reviewer |
| 用户明确不委派 | 主会话按本次指令自审并标明非独立审查 | 发现 R1；同样 6 例中 2 例失败；建议 fix 后停止 |
| 修订候选复审 | 测试宿主在初审结束后准备修订候选，再显式调用 review；主会话复用原 reviewer | 6 例全通过，R1 关闭，发布 review-02；本次 review 终点完成，未声明 validate 通过 |

四次阶段交付均已完成索引发布及回读。主验证会话另行解析最终索引、检查 Git 状态和交付目录：

- 三个项目的业务工作区均 clean；执行者没有修改业务候选，未生成 fix 或 validate 交付。
- 初审候选为 `b6818f9d6b081efae96a50c9e567e94ff379fbf9`；复审候选为 `96bde153d658d2098609db1ed2f30638e95b5c09`。受控修改由测试宿主 `/root` 完成，只涉及 names.py，不冒充执行者自行整改或补造 fix 历史。
- 原 review-01 内容摘要在复审后保持不变；review-02 对应新候选，blocking=0。
- 冻结技能包的 26 个文件与本次源包逐文件摘要一致。

## 自动检查与版本判断

`python3 -B -m unittest discover -s tests -p 'test_*.py'`：505 项通过，无跳过。包括新增 4 项夹具检查、包资源检查与完整 Git 历史版本检查。夹具单测检查输入、真实缺陷与隔离，不模拟 agent 决策；上表来自独立真实会话。

skill-creator 的 quick_validate 校验通过；默认 Python 缺 PyYAML，使用临时 uv 环境提供依赖后执行成功，未增加技能运行依赖。`git diff --check` 通过。

此次改变单独 review 的默认执行流程，包版本由 0.17.0 升为 0.18.0。Front Matter 字段、枚举和状态语义保持不变，协议仍为 0.8。Cadra 已绑定 reviewer 的阶段直接执行，不重复委派；消费契约无需修改，Cadra 不升级。

## 限制

- 子智能体受限场景是请求声明的受控环境条件，不是实际调用工具后遭拒绝的记录。
- 未实测自动选择 review、reviewer 身份缺失、工具中断、并发索引冲突、发布失败或原 reviewer 不可复用路径；这些场景保留在[验收清单](../scenarios.md)。本次没有重新运行 Cadra 或 closeout 的真实会话。
- 验证使用临时冻结包；没有更新真实用户安装、提交、推送或发布技能包。

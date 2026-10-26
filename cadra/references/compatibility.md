# 协议 0.8 与历史记录

按准确版本识别，不按大小推定兼容。Cohestra 仍消费契约 0.8；Cadra 0.8 改变可执行流程、队列追加、角色绑定与恢复语义。历史 0.6/0.7 Task/Run 只读，不把改版本号当作迁移。

- 0.6/0.7 Task/Run 按各自原语义只读解析与 list/report 展示；0.6 缺 executor 时活性记 unknown，不补造。历史 full、feature、small-change 保持原意，不用新版默认值重解释。来源链可以引用已核实的旧版闭合 Run。
- 未完成旧 Run 不由 0.8 resume、收尾、追加或更新；交由与其协议匹配的旧版继续。不得为升级打断运行、转换快照、初始化或建立替代 Run。
- 旧 completed/stopped 必须逐项终态、result.state 一致且 slug 唯一，缺结果不放行新 Run。0.6 支持历史 block YAML（列表缩进为 0 或 2 空格、result 为块映射）和 JSON；0.7 使用原 JSON 头部。重复字段、未知协议或无法识别的形式保守拒绝，不改原 status。基础闭合检查不能替代完整来源链核验。
- 旧 report 只读输出，不新增报告文件或登记链接。0.8 report 按当前规则写报告和追加链接。
- 旧 Task 的 add/ready/run/append 先说明版本边界；只有用户明确要求升级指定 Task，且项目无未完成 Run 时，才执行下述迁移。不把一般 run 或技能安装当迁移授权。

## 显式 Task 升级

add 重读旧 Task 和完整来源链，按其确切 0.6 或 0.7 协议核对定义与准入字段。将原字节备份至 `.yuzio/cadra/tasks/history/<slug>-protocol-<原协议>-<sha256>.md`；同名已存在必须字节一致。history 不参与 Task 扫描。记录备份路径、SHA-256、时间及授权来源，核对成功后才能更新当前 Task。

将 Task.protocol 改为 0.8、preparation 改为 draft，追加迁移依据和 Gate 失效记录。协议迁移本身不增加业务 revision，不改 slug、绑定或历史 Run。后续 ready 必须重新核对；新 Run 的 previous_run 可引用旧闭合链尾。迁移不重开已完成任务，终态展示不被 draft 覆盖。

配置处理：

- 历史 small-change 必须经用户明确选择改为 implementation，不保留别名。两者规范化起点和允许集合相同，仅名称替换不增加业务 revision、不将 flow 计为业务 changed_fields；协议升级仍使 Gate 失效。
- 历史 full/feature 或含 need/design 的列表在新版不可执行；保留原历史含义，要求用户明确选择新的合法 flow。起点或允许集合发生变化时按 [修订规则](revision-rules.md) 分代，不能只改名称伪装等价迁移。
- bugfix、review-only 或新版合法列表可保留原值；其他业务修改仍按原修订规则处理。没有明确新配置时停止升级，先报告需要决定的字段，不留下伪装可执行的 0.8 Task。

本包没有批量迁移器。由 add 执行者按共同原子写入和回读规则操作；无法核对原 YAML、来源或安全备份时停止。项目 README 只追加新版本采用边界，不重写初始化版本。旧 Run、定义快照和历史验收始终不变。

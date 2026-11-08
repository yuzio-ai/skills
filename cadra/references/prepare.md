# Task 准备入口

add／ready 必须使用安装包的 [prepare.py](../scripts/prepare.py)。禁止临时编写 Task／Run 解析器、直接写 Task，或用 list 的旧版只读结果作为写入依据。脚本校验协议、归属、可达依赖、指纹与写入。调用者负责依据本入口规则整理定义、核实授权和交付、判定 Ready Gate。

普通路径按三批执行。每批合并独立工作，允许在一次工具调用内运行多个依序依赖的命令。临时 JSON 和提案放在本次调用的临时目录，重定向中间输出。三批之间复用已读资料。只在具体缺口、冲突、必要输入变化或条件路径触发时增加定向批次。锁冲突时保留现场，重读受影响的状态再决定是否重试。

1. **读取。** 合并读取本入口规则、适用项目规则和目标摘要。项目及 slug 已知时，同批运行 `inspect --project <已解析的绝对路径> --slug <slug> --entry <add|ready>`，把 JSON 保存为 inspection。add 显式更新直接依赖时，传 `--dependencies '<JSON 数组>'`，清空用 `[]`。目标 Task 的 `task.data` 和 `task.body` 已分开解析，可直接用于生成提案。其余输出仅看相关归属／依赖和同名交付摘要。发现旧协议停止，按版本边界处理。
2. **取证。** add 归档必要附件并核验来源、副本和可读性。ready 仅做本项已有依据和必要的项目只读预检。合并执行 `check --inspection <inspection>`，按需附 `--inputs <JSON>` 和 `--attachments <JSON>`，保存结果为 checked。inputs 是业务文件路径 → 本项具体用途，禁止目录或按写入范围批量展开。attachments 是该 Task 已留存的项目相对路径 → 已记录／已核验 SHA-256，有声明的附件必须完整提供。用 `business` 生成通过时的 ready_scope.inputs。`attachment_issues` 逐项处理，仍缺失的必要附件只允许记为未通过。若命令检查和取指纹的输入可能变化，先固定实际受检的清单和摘要，再核对检查适用于这些字节。
3. **发布。** 同一批整理完整 Task 提案并运行 `publish --checked <checked> --proposal <Task Markdown>`。脚本共用 Run 写锁，在锁内重新确认定义、归属、依赖、同名交付和已列出输入，再原子发布并回读。锁内输入复核只比较状态及摘要，无变化时不重跑预检命令。只在回读成功后报告新状态。

以 `python3 -B <安装目录>/scripts/prepare.py` 执行。[共用 Task 读取器](../scripts/task_records.py)用 Ruby/Psych 批量读取 YAML，直接读取 JSON Front Matter。缺容器按本机容器规则补齐。不据此补造缺失的历史 Task。已有交付、修订重启和受限确认交接按本入口指定条件处理，交接变更后以新材料重新取证。准备入口不调用项目命令或 Cohestra，不写 Run。

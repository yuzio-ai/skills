# 数据与调用

## 采集与复用

先按 [存储约定](storage.md) 检查目标忽略规则。脚本从实际技能绝对路径调用；技能源仓库不是默认报告目录。

```sh
python3 /path/to/relatra/scripts/relatra.py configure --output /reports/.yuzio/relatra --project /work/a --project /work/b
python3 /path/to/relatra/scripts/relatra.py collect --config /reports/.yuzio/relatra/config.json --period weekly
python3 /path/to/relatra/scripts/relatra.py report --snapshot /reports/.yuzio/relatra/snapshots/SNAPSHOT
```

configure 不覆盖已有配置，修改需 `--replace`。默认来源为 `${CODEX_HOME:-~/.codex}/sessions` 和 `archived_sessions`，可重复 `--source-root`。输出不能与来源目录重叠或位于业务 `.yuzio/cadra`、`.yuzio/cohestra`。

collect 支持 daily/weekly/monthly/quarterly/yearly；`--date YYYY-MM-DD` 取包含该日的自然周期；`--start YYYY-MM-DD --end YYYY-MM-DD` 为自定义范围，end 包含当天。`--now RFC3339` 固定复算截止；当前周期裁剪到 now。

`--analysis basic|deep` 默认 basic。模式写入 facts 和账本；report 不另选模式。需要从普通切换深度时重新 collect，可复用原来的目标判断。

默认在当前输出目录的 `reports/*/*` 选择可复用报告；`--previous-report PATH` 显式指定。项目、来源集合、时区、技能和数据版本必须一致，前版截止不得晚于本次截止；优先最新截止，同截止取最新生成时间。自动发现遇坏报告时保留提示并跳过，显式指定不适用报告则报错。复用与比较基线互不替代。

每次 collect 保存 `snapshots/<版本>/facts.json`、`tasks.json`、`manifest.json`。manifest 保存 facts 哈希、前版路径及 review_queue，并在命令结果返回。facts 捕获日志的固定字节前缀，保留来源哈希、时间、证据引用及读取缺口；不可手改。

复用完整账本，检查任务引用及证据内容是否仍有效。新增、移除或变化的关联轮次，以及最新修订的未闭合目标进入 review_queue；已知轮次消失另记覆盖缺口。失配任务保留 id/目标，清空无效起点、事件与成果声明，设 `review_required: true` 并记录限制；原判断仍在前版。复核后恢复完整历史、移除该标记与已解决限制。没有依据则保持待确认，不能猜首次交付时间。

新候选仅取本期未归属活动；同聊天的新轮次仍需判断是否属于旧目标。facts 保留截止前历史，供追溯起点、首次交付和跨聊天归并。首次无前版时不遍历审定所有旧聊天，明确保留“未全面盘点更早遗留目标”的限制，后续复用也不撤销此覆盖限制。当前优化不裁剪原始日志扫描，不建立索引或数据库。

## 任务账本

agent 整理 tasks.json，不让用户手工填表。示例中的引用替换为本次 facts 中的实际 id：

```json
{
  "schema_version": 2, "analysis": "basic", "process_reviewed": false,
  "tasks": [{
    "id": "a/navigation", "revision": 1, "project": "/work/a",
    "title": "统一导航点击范围", "type": "implementation",
    "goal": "标题与留白均可点击", "outcome": "三个入口改为整行导航",
    "started_at": null, "turn_ids": ["TURN-ID"],
    "events": [{"id":"delivery-1", "kind":"delivered",
      "at":"2026-10-05T09:20:00+08:00", "evidence":["EVIDENCE-ID"],
      "basis":"static", "verified_excerpt":"三个入口均使用整行导航",
      "note":"静态核对通过，运行时验收未完成"}],
    "limitations": ["没有运行时验收"], "next_step": "补运行时验证"
  }],
  "excluded_turns": [{"turn_id":"REPORT-TURN", "reason":"Relatra 报告生成"}],
  "summary": "本期主要成果及限制", "recommendations": []
}
```

任务 type：implementation/fix/review/design/documentation/research/operations/consultation/other。id 标识独立目标，revision 仅用于实质范围变化，同一键仅一行。跨项目目标选一个主项目；共享 turn 不按字数分摊资源。

已知 started_at 必须提供 start_evidence 和 start_note，证明真实目标起点；未知为 null，不用首条日志代替。goal/outcome/limitations/next_step 可省。outcome 整理截止时的实际变化与当前结论，limitations 保留当前仍适用的限制；已解决的限制不留在当前视图，历史事件和原证据不改写。next_step 只保留未闭合行动，即使已交付或验收也不能隐藏，已由其他目标完成时清空；语义重复行动由 agent 核实并只留一个主要归属目标，仅指向其他目标的说明不作待办。limitations 不自动产生待办。

事件必须有唯一 id、kind、at（带时区 ISO 或 null）、非空 evidence 列表和 note。时间不得超出截止或早于已知起点；未定日期 workflow 不能单独确定事件日期，关联 dated turn 也必须确实定位该事件，不能随便引用旧消息。current_only README 不作历史证明。

交付/验收/验证需 basis：static/build/runtime/user_acceptance/other/artifact/answer。实现交付需 tool_result 或有效 workflow；工具引用需核读 locations 指向的实际源行，在 verified_excerpt 保存去敏摘录。源行不可读或截断时保持待确认。user_acceptance 需明确用户认可；工具中的答复也需核对摘录。answer 仅可证明咨询、审查、设计、文档、研究的实际答案交付，不能证明实现或验收。脚本验证结构、引用与时间，语义及验收条件由 agent 核实。

建议最多三条，形状为 `{"text":"建议", "task_ids":["目标id"], "evidence":["证据id"]}`，须来自相关任务的真实问题；所引任务未出现在本期报告时不展示。summary/recommendations 先写到账本，report 才是最终产物生成入口。summary 按 [报告写作](reporting.md) 整理为带标题和任务明细链接的重点摘要，字段仍为字符串；recommendations 的完整引证列在明细，关键判断可归纳进摘要，不重复堆入正文。

## 更正

复制原报告 tasks.json 到新的工作文件，直接修改完整账本，再生成新版本：

```sh
python3 /path/to/relatra/scripts/relatra.py report --snapshot /reports/.yuzio/relatra/reports/PERIOD/VERSION --tasks /tmp/revised-tasks.json --revises /reports/.yuzio/relatra/reports/PERIOD/VERSION --reason '用户确认目标归并有误'
```

`--revises` 与非空 `--reason` 必须成对提供；父版本须通过哈希校验，与当前项目/来源/时区/版本及周期一致，当前截止不得更早。同 facts 可直接复用原报告；需新证据时重新 collect 后指定新 snapshot。删除、拆分和归并直接编辑 tasks，不改变其他目标的 id；修正错误不增加范围修订号。明确排除的业务活动需写 excluded_turns，不能仅删除任务后让它下次再次成为候选。

新报告保存重点正文 report.md、完整可读明细 details.md、statistics.json、完整 tasks.json、facts.json 和 manifest.json。正文、明细及统计来自同一账本；任务明细锚点按 id/revision 稳定生成。命令参数与返回 JSON 字段不变，明细位于返回的 report 路径同目录。manifest 记录输入哈希、前版、比较基线、被更正版本及原因。没有独立 patch 文件或重放链，旧报告及源日志不变。

## 比较、格式与来源限制

report 的 `--baseline PATH` 明确指定前期报告，校验其哈希并从基础输入重算。比较规则见 [统计口径](metrics.md#比较与覆盖)。没有基线不输出空比较章节。

0.3.0 沿用 schema v2；本次仅调整阅读结构，不改变采集、状态、统计及 JSON 字段语义。旧报告保留原样，不补写 details.md。沿用既有同版本范围核对和格式检查，不新增跨包版本复用或自动迁移承诺；不适用的旧输入需重新 configure/collect。`correct` 和 `--correction` 已移除。不要手工修改 schema 或重签哈希伪造兼容。

本地适配器识别 session_meta、turn_context、生命周期、token_count、token_usage_record 及消息/工具结果引用。只保存用户、assistant final 和实际用户输入工具答复引用；不导入思考、系统指令或账户元数据，harness 注入仍需 agent 识别。工具原输出仅存哈希与源行，不复制任意原文。

只读 `.yuzio/cadra/runs/*.md`、`.yuzio/cohestra/handoffs/**/*.md`；按时间/建立/最近更新字段中的带时区 ISO 取最后声明时间，截止后文件不导入。其他日期格式不猜，不扫描业务源码。未知日志格式、缺稳定 id、未来 payload 时间及不可读来源保留缺口，不用文件名、mtime 或当前状态填历史。桌面只读工具仅补上下文，不证明历史完整；不启动 app-server、不采集远程历史、不写 Codex 内部数据库。

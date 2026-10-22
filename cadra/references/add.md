# add

创建或编辑任务。读 [公共流程](workflow.md)、[Task 规则](task-rules.md)、[Flow](flow.md)；编辑已入过 Run 的定义时读 [修订规则](revision-rules.md)，绑定已有交付时读 [契约前置检查](contract.md#前置检查与首个动作)。

```text
$cadra add
任务：<title；编辑时给现有 slug>
需求：<目标、范围、排除项、验收条件>
优先级：<high / medium / low；缺省 medium>
依赖：<已存在 slug 列表；可空>
流程：<preset 或阶段列表；缺省 full>
执行策略：<stop_queue_on_failure: true/false；缺省 false>
```

1. 固定目标与 slug，解析 Run 归属；未完成 Run 涉及的任务拒绝编辑。
2. 校验定义、依赖与 flow，只修改用户明确指定的字段。缺少业务信息记录为缺口，不编造。
3. 按 [Task 模板](../assets/task.md) 新建或更新任务，维护修订与 Gate 失效记录；已有 Cohestra 交付记录绑定主题及确认依据。
4. 原子保存 Task 并回读，报告 preparation 和缺口，推荐 `$cadra ready` 加 slug。

不执行阶段、不建立 Run。只改本 Task 与必要容器/忽略规则。

# 可选项目配置

仅在项目已有或明确引用 profile，或确需建立可复用配置时读取。配置格式沿用 profile_version 1。


位置：目标项目的 `.yuzio/vistra/profile.yaml`。只有已有入口不足且需要持久配置时，在任务授权范围内建立；不作为执行门槛。示例：[project-profile.example.yaml](../assets/project-profile.example.yaml)。示例中的项目、路径均为虚构，不自动复制为有效配置。

| 字段 | 形状与含义 |
|---|---|
| `profile_version` | 整数 `1`；不认识的版本报告缺口，不强行按旧版解释 |
| `project` | 稳定名称或标识 |
| `sources` | 角色到引用列表的映射 |
| `domains` | `mobile` / `desktop` / `brand` 到补充 `sources`、`defaults` 的映射 |
| `targets` | 对象标识到 `domains`、`purpose`、`surface`、`sources`、`defaults` 的映射 |
| `imports` | Skill 引用列表；每项有 `source`、`scope`、`role`，可用 `modes`、`domains` 限定适用范围 |
| `defaults` | 可覆盖的 `locale`、`appearance`、`output_directory`、`budget` |

`sources` 角色：`canonical`、`design`、`brand`、`tokens`、`components`、`page_overlay`、`adapter`、`policies`、`assets`、`mock_data`。`scope` 为 `user` 或 `project`；`source` 可为文件、链接或宿主暴露的 Skill 标识，必须解析到可读取内容后才能采用。

`budget` 使用 `variants`（正整数方向数）、`refinement_rounds`（非负整数上限），可选 `images`（非负整数图片上限）。这些是默认值，不是外发、运行或写入授权。零图片预算保留文字交付，承诺的视觉部分仍未完成。无效类型或矛盾值不能静默当成有效预算；继续不依赖该值的工作。

## 合并与路径

1. 项目、领域、目标的 `sources` 合并去重，不丢弃仍然适用的依据；实际冲突按资料职责处理。
2. 默认值逐字段按当前要求 → 调用方已确定值 → 目标默认 → 领域默认 → 项目默认 → Vistra 默认解析。未设置字段继续回退，显式零值不视为缺失。跨领域相互冲突的同一参数需要解决，不以最后读取者取胜。
3. `imports` 的范围限定加载；排除项或不可读来源在报告中说明。未知字段记录为未采用，不解释为权限。
4. profile 内相对路径，包括 `output_directory`，相对目标项目根目录；包内引用相对实际加载的包文件。链接、绝对路径保留其明确位置。跨仓库引用使用明确入口，不猜固定机器路径。
5. `null` 为未知或未设置，空列表为未声明来源；都不证明没有约束或已获授权。记录缺失、冲突及实际回退，不为非关键缺项停止全部工作。

Vistra 默认值见 [入口](../SKILL.md#共享预算与默认值)。

profile 不保存选择、授权布尔值、当前截图或旧运行状态；即使旧文件存在这些数据，也不能作为本轮依据。建立或修改配置前读取 [存储约定](storage.md)。

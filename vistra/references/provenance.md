# 开发来源与改写记录

仅在来源核查、升级或维护时读取；日常执行不加载，也不读取上游。运行无 Taste 依赖。升级需比较固定提交差异并回归对应场景，不能整体覆盖定制方法。许可见 [LICENSE](../LICENSE)。

## mobile

对应规则：[mobile](domains/mobile.md)。

定制自 Taste [imagegen-frontend-mobile](https://github.com/Leonxlnx/taste-skill/blob/f624f37a8c650b9cc550253104925efe4c8de246/skills/imagegen-frontend-mobile/SKILL.md)。仓库 `Leonxlnx/taste-skill`，提交 `f624f37a8c650b9cc550253104925efe4c8de246`，读取日期 2026-10-17；源文件 SHA-256 `8a33389979f3074fa0926678e266ad2eb9234624472254469fc1ad916b9caa24`。

采纳跨屏设计基线、层级、合理页面关系与实际查看后的修订。将默认设备框改为内容区评估；删除无界增屏/重生成、固定纹理偏好与图标禁令；平台差异改由项目提供，数量、模式与交接统一采用 Vistra 契约。运行不读取上游；升级须比较固定提交差异并回归相关场景，不能直接覆盖本文件。版权许可见 [LICENSE](../LICENSE)。

## desktop

对应规则：[desktop](domains/desktop.md)。

定制自 Taste [imagegen-frontend-web](https://github.com/Leonxlnx/taste-skill/blob/f624f37a8c650b9cc550253104925efe4c8de246/skills/imagegen-frontend-web/SKILL.md)。仓库 `Leonxlnx/taste-skill`，提交 `f624f37a8c650b9cc550253104925efe4c8de246`，读取日期 2026-10-17；源文件 SHA-256 `6b5c2256522fdba1e3313eafa3d743b960a7b13ec029d3e6586e04b23327c1f8`。

采纳构图变化、内容叙事、跨区域视觉连续性和自检。去掉营销默认、强制逐区块横图及固定图片/装饰数量；新增产品工具、内容、紧凑面板和键盘窗口语境。按 Vistra 预算、证据和项目权威执行。运行不读取上游；更新比较固定提交差异并回归相关用途，不整体替换定制内容。版权许可见 [LICENSE](../LICENSE)。

营销内容论证补充参考 Taste [gpt-tasteskill](https://github.com/Leonxlnx/taste-skill/blob/f6831c5df8ad546c2567535442f1691a823868e3/skills/gpt-tasteskill/SKILL.md)。仓库 `Leonxlnx/taste-skill`，提交 `f6831c5df8ad546c2567535442f1691a823868e3`，读取日期 2026-10-19；源文件 SHA-256 `7d630a777b980971521c4a7619a631aa67dd6f713592e57c12473a8caa505238`。采纳主张到行动的内容检查，将 AIDA 限定为营销场景的可选框架，去掉强制结构、动效和视觉风格。

## brand

对应规则：[brand](domains/brand.md)。

定制自 Taste [brandkit](https://github.com/Leonxlnx/taste-skill/blob/f624f37a8c650b9cc550253104925efe4c8de246/skills/brandkit/SKILL.md)。仓库 `Leonxlnx/taste-skill`，提交 `f624f37a8c650b9cc550253104925efe4c8de246`，读取日期 2026-10-17；源文件 SHA-256 `9584a127e535c90b686c8dcb5a707ede586dac6791fbf92cfd118c5fea96f9a0`。

采纳身份意图识别、已有品牌保留、概念与元素关系、跨载体一致性及画布适配。将默认概念板、少文字和风格预设改为按范围选择，补充单项任务、明确参数、字体与母版缺口及跨领域候选绑定。运行不依赖 Taste；升级只在差异评审及相关场景回归后吸收。版权许可见 [LICENSE](../LICENSE)。

## review

对应规则：[review](modes/review.md)。

参考 Taste [redesign-skill](https://github.com/Leonxlnx/taste-skill/blob/f624f37a8c650b9cc550253104925efe4c8de246/skills/redesign-skill/SKILL.md)。仓库 `Leonxlnx/taste-skill`，提交 `f624f37a8c650b9cc550253104925efe4c8de246`，读取日期 2026-10-18；源文件 SHA-256 `a75d547d04595fe97a5d377dddf145d029d51487a4f2a0a5a9d3b532ca3b84cd`。

采纳排版、布局、状态、导航、图标及内容的分项审查，改为按范围与证据选择。去掉直接修复、固定修复顺序、字体/图标/配色禁令、默认装饰与动效升级，以及为逼真而改写数据的要求。运行不读取上游；更新须经差异评审与相关场景回归。许可见 [LICENSE](../LICENSE)。

补充参考 Taste [gpt-tasteskill](https://github.com/Leonxlnx/taste-skill/blob/f6831c5df8ad546c2567535442f1691a823868e3/skills/gpt-tasteskill/SKILL.md)。仓库 `Leonxlnx/taste-skill`，提交 `f6831c5df8ad546c2567535442f1691a823868e3`，读取日期 2026-10-19；源文件 SHA-256 `7d630a777b980971521c4a7619a631aa67dd6f713592e57c12473a8caa505238`。

采纳减少动态效果后的内容完整性、网格空洞、标题构图、文字辨识与标签用途检查；改为按条件选择，区分有意留白、功能标签及未检查条件。去掉模拟随机输出、统一标题行数、强制动效及工具依赖、固定风格禁令和统一裁切方案，不增加生成前固定输出块或自动运行要求。

## handoff

对应规则：[handoff](modes/handoff.md)。

以下来源均为仓库 `Leonxlnx/taste-skill`、提交 `f624f37a8c650b9cc550253104925efe4c8de246`，读取日期 2026-10-18：

- [image-to-code-skill](https://github.com/Leonxlnx/taste-skill/blob/f624f37a8c650b9cc550253104925efe4c8de246/skills/image-to-code-skill/SKILL.md)，源文件 SHA-256 `4c060a8064a8b13380bc2ef3d6e6a1d0b1e316aa093cd9807d0ce9e4eeb037fa`。采纳对布局、排版、间距、组件、颜色与媒介的细项分析及防漂移方法；去掉生成图最高权威、强制逐区块出图、无限补图和直接实现，参数准确性受 Vistra 证据约束。
- [stitch-skill](https://github.com/Leonxlnx/taste-skill/blob/f624f37a8c650b9cc550253104925efe4c8de246/skills/stitch-skill/SKILL.md)，源文件 SHA-256 `46bdb08fee2dded38b6ba0a051230a502d6ac6e4044afd47592cb40c256028b5`。采纳语义名称、视觉描述、参数和功能角色的组合表达；去掉 Stitch 依赖、另建规范真源、固定风格/断点和强制持续动效。

运行不读取上游；更新须经差异评审与相关场景回归。许可见 [LICENSE](../LICENSE)。

动效回退补充参考 Taste [gpt-tasteskill](https://github.com/Leonxlnx/taste-skill/blob/f6831c5df8ad546c2567535442f1691a823868e3/skills/gpt-tasteskill/SKILL.md)。仓库 `Leonxlnx/taste-skill`，提交 `f6831c5df8ad546c2567535442f1691a823868e3`，读取日期 2026-10-19；源文件 SHA-256 `7d630a777b980971521c4a7619a631aa67dd6f713592e57c12473a8caa505238`。采纳回退后完整呈现内容的要求，改为与平台无关的交接描述，不强制动效、依赖库或运行验证，不将策略当作实现通过。

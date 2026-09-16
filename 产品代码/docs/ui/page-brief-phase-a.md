# Phase A 页面简报｜UI-00 + UI-01

## Confirmation state

- Confirmed: 五个稳定认知空间；同一 Widget 的紧凑/全屏双形态；项目总览首屏顺序；页面以判断为主；复杂修改回 Codex；一个最强主操作。
- Recommended: Phase A 只启用项目总览，后四个空间显示真实状态和前置条件，不伪造空功能。
- Needs confirmation: 无产品级待确认项。
- Needs validation: Codex 宿主实际 inline/fullscreen 尺寸、tool-result 生命周期和重挂载行为。
- Explicitly excluded: 独立 Web 应用、传统全字段编辑器、固定侧栏假设、G0 前视觉决策。

## Authority

- Product source: `../../01-产品需求基线-v1.0.md`
- Active design direction: 可信、专业、现代但克制的企业 AI 工作台。
- Design source for this direction: `../../03-UI设计与交互规范-v1.0.md`
- Alternate design directions that must not be mixed: 旧独立 Web 产品、Image 2 探索图中的未确认表面细节。
- Approved references: `prototypes/00-responsive-native-widget-exploration.png`、`prototypes/01-project-overview-ai-cognitive-map.png`。
- Constraints: MCP App iframe、360–480px 紧凑、1440×1024 全屏、业务状态来自受管项目。

## Five planes

- Strategy: 用户用最少注意力判断 AI 是否理解正确、是否在轨、现在是否需要干预。
- Scope: Phase A 读取项目总览，展示认知主线，提交一个 revision-safe 判断，并把后续意图交给 Codex。
- Structure: 项目 → 目标/听众/问题 → AI 判断 → 已确认/不确定性 → 成果/状态门 → 当前判断。
- Skeleton: 紧凑模式为单列认知线程；全屏为稳定导航 + 主认知地图 + 焦点 Inspector。
- Surface: 白/冷灰、紫色 AI、蓝色事实、绿色确认、琥珀不确定性、系统字体、无装饰性动效。

## Goal scenario

当售前人员在 Codex 中恢复一个正在制作的解决方案 PPT 项目时，他需要在几秒内确认 AI 当前理解、最大不确定性和成果状态，并处理一个关键判断。系统在不暴露内部思维链的前提下提供可追溯认知投影和 revision-safe 回写，产生可恢复的新版本；宿主不支持对话或全屏时，决定仍会保存并提供明确降级反馈。

## Page definition

- Page name: AI PPT Studio 项目总览 / AI 交付认知地图
- Core user: 制作阅读优先售前解决方案 PPT 的售前人员
- Context: Codex 对话内嵌或全屏 Native Widget
- Single mission: 判断 AI 是否在正确方向，并完成当前一个高影响选择
- Entry state: MCP render tool 带入项目快照，或重挂载后重新读取
- Completion result: 人工决定已持久化，新 revision 可被 Codex 继续执行
- P0 information: 项目、交付目标、AI 当前判断、最大不确定性、当前决定、主操作
- P1 information: 听众、问题、状态门、受影响成果、来源和版本
- P2 information: 历史决定和完整证据（后续阶段展开）
- Primary action: 提交当前判断 / 继续与 Codex 对话
- Secondary actions: 展开全屏、刷新、查看上下文、提出复杂修改
- Critical risks: 事实与推论混淆、陈旧 revision 覆盖、保存后未触发 Codex 却假装开始、紧凑视图复制完整网页
- Required states: loading、ready、saving、saved、saved-with-host-fallback、revision-conflict、error、empty decision

## Seven interaction questions

1. 顶部持续显示页面、项目和同步 revision。
2. 选项、提出修改、全屏和刷新均有文字或稳定图标语义。
3. 当前判断区只有一个视觉主按钮。
4. 单选后提交；复杂意见进入 Codex。
5. 保存中、已保存和宿主未接收分开反馈。
6. 返回新 revision、影响范围和刷新后的认知投影。
7. 冲突时保留输入并刷新；失败时可重试；历史决定不可被静默覆盖。

## Scan test

3–5 秒内识别：当前项目、交付目标、AI 当前判断、最大不确定性、提交当前判断，以及证据/上下文入口。

## Validation tasks

1. Understand the page: 说出 AI 当前交付目标和主要听众。
2. Find critical information: 找到当前最大不确定性和受影响成果。
3. Complete primary action: 选择一个选项并提交。
4. Handle an error: 用过期 revision 提交，确认没有覆盖并可刷新。
5. Confirm result: 看见新 revision 和已保存状态。
6. Cancel, undo, or recover: 提交前可改选；冲突/宿主失败保留输入并允许回到 Codex。

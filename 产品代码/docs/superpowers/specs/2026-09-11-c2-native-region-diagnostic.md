# C2 G1 前受控区域校样最小合同

状态：总控于 2026-09-11 依据用户持续制作与必要修复授权明确要求实施；归原 CHG-IL-C2、命名分支和 28a9 Worktree。总控负责将四基线同步至 v2.18 §1.10 并独审；本文件不复制或改写本 Worktree 的平行四基线。源码、独审、封包与客户校样效果分别记录，本文不表示已完成。

## 1. 问题与边界

本次三页已选图和区域输入有确切来源，部分实际字形仍需用 SDK 渲染才能判断。现有链要求全部 region review passed 后才能形成正式合同和计划，而正式 native handoff 又要求 G1 passed；当前没有在不伪造这些状态的情况下产生校样的治理入口。区域字段通过不等于真实字体墨迹或设计还原通过。

只增加受控工程校样任务，复用现有唯一 `render()` 和实际结果检查核心，用于取得独立审查证据。它不是正式 build-native-first、锚点或第二 writer，不重新设计、不改变选定图、不重开用户审批，不代替后续正常 region review → contracts/plan/G1 → 正式 build-result → 四维/PowerPoint 与用户验收。

## 2. 诊断准入

新动作暂定 `build-native-diagnostic`，沿用 `native-first-engineer` 执行角色，独立任务 ID 与 ContextPack。动作目标严格为 `[当前 selection_ref, 当前 region_inventory_ref]`，不能传任意路径或自由 handoff。支持本轮已确立的 v3 区域与原 v2 selected copy；不隐式升级旧合同。

- 要求当前 G0 passed，当前 Image-led 路线、来源、有效授权、工作选定/用户选定、完整 TargetBinding 均可重验。遵循既有 G2/G3 冻结边界；不借诊断解冻正式产线。
- 区域必须已正式登记，且与当前选择和真实图像字节/尺寸匹配。所有现有原文覆盖、角色/用途、关系、版本、几何/schema和资产校验继续执行。
- 需要同一当前区域的真实已完成独立工程审查：v3 的 visible-copy-transcription、complete-region-coverage、material-roles、source-image-derived-relations 四项必须 passed；faithful-geometry-appearance 可以是 passed 或 not-established。任何 failed、缺项、其他 not-established、伪造 reviewer、未完成任务或过期 selection/review 均拒绝。不能把 appearance failed 默认为可继续。
- 准入只允许取得外观证据，不将该项改为 passed。确切字体、显式 crop/frame 比例、路径/物理连接器能力等 renderer 前置仍有效；缺能力仍写前失败。

## 3. Runtime 派生的独立输入身份

Runtime 从正式选择、区域与独审回执派生 `image-led-native-diagnostic-input/v1`，记录 project/revision、task ID、selection/ref、region/ref、region-review/ref、来源/政策依赖以及完全原样的区域和资产投影。使用独立 artifact kind `image-led-native-diagnostic-input` 与任务专属 slot；与 ContextPack/Agent task 在同一事务建立。引用必须实际落盘可解析，不能只造 hash 字符串。

派生时复用现有确定性 region → native object 投影：只添加 object_id/render_mode，不计算新布局；文案、span、字号/字距、坐标、z_order、材料角色与所有有限外观来自已登记区域。完整素材资产按确切 ref/hash 从 Runtime 解析、解码并核对，不能任意替换或导入预裁文件。

诊断 renderer handoff 使用独立版本与目的：`handoff_version=codex-presentations-image-led-diagnostic/v1`、`compiler_version=image-led-diagnostic-compiler/v1`、`purpose=region-diagnostic`、`diagnostic_ref` 指向上述实际输入；保留 project_id、selection_ref、region_inventory_ref、task_id、slides、assets、output_paths。**没有 plan_ref，不伪造 visual-compilation-plan、正式 contract 或 G1-passed。** 输入 schema 闭合，旧正式 v1/v2/v3 的字段与版本判定保持。

同一 `render()` 显式识别诊断合同并走相同域校验、字体/图片/裁切检查、对象创建、导出、重导入和对比代码。诊断版本仅决定身份和用途，不能跳过已有字段/内容/素材检查。若需要整理公共 helper，只提取共享逻辑，不新增另一套 PPTX 实现。

## 4. 输出与结果事务

诊断输出位于真实项目根内的独立任务目录，任务 ID 必须包含于路径；父目录必须已存在且非 symlink，目录/文件必须不存在。输出名用诊断语义，不能覆盖原文件。运行失败保留失败诊断，不提交成功结果，不自动重试。

输出与正式结果使用可区分的闭合身份：purpose/diagnostic_ref 替代正式 plan_ref；状态保持 `engineering-output-unassessed`，visual_fidelity、target_powerpoint、user_acceptance 全部 not-established。输出包含真实 PPTX、handoff、mapping、inspect、authoring/reimport、逐页 PNG/layout 和对应定版图的 side-by-side/overlay/region differences。不得在内容画布加额外文案来标注状态；状态记录在结果元数据和用户说明。

新 `artifact_type=image-led-native-diagnostic-result` 仅由其确切 `build-native-diagnostic` 任务提交。Runtime 重解析任务 ContextPack 和真实诊断 input，重派生并比对当前选择、区域、准入审查和有效依赖；执行与正式结果相同的实际 OOXML/原文/样式/裁切/身份/文件 hash/重渲染检查。不能信任 Agent 自报通过或单看 PNG。输入变化、过期任务、错误目的或伪造文件均拒绝。

诊断结果只写任务专属 diagnostic artifact/head 并完成该 Agent task，不写或移除正式 build-result、anchors、current native-pptx、editability/preflight 当前头，不修改任何 Gate。正式结果 intake 与 anchor promotion 明确拒绝诊断任务/输入/结果；诊断不能通过改标签直接提升为交付。旧诊断保留为历史，但不能为新选择/区域作当前证明。

## 5. 审查与后续

独立 reviewer 查看校样实际字形与细节，判断仍登记到当前 exact region inventory 的原 region-review 机制，并在说明中引用确切校样任务/输入/结果及 PPTX hash。校样本身不把 faithful-geometry-appearance 升级；若发现问题，修订区域后生成新校样，旧校样不能沿用。完整正式链继续按原门限执行；本轮不自动将预览 PPTX晋升为正式构建。

最低证据：G1 未通过、四项 passed/appearance not-established 的真实隔离 Runtime 可合法生成诊断输入/任务和同 renderer SDK 校样；输入/输出都保留准确 v3 Unicode、素材和映射；准入 failed/其他项 not-established、错项目/旧选择/审查、撤回来源授权、伪造 diagnostic_ref、非法字段/资产、缺字体、目录越界/已存在均在对应写前拒绝；实际文件/原文/裁切/字距篡改拒绝；诊断结果无法被正常结果/anchor通路接受，原 Gate 与正式头完全保持。范围限定相关回归与独立反例，不重复无关全项目/网络测试。

字距与单字形描边能力是独立有限载体：当前诊断先支持已受审字段，不能为了生成校样临时放宽未知 outline/weight/group 字段。字形 CapabilityGap 如实保留；已交包和已完成提交不回改。

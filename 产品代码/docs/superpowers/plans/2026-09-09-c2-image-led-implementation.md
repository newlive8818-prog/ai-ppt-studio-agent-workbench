# C2 Image-led 三页闭环实施计划

> 使用 executing-plans 实施；独立子代理执行规格和工程 Review。唯一执行事实见 ../../validation/c2-image-led/verification-report.md。

**Goal:** 在既有 Runtime 正式路径落实 Image 2 自主设计、可信定版与忠实原生转换。

**Architecture:** 源材料/内容/Gate 不复制；专用派生层经现有 action/artifact/确认通道接入。Image-led 使用显式 compiler/handoff 版本；旧合同读取继续隔离，UI 保持已验收结构。

**Tech Stack:** Python stdlib / unittest、Node MCP / node:test、React / Vitest、Codex Presentations SDK。依赖复用本机缓存，不安装插件。

实施依据：[技术设计](../specs/2026-09-09-c2-image-led-runtime-design.md)。所有路径相对源码根。以下每一组先写行为测试并记录 RED，再实现并记录 GREEN，范围内技术修复自主继续。

## T01 技术规格与复用边界

- [x] 阅读基线、核对精确 Git/manifest、审查现有 material/visual/action/Gate 接口。
- [x] 保存正式设计，声明独立 Region 审查不等于自动视觉能力。
- [x] 独立材料/视觉规格 Review，关闭 Important/Critical，保存意见与处理。
- [x] 提交规格、计划、开工记录（b53f201）；不修改已验收 C1。

## T02 当前材料输入与请求

Files: 新增 `domains/materials/image_input_contracts.py`、`application/image_led_service.py`、`tests/test_image_input_contracts.py`、`tests/test_image2_input_boundary.py`；修改 `application/project_service.py`、`context_compiler.py`、`application/bridge/project.py`、`mcp/server.mjs`、`mcp/tools/project-tools.mjs`。

- [x] 用临时 ProjectKernel、登记真实临时源文件、当前蓝图/EvidenceBook 和测试专用可信 G0 建 fixture；相同测试替换 source 字节时先观察无拒绝的 RED。
- [x] 使用边界测试验证未登记来源、hash变化、同源换ID、排除区域相交和用途越权，并比较完整业务树快照。
- [x] 先写闭合 schema 与只读桥接，解析 `ArtifactReference`、`require_exact_ref`，核对原始文件/提取内容 hash；拒绝 URL/目录无快照，保留文本空白和合法无图页。标准 Transitional OOXML page/object/table 已接入，复杂格式保持 CapabilityGap。
- [x] 写可信 input policy 确认与持续复用测试：相同授权用于另一页不消费新 identity；自填授权、修改未签 scope、换项目/receiver/材料区域失败。
- [x] 用 ScopedConfirmationPolicy + confirmation ledger 绑定 scope artifact；既有 human-decision 接口做宿主验证，Python sole writer，缺少 verifier 返回真实 gap。
- [x] 写 `generate-slide-images` 当前 pack context/请求 RED；`RecordingTransport.calls == []` 证明前置失败不外发。输入变化/过期 context 拒绝；成功 payload 无内部路径/账本/排除正文/布局要求。
- [x] 接入原 action/context/result 事务；持久 request ID、失败未知状态，禁止盲重发；竞态撤销/并发claim/历史请求恢复均有回归。
- [x] Run: `PYTHONPATH=src:/private/tmp/c2-python-deps python3 -m unittest tests.test_image_input_contracts tests.test_image2_input_boundary -v`，全部通过后纳入 C2 候选。

## T03 定版、忠实合同与通用转换

以下勾选表示工程入口与 synthetic 验证，真实客户/用户决定在 T05 独立维护。未知载体（包括当前非 null shadow）写前 CapabilityGap，不能改图绕过。

Files: 新增 `domains/visual/image_led.py`、`application/image_led_native.py`、`scripts/image-led-native.mjs`、`tests/test_image_led_fidelity.py`、`tests/image-led-native.test.mjs`；修改 `application/visual_service.py`、`domains/visual/compilation.py`、`context_compiler.py`。

- [x] 候选登记读取图像实 bytes，并绑定 request、pack、页、copy 和 materials；三页 synthetic 候选链通过。
- [x] 选择 proposal 将确切 candidate+TargetBinding+逐字文案固定到不可变 ref；区域清单在可信定版之后；真实可信决定写 selection，伪造 selection 字符串在入口被拒。
- [x] 纯域合同覆盖不同页 ID/内容/对象数，逐字 copy、区域/对象完整非重复、材料反向覆盖和未知能力拒绝。
- [x] 实现闭合 TargetBinding、完整区域映射与 geometry/content/appearance/material/connector 等值检查。核心对象不能映射成位图；复杂无字装饰允许独立层。
- [x] 现有合同集在新路线比较 selected copy，旧路线仍比较旧蓝图；不允许新路线无 selection 走旧发布。合同与独立版本计划同事务。
- [x] 编译器验证完全匹配后派生，只复制权威对象与绑定；相同输入 `assertEqual(first, second)`，改输入 `assertNotEqual`。
- [x] build-native-first context 解析精确 current 计划并复验依赖；输出必须唯一不存在/项目内。renderer 预检后使用 Presentations SDK 执行数据，不按页 ID 分支、不写专页脚本。
- [x] 实際读取 Presentations skill/docs，用两组数据运行相同 renderer；保存 SDK 输出、对象/文本检查及渲染，失败保全、不覆盖旧结果。
- [x] Run: Python fidelity + 原视觉编译/lineage 回归，Node renderer tests；通过后纳入 C2 候选。

## T04 G2/G3、投影和 Skill

Files: 修改 `application/gate_evaluator.py`、`application/visual_invalidation.py`、必要现有投影入口、`skills/ai-ppt-studio/SKILL.md`、`skills/ai-ppt-studio/references/presentations-handoff.md`、`references/visual-workflow.md`；新增 `tests/test_image_led_runtime.py`。

- [x] RED：替换 selection/图像/合同后 old plan/anchor/G2 evidence 不再 current；伪造四维 evidence、postflight failure 不能晋级；真实 PPTX hash 不符拒绝。
- [x] 结果核对真实对象/文件与目标身份，四维证据独立，G2 继续要求当前 macos-powerpoint 证据；G3 仍由既有可信用户确认。
- [x] 验证 VisualReview 投影取 selected copy，不用 frozen-copy fallback，保持 R3 token-map/ReviewMark/text-anchor 和布局。
- [x] 更新 Skill 只执行新合同身份/禁止重设计，原样记录 legacy 未迁移证据，保持43工具目录。
- [x] Run: image-led Runtime、v23 lineage、visual review、Node MCP相关回归；通过后纳入 C2 候选。

## T05 实物、独立 Review 与候选

- [ ] 在独立 Runtime 当前项目经真实 Mission/内容/G0；不能复用测试签名器或 C1 Gate。缺少真实决定先准备可审对象，再请求真实决定。
- [ ] 合法已授权材料通过当前输入包生成三页；定版前来源核对、用户确切选稿；同一通用 renderer 忠实转换。
- [ ] 并排/叠图/局部差异、四维审查；当前 PowerPoint 打开/编辑/保存/重开与 hash，既有审核和真实 G3。独立记录 E1–E5，未运行明确 NotRun。
- [x] Run: `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=/private/tmp/c2-python-deps python3 -m unittest discover -s tests`。
- [x] Run: `npm run quality`（typecheck/build/node/widget），MCP catalog 与相关 contract tests；四基线相对链接与原型、`git diff --check`。
- [x] 冻结候选提交后对同一 SHA 做独立规格/工程 Review，修复则新 SHA、定向复验、Review 对准最终差异。
- [x] 记录精确 SHA、diff、测试、AC与剩余真实门给总控，不合并/Push/安装/发布/C3。

## 总控返回的 Runtime 集成修复（2026-09-09）

代码校验器和独立 renderer 已存在不等于 Runtime 集成完成。以下未关闭项先真实生产入口 RED，再实现与复验。

- [x] selection→RegionInventory 正式登记、真实 Agent 审查 lineage、变化后失效。
- [x] regions→合同/独立版本计划原子发布→正式 action handoff。
- [x] 实际 renderer bytes/hash→构建结果→四维审核→anchors/G2/既有审核投影。
- [x] generate-slide-images 的实际生产执行/结果接入，不盲重发未知请求。
- [x] 针对测试、全量/Node/Widget/类型/构建、独立 Review 与新精确本地提交。
- [ ] 真实样本、PowerPoint、真实用户 G3（独立于上述工程项）。

本轮代码候选 `ba7efa760c93bf423ed4f932ea8d2c54fa16f157` 已完成703项Python、149项Node、755项Widget、类型/构建、两路按精确SHA划分范围的独立Review；真实 T05 样本/用户/PowerPoint 条目仍未完成。精确证据与后续总控交接仅维护在唯一执行记录。

## 总控返回：G-01/G-02 生图恢复修复

保留上述候选身份、旧全量通过与原三集成问题 CLOSED，继续原 Change/分支/Worktree。

- [x] G-01 真实默认 MCP→真实 bridge RED：仅刷新 revision 的 unknown 重试不得二次外发。
- [x] G-02 真实 bridge RED：无关公开 decision 更新后，成功响应保全。
- [x] 持久原请求恢复、明确 new 意图、同 ID 输入冲突与无新增授权回归。
- [x] request/claim CAS 返回保全、并发返回、连续无关更新、撤销/来源变化后保全与晋级拒绝。
- [x] 适用/全量回归、作者隔离固定候选 Review、本地候选提交与总控复核证据准备；唯一执行记录记载全部证据。代码候选 `c9e01379821b2e1b3f79a3e9a1239489c6270532`，关闭复核 Critical/Important/Minor=0，Python713/713、Node160/160、Widget755/755与类型/构建通过。
- [ ] 总控对固定候选完成复核并决定是否进入合并准备；本执行任务不自动合并、Push、发布或启动 C3。

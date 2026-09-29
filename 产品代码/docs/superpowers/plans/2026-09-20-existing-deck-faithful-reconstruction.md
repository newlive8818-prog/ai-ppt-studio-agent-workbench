# Existing Deck Faithful Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 现有 PPT 优化项目从指定原稿直达逐页 Image 2 设计，内部选稿后忠实转换为可编辑 PPTX；任一页未还原或未验证时禁止登记可交付结果。

**Architecture:** 新项目类型使用独立的源稿、内部选图与最终验收状态，不借旧路线的 G0/G3 或用户定版回执。沿用现有 Image-led 的 TargetBinding、区域清单、原生对象和字节核验器；在构建前检查完整选图与映射，在结果登记及交付前检查同一组身份。所有中间页保持候选/受阻状态，原稿页只能作为输入。

**Tech Stack:** Python Runtime、不可变 artifact/CAS、Codex Presentations、现有 Image-led validators、unittest。

**Spec:** `../../../../00-唯一研发基线索引-v1.0.md` §1.2–1.3、§1.8；`../../../../01-产品需求基线-v1.0.md` §1.7；`../../../../02-系统详细设计-v1.0.md` §1.2–1.3、§1.7；`../../../../03-UI设计与交互规范-v1.0.md` §1.7。当前 C3 变更边界见 `../../changes/CHG-IL-C3.md`。本计划是待实现设计，不提升当前 Runtime、代表性客户 43 页或 G4 的状态。

## Global Constraints

- 仅适用用户指定现有 PPT 且任务限于视觉优化和可编辑转换；从零制作保留原流程。
- 原稿文件、页序、原文和素材是输入依据，不是设计权威；确切选中图是下游设计依据。
- 不要求用户中途逐页审图；AI 内部选择的记录称为 `internally-selected`，不得伪造 `user-finalized` 或旧 G0/G3。
- `project_id + slide_id + page_order + target_image_sha256 + selected_copy_sha256 + material_roles + accepted_deviations` 必须贯穿构建和检查。
- 主文字、数字、表格和关键关系为原生可编辑对象；无字复杂装饰可作为独立可替换层。
- 无完整身份、映射或同身份视觉审查时失败即停；失败不覆盖原稿、已有结果和已验收文件。
- 如源页含不得外发的真实图片，CRS 仅设计空白素材位；本地合成图成为确切选图标的，独立内部审查同时绑定原响应、合成记录与目标图，随后逐页区域映射与原生还原均引用该目标图。

---

### Task 1: 专用入口和不可变原稿身份

**Files:**
- Create: `src/ai_ppt_studio/application/existing_deck_optimization.py`（入口与源稿页清单）
- Modify: `src/ai_ppt_studio/application/project_service.py`（显式项目类型分派）
- Test: `tests/test_existing_deck_optimization.py`

**Interfaces:**
- Consumes: 由现有材料读取器验证的原始 PPTX 字节、实际源文件 SHA-256、Codex Presentations 导入的逐页画面/可见文字/素材字节。
- Produces: `source-deck-snapshot`，含 `project_id`、`source_pptx_sha256`、`source_pptx_ref`、按页序排列的 `slide_id/page_order/visible_copy/media_refs`；写入当前 head `optimization/source`。入口明确标识 `existing-deck-optimization/v1`，旧项目类型不能隐式切换。

- [ ] **Step 1: 写失败测试。** 构造两页原稿，分别改变源文件字节、调换页序、删去一个文本项、复用另页图片；逐一断言入口拒绝且 revision 与 artifact heads 不变。再断言合法两页按源顺序生成唯一快照。
- [ ] **Step 2: 运行测试确认它因入口不存在而失败。** `PYTHONPATH=src python3 -m unittest tests.test_existing_deck_optimization -v`
- [ ] **Step 3: 实现入口。** 对 PPTX 实际字节算 SHA-256；页序按导入结果生成、检查唯一且连续；文本保留原文、换行及有意义的空白；图片身份来自实际字节。已有 `file://` 或 `inline://` 清单引用不能替代可重放源文件。
- [ ] **Step 4: 重跑单测，通过后记录所覆盖的源稿身份与尚未建立的外部样本证据。**

### Task 2: 内部选图，禁止候选图自动升级为设计权威

**Files:**
- Modify: `src/ai_ppt_studio/application/image_led_selection.py`（专用内选入口；保留原有可信用户选择入口）
- Modify: `src/ai_ppt_studio/domains/visual/image_led.py`（选图来源校验）
- Test: `tests/test_existing_deck_selection.py`

**Interfaces:**
- Consumes: Task 1 当前 `optimization/source`；每页确切请求与响应、原图字节 SHA-256、原稿逐项文案与素材角色、独立内容/来源核对结果。源图片已获外发许可时使用 `source-media-guided` 绑定原字节与 OOXML 位置；未获许可时使用空白版位和本地合成，不在两个路径间静默切换。
- Produces: `optimization/selection`：完整、唯一、按源页序的每页 `TargetBinding`，另有 `selection_origin=internally-selected` 和内部复核任务身份。guided 路线的复核绑定请求与响应并检查素材保真/角色位置，本地路线绑定响应、合成记录及确切目标图。不能用现有 `image-led-selection-confirmation` 冒充内部决定。

- [ ] **Step 1: 写失败测试。** 候选数少于源页数、图片跨页、旧图片 hash、当前可见文字不同、来源复核未通过、重复页和混入另一个原稿的图均拒绝；合法候选仍为 `candidate`，只有受审的内部选择写入 `optimization/selection`。
- [ ] **Step 2: 运行新测试确认拒绝行为尚不存在。** `PYTHONPATH=src python3 -m unittest tests.test_existing_deck_selection -v`
- [ ] **Step 3: 复用当前 candidate、review 和 `validate_target_binding` 校验，在独立项目路线中登记完整选图；保留图片字节 hash、源稿/源页身份与选择任务身份。** 无须用户逐页确认，但不能声明其做过视觉定版。
- [ ] **Step 4: 运行新测试及 `tests.test_image_led_selection`，证明旧路线可信确认行为未改变。**

### Task 3: 构建前的双向映射及无回退原生转换

**Files:**
- Modify: `src/ai_ppt_studio/application/image_led_native.py`（当前源稿与选图完整性）
- Modify: `src/ai_ppt_studio/context_compiler.py`（精确 handoff）
- Modify: `scripts/image-led-native.mjs`（只消费 handoff；禁止源稿页填位）
- Test: `tests/test_existing_deck_native.py`

**Interfaces:**
- Consumes: Task 2 的完整 selection；定版图实际字节、逐页区域清单和当前共同规范。
- Produces: 每页目标区域到原生对象、原生对象到目标区域的双向映射及唯一 PPTX 构建任务；不接受来源原稿 slide proto 作为缺页替代。

- [ ] **Step 1: 写失败测试。** 少一个选图/区域、过期文案、一个无来源原生对象、一个未覆盖的设计区域、原稿页填位、整页贴图冒充可编辑均在 PPTX 写入前拒绝；项目目录及先前有效 PPTX 字节保持不变。
- [ ] **Step 2: 运行新测试确认至少一个负例当前可越过该入口。** `PYTHONPATH=src python3 -m unittest tests.test_existing_deck_native -v`
- [ ] **Step 3: 只为专用路线加入完整页集合、精确图 hash、双向区域映射和原生对象前置校验；复用现有受管 handoff 与 `validate_faithful_objects`，删除所有以旧 slide proto 代填缺失页的分支。**
- [ ] **Step 4: 运行新测试及 `tests.test_image_led_runtime tests.test_image_led_results`，并检查提交前目录没有未授权 PPTX。**

### Task 4: 逐页对照及交付拒绝门

**Files:**
- Modify: `src/ai_ppt_studio/application/image_led_results.py`（同一 PPTX 的全页结果核验）
- Modify: `src/ai_ppt_studio/application/delivery_service.py`（专用项目类型的可交付条件）
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`（此路线的最终验收状态；不写旧 G0/G3）
- Test: `tests/test_existing_deck_delivery.py`

**Interfaces:**
- Consumes: Task 1–3 的源稿/选图/区域/构建身份、每页原生渲染、并排图、叠图、区域差异、独立视觉审查、编辑性和目标 PowerPoint 证据。
- Produces: 仅当全部源页同身份 `passed` 时的交付候选与最终文件 SHA-256；用户最终验收仍单独记录。

- [ ] **Step 1: 写失败测试。** 逐页文本、数字、素材、视觉/关系、编辑性、共同规范、目标环境分别注入一项失败；特别证明原稿文本数量、43 页页数、包结构、无溢出全部通过而有一页设计对照失败时仍不能交付。
- [ ] **Step 2: 运行新测试确认当前通用交付入口不足以识别这种项目类型。** `PYTHONPATH=src python3 -m unittest tests.test_existing_deck_delivery -v`
- [ ] **Step 3: 交付入口仅接受与当前 selection、区域和最终 PPTX hash 相同的全页报告，检查每页双向映射、逐字内容、局部视觉差异及可编辑性均通过；无结果或 `not-established` 一律拒绝。** 显式记录被接受的差异，不能用全页平均分抵消关键区域失败。
- [ ] **Step 4: 运行新测试、交付/G4 回归及全量 Python 回归。** 真实 43 页和 macOS PowerPoint 检查分别保存，不用单测代替实物与用户结果。

## 真实代表性客户项目退出条件

- 43 页各自拥有当前源页、CRS 请求/响应、内部选中图、区域映射、原生页、逐页对照和编辑性回执；43/43 均通过才允许登记完整交付候选。
- 完整 PPTX 当前 hash 在 macOS PowerPoint 中完成显示、编辑、保存、重开检查，然后交付用户做最终验收。
- 旧 v4 阶段稿保留历史身份；本计划或本地单测通过不改变它的完成状态。

## 2026-09-20 Worktree 实施状态

Task 1–4 的专用入口、内选图、原生双向映射及交付拒绝门已在本 C3 Worktree 增量编写，并以两页合成数据验证；详细回执见 [C3 验证台账](../../validation/c3-whole-deck/verification-report.md) §4.16。以上 checkbox 保留未勾选，表示完整任务仍有正式桥接/宿主、真实代表性客户 43 页、macOS PowerPoint 与最终交付的退出条件未满足。代码单测或合成的桌面证据不提升真实项目状态。
## 2026-09-21 历史设计复用增量

- 新增受治理的历史设计导入入口：精确绑定当前原稿、页号、可见文案、共同规则、图片字节及历史请求/响应 provenance；只接受历史 `CRS / gpt-image-2` 身份。
- 导入不调用 transport；同页已有 `unknown/started` 请求时保留其原 identity。导入候选仍须来源审核、候选登记和内部选图。
- 43 页逐页比较记录位于 [代表性客户 43 页历史设计与当前候选比较](../../validation/c3-whole-deck/representative-customer-43-design-comparison-20260921.md)。当前比较建议不提升 Runtime selection、native plan、native result、QA 或 delivery 状态。
- 当前执行顺序：完成源码回归与插件安装验证，再将确定复用的历史图通过公共 MCP 导入；随后逐页来源审核，仅为 P23、P24 及深审后确需重生的页面创建新的 Sunburst 请求。

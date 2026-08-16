# 《当 AI 开始负责交付》PPTX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按用户已经确认的 `19 页主分享 + 8 页附录`，制作一份互联网化、轻科技、简单、轻松、适合朋友分享且原生可编辑的 27 页 PowerPoint；主分享在物理第 19 页完成收尾，附录 A1–A8 只用于讨论深挖。

**Architecture:** 采用 Presentations 的“明确自定义视觉方向”路线，从空白 16:9 画布构建，不使用 Codex Grid、企业模板或第二套 PPTX 工具。使用 `@oai/artifact-tool` JavaScript ES module 创建全部可见文字、流程、架构、表格、时间线、Gate 与页码；封面和主分享收尾分别使用两张不重复的 Imagegen 抽象氛围图，语义关系仍保持 PowerPoint 原生可编辑。所有中间源、素材、渲染、布局检查和 QA 记录位于单一临时目录，项目目录只接收最终 PPTX。

**Tech Stack:** Codex Presentations、`@oai/artifact-tool`、JavaScript ES modules、内置 Imagegen、PowerPoint PPTX、`render_slides.py`、`create_montage.py`、`slides_test.py`、本地 Markdown/Git/原型证据。

---

## 0. 固定合同、页序与路径

### 权威输入

- 内容与视觉设计：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/产品代码/docs/superpowers/specs/2026-08-16-ai-native-product-friends-sharing-deck-design.md`
- 唯一基线索引：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/00-唯一研发基线索引-v1.0.md`
- 产品需求：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/01-产品需求基线-v1.0.md`
- 系统合同：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/02-系统详细设计-v1.0.md`
- UI 合同：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/03-UI设计与交互规范-v1.0.md`
- 可使用的局部原型证据：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/产品代码/prototypes/08-content-full-deck-review-v7-inline-feedback.jpg`

### 最终物理页序

```js
const MAIN_CONTENT_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 15, 16, 17, 21, 23, 24, 26, 27];
const APPENDIX_CONTENT_IDS = [11, 12, 13, 18, 19, 20, 22, 25];
const PHYSICAL_CONTENT_IDS = [...MAIN_CONTENT_IDS, ...APPENDIX_CONTENT_IDS];
```

必须同时满足：

- 物理第 1–19 页为完整主分享；物理第 19 页使用内容 ID 27，并承担收尾；
- 物理第 20–27 页为 `附录 A1–A8`；
- 物理第 20 页才开始附录编号；主分享不显示附录提示；
- 全文件 27 页，但现场讲到物理第 19 页即可自然停止；
- 封面图只用于物理第 1 页；收尾图只用于物理第 19 页；两张图不得复用。

### 固定路径

```text
SKILL_DIR=/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations
TMP_DIR=/private/tmp/codex-ai-native-friends-deck-20260816-v3
BUILDER=/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs
ASSET_DIR=/private/tmp/codex-ai-native-friends-deck-20260816-v3/assets
OUTPUT_DIR=/private/tmp/codex-ai-native-friends-deck-20260816-v3/output
TMP_PPTX=/private/tmp/codex-ai-native-friends-deck-20260816-v3/output/当 AI 开始负责交付.pptx
FINAL_DIR=/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料
FINAL_PPTX=/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx
RUNTIME_NODE=/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
RUNTIME_NODE_MODULES=/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules
RUNTIME_PYTHON=/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
RUNTIME_BIN_DIR=/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override
```

执行前必须再次调用 `load_workspace_dependencies`。如果返回路径与上面不同，以当次返回的三个字段 `RUNTIME_NODE`、`RUNTIME_NODE_MODULES`、`RUNTIME_BIN_DIR` 为准，并先更新本计划的执行记录；不得从一个路径推导另一个路径，不得使用系统、全局或仓库本地依赖。

### 已确认视觉合同

- 画布：16:9，1280×720。
- 背景：暖白 `#F7F8FC`、白色 `#FFFFFF`、极浅灰蓝 `#EEF2F8`；只允许少量深色转折页。
- 文字：石墨黑 `#151821`，次级灰 `#5C6475`。
- 强调：电光蓝紫 `#6377FF`、清透青绿 `#55D6C2`；个人认知转折少量使用暖珊瑚 `#FF8A6B`。
- 字体：中文 `PingFang SC`，英文和数字 `Helvetica Neue`；封面标题 68–80 pt，页标题 38–48 pt，正文不小于 18 pt，注释 14–16 pt。
- 气质：像朋友讲一次真实产品实验，诚实、轻松、略带自嘲；不是发布会、商业宣传、咨询报告或功能清单。
- 构图：一页一个判断；优先大标题、短句、开放留白、原生关系和真实证据；相邻页不得连续使用同一双栏、三列或卡片网格。
- 禁止：Codex Grid、企业蓝模板、卡片墙、Dashboard、胶囊按钮、机器人头像、芯片大脑、二进制雨、深色赛博霓虹和连续玻璃拟态。
- 事实边界：`已实现基础`、`已批准目标合同`、`已确认交互原型`、`待迁移能力`、`待验证能力`、`专项成功` 必须分别表达；不得声称整个产品已完成最终验收。
- 目标边界：当前产品必需发布目标为 macOS PowerPoint；Windows 与 WPS 是 deferred，不表达为已通过、兼容、失败或不支持。

## Task 1: 建立隔离构建环境与事实快照

**Files:**

- Create: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/source-notes.txt`
- Create: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/visual-brief.txt`
- Create: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/asset-prompts.txt`
- Read: 第 0 节列出的五份权威输入

- [ ] **Step 1: 重新加载演示文稿依赖**

调用 `load_workspace_dependencies`，记录当次返回的 Node.js executable、Node.js packages 和 Override binaries。预期三条路径都存在；任何一条缺失都在开始制品写入前报告阻断。

- [ ] **Step 2: 创建单一临时目录和最终输出目录**

Run:

```bash
mkdir -p '/private/tmp/codex-ai-native-friends-deck-20260816-v3/assets' '/private/tmp/codex-ai-native-friends-deck-20260816-v3/output' '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料'
```

Expected: 三个目录存在；不删除、不清空、不覆盖其他任务目录。

- [ ] **Step 3: 刷新 Git 时间点事实**

Run from the project root:

```bash
git rev-list --count HEAD
git log --reverse --date=short --pretty=format:'%ad%x09%s'
git rev-parse HEAD
```

Expected: 获得当前提交数量、日志输出的第一条可见提交日期和当前 HEAD。物理第 10 页可见文案保持口语化的“两周、近 100 次提交”；精确值和统计口径只进入 speaker notes，提交数量不作为产品成功证明。

- [ ] **Step 4: 用 `apply_patch` 写入来源快照**

`source-notes.txt` 必须逐条记录：五份权威输入绝对路径、当前 HEAD、提交统计、08 原型的证据身份、v2.2 目标/实现边界、macOS PowerPoint/deferred 边界、禁止的客户数据与敏感信息。文件末尾写明：`This is a source ledger, not acceptance evidence.`

- [ ] **Step 5: 用 `apply_patch` 写入视觉说明与素材提示词记录**

`visual-brief.txt` 必须抄录本计划第 0 节全部视觉合同和主/附录页序。`asset-prompts.txt` 必须保存 Task 2 的两条最终提示词、生成模式 `built-in imagegen`、选中输出路径和是否迭代。

## Task 2: 生成两张不重复的氛围图并固定本地证据

**Files:**

- Create: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/assets/cover-ai-collaboration.png`
- Create: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/assets/closing-ai-handoff.png`
- Create: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/assets/content-review-reference.jpg`

- [ ] **Step 1: 使用内置 Imagegen 生成封面图**

使用 `imagegen` 的 built-in 模式，use case 为 `stylized-concept`，输入以下完整提示词：

```text
Use case: stylized-concept
Asset type: 16:9 PowerPoint cover atmosphere image
Primary request: Friendly abstract editorial illustration about humans and AI building a product together.
Scene/backdrop: warm off-white background with flowing translucent threads and modular forms suggesting conversation, reasoning, code, and delivery.
Style/medium: refined contemporary editorial illustration, light internet-product aesthetic, soft depth, tactile translucent materials.
Composition/framing: 16:9 landscape; visual energy concentrated on the right; left 42 percent mostly quiet and low-detail for large Chinese title.
Lighting/mood: optimistic, intelligent, friendly, airy, collaborative.
Color palette: electric periwinkle, clear aqua, tiny warm coral accent, graphite only in very small amounts.
Text (verbatim): ""
Constraints: no text, no logo, no watermark; atmosphere only, not a semantic diagram.
Avoid: robot, humanoid face, brain, binary digits, circuit board, dashboard UI, dark cyberpunk, neon tunnel.
```

Inspect the generated image at full size. Accept only if the left title area is quiet, the right-side energy is clear, no forbidden motif appears, and the file is sharp enough for 1280×720. Copy the accepted built-in output into the exact asset path `cover-ai-collaboration.png` and record the original returned path in `asset-prompts.txt`.

- [ ] **Step 2: 使用内置 Imagegen 生成收尾图**

使用一次独立 built-in 调用，输入以下完整提示词：

```text
Use case: stylized-concept
Asset type: 16:9 PowerPoint closing atmosphere image
Primary request: Distinct abstract editorial illustration about responsible AI delivery, where human judgment and computational execution meet at a luminous handoff point protected by software guardrails.
Scene/backdrop: warm off-white fading into pale lavender; two different streams converge without forming a human figure.
Style/medium: refined contemporary editorial illustration, light internet-product aesthetic, soft luminous materials, visibly different composition from the cover.
Composition/framing: 16:9 landscape; convergence on the left-center; right 42 percent clean and low-detail for a closing statement and question.
Lighting/mood: reflective, responsible, hopeful, calm.
Color palette: periwinkle, clear aqua, subtle warm coral, restrained graphite.
Text (verbatim): ""
Constraints: no text, no logo, no watermark; atmosphere only, not a semantic diagram; must not resemble or repeat the cover composition.
Avoid: robot, humanoid face, brain, binary rain, circuit board, dark cyberpunk, dashboard UI, handshake stock-photo symbolism.
```

Inspect at full size. Accept only if the right-side copy area remains clean, the convergence point is readable, and the composition is distinct from the cover. Copy the accepted output into `closing-ai-handoff.png` and record provenance in `asset-prompts.txt`.

- [ ] **Step 3: 固定内容审核原型的局部证据图**

Run:

```bash
cp '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/产品代码/prototypes/08-content-full-deck-review-v7-inline-feedback.jpg' '/private/tmp/codex-ai-native-friends-deck-20260816-v3/assets/content-review-reference.jpg'
shasum -a 256 '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/产品代码/prototypes/08-content-full-deck-review-v7-inline-feedback.jpg' '/private/tmp/codex-ai-native-friends-deck-20260816-v3/assets/content-review-reference.jpg'
```

Expected: 源文件与临时副本哈希相同。任何使用位置必须同时显示 `已确认交互参考，不代表真实 Runtime / 宿主验收`。

- [ ] **Step 4: 验证素材边界**

逐张查看三张素材，确认没有客户专属信息、敏感项目名、凭据、Bearer token、未授权截图或生成文字。若 built-in Imagegen 不可用，停止在首次 PPTX authoring 之前并报告真实能力缺口；不得静默切换到需要 API key 的 CLI，也不得用占位图冒充已批准的两张氛围图。

## Task 3: 建立 Artifact Tool 构建器与可验证顺序

**Files:**

- Create: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs`
- Read: `/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations/artifact_tool_docs/API_QUICK_START.md`
- Read: `/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations/artifact_tool_docs/api/API_DOCS.md`

- [ ] **Step 1: 读取 Artifact Tool 必需文档**

Run:

```bash
sed -n '1,460p' '/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations/artifact_tool_docs/API_QUICK_START.md'
sed -n '1,1100p' '/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations/artifact_tool_docs/api/API_DOCS.md'
```

Then read the speaker-notes, image, table, connector, render/export and inspect references linked by `API_DOCS.md`. Expected: authoring、speaker notes、image crop、native table、connector ordering、PPTX export and layout inspection APIs are resolved before code is written.

- [ ] **Step 2: 连接只读依赖目录**

Run:

```bash
ln -s '/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules' '/private/tmp/codex-ai-native-friends-deck-20260816-v3/node_modules'
```

Expected: `@oai/artifact-tool` can resolve from the temporary builder without modifying the dependency bundle.

- [ ] **Step 3: 用 `apply_patch` 创建构建器骨架**

The `.mjs` must define and use this exact order contract:

```js
const MAIN_CONTENT_IDS = Object.freeze([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 15, 16, 17, 21, 23, 24, 26, 27]);
const APPENDIX_CONTENT_IDS = Object.freeze([11, 12, 13, 18, 19, 20, 22, 25]);
const PHYSICAL_CONTENT_IDS = Object.freeze([...MAIN_CONTENT_IDS, ...APPENDIX_CONTENT_IDS]);

if (MAIN_CONTENT_IDS.length !== 19) throw new Error('Main deck must contain 19 slides');
if (APPENDIX_CONTENT_IDS.length !== 8) throw new Error('Appendix must contain 8 slides');
if (PHYSICAL_CONTENT_IDS.length !== 27) throw new Error('Deck must contain 27 slides');
if (PHYSICAL_CONTENT_IDS[18] !== 27) throw new Error('Main slide 19 must be closing content 27');
if (PHYSICAL_CONTENT_IDS[19] !== 11) throw new Error('Appendix must begin on physical slide 20');
```

The builder must also define:

- one theme object containing the approved colors, fonts, margins and minimum type sizes;
- one `addSourcesNotes(slide, sources)` helper that always writes a `[Sources]` block;
- one footer helper that renders the current physical page number on main pages 1–19 and `附录 A1–A8` on appendix pages;
- one image helper that crops without distortion and never reuses cover/closing assets;
- simple native flow, layer, loop and comparison helpers; connectors are created before nodes;
- 27 named physical-slide functions and a `main()` that invokes them in physical order;
- export to the exact temporary PPTX path;
- export or inspect one layout JSON per physical slide as `slide-01.layout.json` through `slide-27.layout.json`;
- an assertion that the created presentation contains exactly 27 slides before export;
- no TypeScript-only syntax, `python-pptx`, PptxGenJS, LibreOffice or alternate PPTX writer.

- [ ] **Step 4: 建立 speaker notes 来源矩阵**

Every slide function must receive a non-empty `sources` array. Use the content design as the default source; add the relevant product/system/UI baseline for product-contract claims, Git HEAD for development-history claims, the local generated-image prompt for physical slides 1 and 19, and the local prototype path for physical slide 11 if the screenshot is shown. Notes must explicitly distinguish target contract from implemented evidence.

- [ ] **Step 5: 运行纯语法检查，不进行 authoring**

Run:

```bash
/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check '/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs'
```

Expected: exit code 0. Do not execute the builder yet; the artifact-operation marker must remain immediately before the first actual PPTX authoring run in Task 7.

## Task 4: 实现物理第 1–10 页主分享

**Files:**

- Modify: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs`
- Source: content IDs 1–10 in the approved content design

| 物理页 | 内容 ID | Function | Audience-facing title | 主视觉与可见重点 |
|---:|---:|---|---|---|
| 1 | 1 | `addMain01Cover` | 当 AI 开始负责交付 | 左侧极简标题；右侧封面氛围图；无功能清单、无 footer |
| 2 | 2 | `addMain02StartingPoint` | 我原本只想让 AI 做一份好 PPT | `我给 AI / 我想得到 / 我实际得到` 三段递进 |
| 3 | 3 | `addMain03PptDefinition` | PPT 不是一组页面，而是一套决策沟通交付系统 | 五层原生纵深关系 |
| 4 | 4 | `addMain04GenerateVsDeliver` | 生成一份 PPT，与交付一份 PPT，是两件事 | 七段责任链，后半段加重 |
| 5 | 5 | `addMain05ExecutorShift` | AI 改变的不是按钮，而是产品的执行主体 | 传统软件 / AI 原生责任对照，中心突出主要执行者变化 |
| 6 | 6 | `addMain06DesignMisjudgment` | 我一开始认为：AI 不懂设计 | 大字误判与三句认知转折，珊瑚色只服务个人反思 |
| 7 | 7 | `addMain07WhyAiUnderstandsDesign` | AI 为什么可以“懂设计” | 解释 `表征、解释、比较、推演、迁移`，不做意识主张 |
| 8 | 8 | `addMain08EngineeringDesignKnowledge` | 把 AI 的设计知识固化进工程 | Prompt→合同→工具→Gate→用户的原生链路 |
| 9 | 9 | `addMain09HumanAiDevelopmentLoop` | 我不是先写完需求，而是和 AI 循环开发 | 人机开发闭环；人负责判断，AI 负责推演和执行 |
| 10 | 10 | `addMain10FiveDefinitions` | 两周、近 100 次提交，产品经历了五次定义 | 五阶段时间线；提交数量退居证据，不做成功指标 |

- [ ] **Step 1: 实现 `addMain01Cover`**

保持封面最小化：标题、副标题、姓名/日期和 `cover-ai-collaboration.png`。标题区不得压到图像高细节区域；备注记录生成提示词和本地资产路径。

- [ ] **Step 2: 实现 `addMain02StartingPoint`**

三段信息使用一条斜向或纵向递进线，不做三张 UI 卡片；最后一段用克制珊瑚强调“没人能证明它已经可用”。

- [ ] **Step 3: 实现 `addMain03PptDefinition`**

用五层可编辑关系表达 `决策语境 → 证据边界 → 阅读叙事 → 视觉编码 → 真实交付`；每层只放一个短解释，完整定义放备注。

- [ ] **Step 4: 实现 `addMain04GenerateVsDeliver`**

创建七段水平链；连接线先于节点；突出 `原生可编辑文件、真实 PowerPoint、用户真实使用`，标题保持单行。

- [ ] **Step 5: 实现 `addMain05ExecutorShift`**

用开放式左右对照而不是表格网格：左侧“人操作软件”，右侧“AI 执行任务”，底部横向治理托底；中心只出现一次 `主要执行者变了`。

- [ ] **Step 6: 实现 `addMain06DesignMisjudgment`**

使用大字号第一人称误判，依次显示 `最初判断 / 后来发现 / 真正问题`；不要用机器人或脑图。

- [ ] **Step 7: 实现 `addMain07WhyAiUnderstandsDesign`**

使用一个中心句和五个关系动词；层级、对比、节奏、密度、构图等设计词作为低权重背景，不组成卡片墙。

- [ ] **Step 8: 实现 `addMain08EngineeringDesignKnowledge`**

实现 `案例与反馈 → 机制/反模式 → Visual Brief → Design System → Slide Contract → 原生锚点 → Gate/用户`；可见收束句固定为 `Prompt 激活知识，合同冻结知识，工具执行知识，Gate 和用户证明知识。`

- [ ] **Step 9: 实现 `addMain09HumanAiDevelopmentLoop`**

实现七步原生循环；人和 AI 的责任只用两组短句标注，不能渲染隐藏思维链或把 AI 描述为无人监督完成产品。

- [ ] **Step 10: 实现 `addMain10FiveDefinitions`**

实现五阶段轨迹：隔离式 Skill MVP、Agent 原生工作台、多角色与视觉治理、Contract-first v1.6、v2.2 轻量重构。精确提交统计进入备注；可见页只保留“两周、近 100 次提交”。

- [ ] **Step 11: 运行语法检查**

Run:

```bash
/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check '/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs'
```

Expected: exit code 0；仍不执行 builder。

## Task 5: 实现物理第 11–19 页主分享并在第 19 页收尾

**Files:**

- Modify: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs`
- Source: content IDs 14、15、16、17、21、23、24、26、27

| 物理页 | 内容 ID | Function | Audience-facing title | 主视觉与可见重点 |
|---:|---:|---|---|---|
| 11 | 14 | `addMain11ProductBecomesLight` | 创意需要反复推翻，所以产品反而要变轻 | 对话 + 两张按需审核页 + Runtime；原型图只作局部证据 |
| 12 | 15 | `addMain12ProductDefinition` | 这些失败最终定义了什么产品 | 一句话产品定义 + 人/AI/系统三条责任 |
| 13 | 16 | `addMain13FourLayerArchitecture` | 四层系统把自主执行变成可信交付 | 交互、AI 执行、治理、真实交付四层 |
| 14 | 17 | `addMain14GateOverview` | 这不是步骤清单，而是一组责任门 | Mission→G0→G1→G2→G3→G4→复盘总览 |
| 15 | 21 | `addMain15ExperienceObject` | 经验系统不是多存几条 Prompt | 一个经验对象的来源、范围、机制、结果、版本与反例 |
| 16 | 23 | `addMain16AiEraMvp` | AI 时代，MVP 不再是“最少功能” | `Minimum Verifiable Delivery Loop` + 六个闭环条件 |
| 17 | 24 | `addMain17RequirementDrift` | 为什么 AI 写出的代码会偏离最新需求 | 多个真相源拉扯一个实现结果 |
| 18 | 26 | `addMain18TraditionalSoftwareRole` | 传统软件没有消失，它成为 AI 的治理骨架 | 原生对比表；责任重分配，不做新旧优劣二元对立 |
| 19 | 27 | `addMain19Closing` | 产品价值，取决于它能对什么结果负责 | 收尾氛围图 + 责任汇合 + 开放问题；现场在此停止 |

- [ ] **Step 1: 实现 `addMain11ProductBecomesLight`**

用左侧淡出的五空间旧构想与右侧“Codex 对话 + 两张按需审核页 + Runtime”收敛关系表达复杂度重新安放。08 原型只占局部，必须带 `已确认交互参考，不代表真实 Runtime / 宿主验收`。

- [ ] **Step 2: 实现 `addMain12ProductDefinition`**

主句使用已批准定义：`运行在 Codex 内、面向阅读优先售前解决方案的受治理自主交付系统`。下方只保留 AI、人、系统三条责任，不做功能墙。

- [ ] **Step 3: 实现 `addMain13FourLayerArchitecture`**

四层使用不同宽度和结构，不画成四张等宽卡片；治理层横向托底。目标合同与当前实现边界写入备注，不能在可见页声称全部完成。

- [ ] **Step 4: 实现 `addMain14GateOverview`**

连接线先于 Gate 节点；每一道门只放一句责任边界。可见结论固定为 `每一道门都在防止一种责任冒充另一种责任。`

- [ ] **Step 5: 实现 `addMain15ExperienceObject`**

围绕一个可版本化经验对象排布来源、适用范围、机制、应用、结果、版本、反例；强调反馈必须能被证明、降级和回滚。

- [ ] **Step 6: 实现 `addMain16AiEraMvp`**

大定义固定为 `Minimum Verifiable Delivery Loop`，中文解释为 `最小可验证交付闭环`。六个条件保持低密度：真实任务、可用交付、失败暴露、用户验收、反馈进入下一轮、可恢复。

- [ ] **Step 7: 实现 `addMain17RequirementDrift`**

将聊天、基线、计划、代码、测试、原型作为不同方向的真相源，中心是被拉扯的实现；收束句强调 AI 会高速实现过期需求。

- [ ] **Step 8: 实现 `addMain18TraditionalSoftwareRole`**

使用原生可编辑对比表，正文不小于 18 pt；顶部结论是 `传统软件成为 AI 的治理骨架`。不得使用“传统软件落后、消失、被取代”等表达。

- [ ] **Step 9: 实现 `addMain19Closing`**

使用 `closing-ai-handoff.png`，右侧放核心结论和开放问题，左侧用少量原生关系显示人保留判断、AI 负责执行、软件锁定边界。不得写“谢谢”，不得提示“继续看附录”，不得复用封面图。

- [ ] **Step 10: 锁定主分享收尾断言并运行语法检查**

Builder must assert `PHYSICAL_CONTENT_IDS[18] === 27` and the nineteenth created slide has role `main-closing`.

Run:

```bash
/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check '/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs'
```

Expected: exit code 0；仍不执行 builder。

## Task 6: 实现物理第 20–27 页附录 A1–A8

**Files:**

- Modify: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs`
- Source: content IDs 11、12、13、18、19、20、22、25

| 物理页 | 附录 | 内容 ID | Function | Audience-facing title | 深挖任务 |
|---:|---:|---:|---|---|---|
| 20 | A1 | 11 | `addAppendixA1RoleResponsibility` | 第一个错误：角色越多，责任反而越模糊 | 角色数量与真实责任、独立实例证据 |
| 21 | A2 | 12 | `addAppendixA2EvidenceFirst` | 第二个错误：观点先行，会让 AI 带着结论找证据 | 观点先行 vs 证据先行 |
| 22 | A3 | 13 | `addAppendixA3FactsCannotBeInferred` | “已理解”和“真实完成”不能互相冒充 | Mission 与 Review Bridge 两条事实链 |
| 23 | A4 | 18 | `addAppendixA4MissionToG0` | Mission → G0：先把“说什么、凭什么说”做完整 | 内容生产、两道硬门、全稿审核与 G0 |
| 24 | A5 | 19 | `addAppendixA5G1ToG2` | G1 → G2：把审美判断变成可以执行的视觉合同 | Visual Brief、Design System、合同、锚点与双硬门 |
| 25 | A6 | 20 | `addAppendixA6G3ToG4` | G3 → G4：从视觉确认走到真实可用文件 | 反馈、G3、全量 PPTX、真实目标、G4 与复盘 |
| 26 | A7 | 22 | `addAppendixA7ExperienceEvolution` | 一个会进化的系统，也必须会退化 | 晋升、收窄、拆分、降级和回滚 |
| 27 | A8 | 25 | `addAppendixA8SingleSourceOfTruth` | 个人 AI 开发最重要的管理对象：唯一真相 | 最新决定到基线、计划、代码、测试和证据的传播链 |

- [ ] **Step 1: 实现 `addAppendixA1RoleResponsibility`**

使用开放三列 `早期假设 / 暴露问题 / 后来选择`；页眉显示 `附录 A1`。没有独立身份、上下文和输入输出记录时，只能写 `isolated-review-task`，不能写多 Agent 已证明专业。

- [ ] **Step 2: 实现 `addAppendixA2EvidenceFirst`**

上方灰色旧链 `预设观点 → 选择证据 → 组织说服路径`，下方蓝紫/青绿新链从事实、未知、冲突、缺口出发；保持标题和链路文本可读。

- [ ] **Step 3: 实现 `addAppendixA3FactsCannotBeInferred`**

上半页是 Mission/G0 不等式，下半页是 `准备 → Session → 打开 → 持久化 → 宿主通知 → AI 接收`；每一步允许独立失败，不用一个绿色勾表示全部完成。

- [ ] **Step 4: 实现 `addAppendixA4MissionToG0`**

以六阶段原生链解释内容生产、两道硬门、全稿审核、整套修订和 G0；技术对象全名进入 speaker notes，可见页用朋友能理解的短标签。

- [ ] **Step 5: 实现 `addAppendixA5G1ToG2`**

展示视觉命题、设计系统、逐页合同、三张锚点、视觉/工程硬门；G1/G2 明确为内部 Gate，不出现用户确认图标。

- [ ] **Step 6: 实现 `addAppendixA6G3ToG4`**

展示视觉反馈、G3、全量原生 PPTX、真实 PowerPoint 目标、G4、复盘。珊瑚色只标人类高影响确认；deferred 目标只进入备注中的边界说明。

- [ ] **Step 7: 实现 `addAppendixA7ExperienceEvolution`**

使用一个清晰循环，不画复杂网络；反馈经过抽象、应用、评价后可以晋升，也可以因反例收窄、拆分、降级或回滚。

- [ ] **Step 8: 实现 `addAppendixA8SingleSourceOfTruth`**

实现 `最新决定 → 权威基线 → 影响分析 → 新计划 → 范围开发 → 测试 → 真实证据`；最后一页仍显示附录身份，不做第二次结束页。

- [ ] **Step 9: 锁定附录编号与最终数量并运行语法检查**

Builder must assert physical slides 20–27 have labels `附录 A1` through `附录 A8`, and no main slide contains an appendix label.

Run:

```bash
/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check '/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs'
```

Expected: exit code 0；`main()` 已按 19 主分享 + 8 附录顺序调用全部 27 个函数。

## Task 7: 首次 authoring、渲染与自动检查

**Files:**

- Execute: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs`
- Create: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/output/当 AI 开始负责交付.pptx`
- Create: 27 slide PNGs, 27 layout JSONs, montage and inspect snapshot

- [ ] **Step 1: 在首次 authoring 前且仅执行一次制品标记**

Immediately before the next command, run exactly once:

```bash
RUNTIME_NODE='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node' RUNTIME_NODE_MODULES='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules' RUNTIME_BIN_DIR='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override' /Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node '/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations/container_tools/mark_artifact_operation_started.mjs' --operation-kind create --expected-output-count 1 --output-format pptx
```

Expected: success. Do not run this marker again for rebuilds or QA fixes.

- [ ] **Step 2: 运行完整 27 页构建器**

Run immediately after Step 1:

```bash
RUNTIME_NODE='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node' RUNTIME_NODE_MODULES='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules' RUNTIME_BIN_DIR='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override' /Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node '/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs'
```

Expected: one non-empty PPTX, 27 layout JSON files and an inspect snapshot; builder reports main count 19, appendix count 8 and total count 27.

- [ ] **Step 3: 用捆绑脚本渲染每一页**

Run:

```bash
RUNTIME_NODE='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node' RUNTIME_NODE_MODULES='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules' RUNTIME_BIN_DIR='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override' /Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 '/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations/container_tools/render_slides.py' '/private/tmp/codex-ai-native-friends-deck-20260816-v3/output/当 AI 开始负责交付.pptx'
```

Expected: render directory contains `slide-1.png` through `slide-27.png` with no missing physical page.

- [ ] **Step 4: 创建整套 montage**

Run with the render directory produced in Step 3:

```bash
RUNTIME_NODE='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node' RUNTIME_NODE_MODULES='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules' RUNTIME_BIN_DIR='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override' /Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 '/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations/container_tools/create_montage.py' --input_dir '/private/tmp/codex-ai-native-friends-deck-20260816-v3/output/当 AI 开始负责交付' --output_file '/private/tmp/codex-ai-native-friends-deck-20260816-v3/output/deck-montage.webp'
```

Expected: montage shows 27 thumbnails in physical order, with the visual closing at thumbnail 19 and appendix beginning at thumbnail 20.

- [ ] **Step 5: 运行溢出检查**

Run:

```bash
RUNTIME_NODE='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node' RUNTIME_NODE_MODULES='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules' RUNTIME_BIN_DIR='/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override' /Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 '/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations/container_tools/slides_test.py' '/private/tmp/codex-ai-native-friends-deck-20260816-v3/output/当 AI 开始负责交付.pptx'
```

Expected: no content overflowing the slide canvas. Any warning must be visually inspected and fixed unless it is a verified intentional background bleed.

- [ ] **Step 6: 检查占位词、错误兼容声明和来源备注**

Run:

```bash
rg -n -i 'T(BD)|T(ODO)|lorem|placeholder|click to|兼容 Windows|兼容 WPS|四个目标已通过' '/private/tmp/codex-ai-native-friends-deck-20260816-v3/output/deck-inspect.ndjson'
```

Expected: no match. Builder must also report 27 non-empty `[Sources]` blocks.

- [ ] **Step 7: 验证物理顺序与文件数量**

Use the exact content-order assertion already embedded in `build-deck.mjs`, then inspect filenames and montage. Expected:

```text
main slides = 19
appendix slides = 8
all slides = 27
physical slide 19 content id = 27
physical slide 20 content id = 11
layout json count = 27
rendered png count = 27
```

## Task 8: 全尺寸视觉复核、修订与交付

**Files:**

- Create: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/qa-ledger.txt`
- Inspect: montage and every final slide PNG at full size
- Modify: `/private/tmp/codex-ai-native-friends-deck-20260816-v3/build-deck.mjs`
- Create: `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx`

- [ ] **Step 1: 先检查 27 页整体节奏**

用 `view_image` 打开 `deck-montage.webp`。确认：主分享 1–19 形成完整故事；第 19 页具有明显收尾感；第 20 页开始出现附录眉题；相邻页轮廓有变化；整套年轻、轻松、有科技感但不是赛博或企业发布会；深色页不连续。

- [ ] **Step 2: 全尺寸检查物理第 1–10 页**

逐张用 `view_image` 打开 `slide-1.png` 到 `slide-10.png`。检查标题单行、正文可读、图像裁切、连接线、留白、主张单一性和来源备注；把每页 `pass` 或具体修复项写入 `qa-ledger.txt`。

- [ ] **Step 3: 全尺寸检查物理第 11–19 页**

逐张打开 `slide-11.png` 到 `slide-19.png`。重点检查原型证据说明、四层架构、Gate 连接线、传统软件对比表和收尾图裁切。确认第 19 页不是过渡页、没有附录提示、没有“谢谢”、没有复用封面图。

- [ ] **Step 4: 全尺寸检查附录 A1–A8**

逐张打开 `slide-20.png` 到 `slide-27.png`。确认 `附录 A1–A8` 连续、标题与主分享视觉一致但身份克制、三张 Gate 深挖页没有混写责任、最后一页不是第二次正式收尾。

- [ ] **Step 5: 修复全部视觉问题**

使用 `apply_patch` 修改 builder；缩短文案或改变布局，不通过缩小到最低字号以下解决密度。重新执行 builder 时不再运行 artifact marker；重新渲染并查看每一张改变过的幻灯片。所有无意重叠、裁切、标题换行、连接线穿字、图片失真和页码错误必须修复。

- [ ] **Step 6: 重跑自动检查与最终 27 页复核**

重复 Task 7 的 build、render、montage、`slides_test.py` 和 inspect 扫描，但不重复 marker。确认 27 张最终 PNG 都是当前 PPTX 的最新渲染；QA ledger 每页都有最终 `pass`。

- [ ] **Step 7: 复制最终 PPTX 并核对哈希**

Run:

```bash
cp '/private/tmp/codex-ai-native-friends-deck-20260816-v3/output/当 AI 开始负责交付.pptx' '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx'
shasum -a 256 '/private/tmp/codex-ai-native-friends-deck-20260816-v3/output/当 AI 开始负责交付.pptx' '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx'
```

Expected: 两个 SHA-256 完全一致。除用户另行要求，不提交二进制 PPTX 到 Git。

- [ ] **Step 8: 最终交付事实说明**

向用户只交付最终 PPTX，并简要说明：19 页主分享 + 8 页附录、主分享第 19 页自然结束、文件原生可编辑、已完成 27 页渲染/溢出/逐页视觉检查、两张生成图的来源提示词、以及没有把产品目标合同包装成当前全部实现。不得把本轮技术 QA 称为产品 G2/G4 或真实 macOS PowerPoint 正式验收。

## Plan self-review

- Spec coverage: 27 个已批准内容 ID 全部出现且只出现一次；主分享映射为 `1–10, 14, 15, 16, 17, 21, 23, 24, 26, 27`，附录映射为 `11, 12, 13, 18, 19, 20, 22, 25`。
- Closing coverage: 内容 ID 27 位于物理第 19 页；附录 A1 从物理第 20 页开始；封面和收尾使用不同生成图。
- Visual-route coverage: 采用用户明确的互联网化、轻科技、简单、朋友风自定义路线；不使用 Codex Grid、企业模板、Dashboard、卡片墙或赛博陈词滥调。
- Native-editability coverage: 关系、流程、架构、表格、时间线、Gate 和文字由 Artifact Tool 原生构建；生成图只承担环境氛围。
- Source-boundary coverage: 每页 speaker notes 都有 `[Sources]`；目标合同、已实现基础、原型、待迁移、待验证和真实证据分开表达。
- Tool-boundary coverage: 只使用 `@oai/artifact-tool` JavaScript ES module 写 PPTX；没有 `python-pptx`、PptxGenJS、LibreOffice 或第二写入路线。
- Marker coverage: `mark_artifact_operation_started.mjs` 在首次 builder authoring 前成功运行一次且只运行一次；语法检查不计 authoring。
- QA coverage: 27 页全部渲染、27 份 layout JSON、montage、overflow 检查、inspect 扫描和逐页全尺寸复核；任何无意重叠均须修复。
- Privacy coverage: 不使用客户专属事实、私密数据、凭据、Bearer token、敏感项目名或未授权截图。
- Placeholder scan: 计划中的内容分支、物理页序、两条提示词和全部固定路径均已确定；运行时差异只有一个明确处理规则——以当次 `load_workspace_dependencies` 返回值为准。

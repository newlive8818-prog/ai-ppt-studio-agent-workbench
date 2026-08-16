# 《当 AI 开始负责交付》增强视觉 PPTX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按已批准的方案 A，将 27 页朋友分享 PPT 重构为“AI 产品实验纪录片 × 互联网电子杂志”，通过用户指定的 CRS API 生成 7 张互不复用的 Image 2 非语义素材，并交付一份 `19 页主分享 + 8 页附录`、原生可编辑、逐页验证的 PowerPoint。

**Architecture:** 使用新的 `/private/tmp/codex-ai-native-friends-deck-20260817-v4` 隔离目录，不复用 v3 弱视觉 builder。Image 2 只生产氛围、隐喻和材质，所有文字、责任、流程、Gate、架构和表格继续由 `@oai/artifact-tool` 原生对象表达；构建器按主题/素材/备注/页组拆分，最后统一导出、渲染和检查。

**Tech Stack:** CRS Images API、`gpt-image-2`、Imagegen CLI、Codex Presentations、`@oai/artifact-tool` JavaScript ES modules、PowerPoint PPTX、`render_slides.py`、`create_montage.py`、`slides_test.py`、Git 与本地权威 Markdown/原型证据。

---

## 0. 执行合同、权威输入与文件边界

### 权威输入

- 增强视觉设计：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/产品代码/docs/superpowers/specs/2026-08-16-ai-native-product-friends-sharing-deck-design.md`
- 唯一基线索引：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/00-唯一研发基线索引-v1.0.md`
- 产品需求：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/01-产品需求基线-v1.0.md`
- 系统合同：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/02-系统详细设计-v1.0.md`
- UI 合同：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/03-UI设计与交互规范-v1.0.md`
- 内容审核局部证据：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/产品代码/prototypes/08-content-full-deck-review-v7-inline-feedback.jpg`

### 固定物理顺序

```js
const MAIN_CONTENT_IDS = Object.freeze([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 15, 16, 17, 21, 23, 24, 26, 27]);
const APPENDIX_CONTENT_IDS = Object.freeze([11, 12, 13, 18, 19, 20, 22, 25]);
const PHYSICAL_CONTENT_IDS = Object.freeze([...MAIN_CONTENT_IDS, ...APPENDIX_CONTENT_IDS]);
```

必须同时满足：

- 物理第 1–19 页是完整主分享；物理第 19 页使用内容 ID 27 并正式收尾；
- 物理第 20–27 页是 `附录 A1–A8`；
- 第 19 页不写“谢谢”，不提示附录，不复用封面图；
- 27 个内容 ID 全部出现且只出现一次；
- macOS PowerPoint 是当前必需目标；Windows/WPS 仍为 deferred，不形成兼容或不支持声明。

### 新临时目录与最终输出

```text
SKILL_DIR=/Users/defei/Library/Application Support/Codex API Client/codex-home/plugins/cache/openai-primary-runtime/presentations/26.813.12317/skills/presentations
IMAGEGEN_DIR=/Users/defei/Library/Application Support/Codex API Client/codex-home/skills/.system/imagegen
TMP_DIR=/private/tmp/codex-ai-native-friends-deck-20260817-v4
ASSET_DIR=/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2
CANDIDATE_DIR=/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates
SOURCE_DIR=/private/tmp/codex-ai-native-friends-deck-20260817-v4/src
OUTPUT_DIR=/private/tmp/codex-ai-native-friends-deck-20260817-v4/output
QA_DIR=/private/tmp/codex-ai-native-friends-deck-20260817-v4/qa
TMP_PPTX=/private/tmp/codex-ai-native-friends-deck-20260817-v4/output/当 AI 开始负责交付.pptx
FINAL_PPTX=/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx
```

### 源码职责

| 文件 | 单一职责 |
|---|---|
| `src/build-deck.mjs` | 创建 Presentation、按注册表调用 27 页、导出 PPTX/PNG/layout/montage/inspect |
| `src/theme.mjs` | 色彩、字体、间距、基础文字与语义线条 helper；不提供默认卡片墙 helper |
| `src/assets.mjs` | 加载 7 张 Image 2 素材和 08 原型，定义使用页唯一性与裁切 |
| `src/notes.mjs` | 每页 `[Sources]`、讲者提示和事实边界 |
| `src/registry.mjs` | 27 页物理顺序、内容 ID、角色、附录编号与 builder 引用 |
| `src/slides-main-01-10.mjs` | 物理第 1–10 页 |
| `src/slides-main-11-19.mjs` | 物理第 11–19 页 |
| `src/slides-appendix.mjs` | 附录 A1–A8 |
| `src/verify-contract.mjs` | 不 authoring 的静态合同检查 |

项目目录只接收最终 PPTX和本计划文档；不把 v4 临时源码、图片候选、渲染或 QA ledger 写入项目目录。不得触碰 `/Users/defei/Documents/AI-PPT-Workspace` 或并行 Web 产品空间。

---

### Task 1: 建立 v4 隔离环境与时间点事实

**Files:**

- Create: `/private/tmp/codex-ai-native-friends-deck-20260817-v4/source-notes.txt`
- Create: `/private/tmp/codex-ai-native-friends-deck-20260817-v4/visual-brief.txt`
- Create: `/private/tmp/codex-ai-native-friends-deck-20260817-v4/asset-prompts.txt`

- [ ] **Step 1: 重新加载演示文稿依赖**

调用 `load_workspace_dependencies`，逐项记录返回的 Node.js executable、Node.js packages、Python executable 和 Override binaries。后续命令只使用当次返回路径，不从旧计划或相邻路径推导。

Expected: 四条绝对路径真实存在；任一路径缺失即在 authoring 前停止。

- [ ] **Step 2: 创建 v4 目录，不删除 v3**

Run:

```bash
mkdir -p \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2' \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates' \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/src' \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/output' \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/qa' \
  '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料'
```

Expected: 目录存在；v3 保留为已失效实现证据，不执行其 builder。

- [ ] **Step 3: 连接只读 Node 依赖**

Run with the current `RUNTIME_NODE_MODULES` returned by `load_workspace_dependencies`:

```bash
ln -s "$RUNTIME_NODE_MODULES" '/private/tmp/codex-ai-native-friends-deck-20260817-v4/node_modules'
```

Expected: `node_modules` 是指向当次 bundled packages 的 symlink；不修改依赖目录。

- [ ] **Step 4: 刷新 Git 事实**

Run from the project root:

```bash
git rev-parse HEAD
git rev-list --count HEAD
git log --reverse --date=short --pretty=format:'%ad%x09%s'
```

Expected: 记录当前 HEAD、可见提交数和首个可见提交日期；可见页仍使用口语化“两周、近 100 次提交”，精确值只进备注。

- [ ] **Step 5: 用 `apply_patch` 写三份事实文件**

`source-notes.txt` 必须包含六个权威输入、Git 时间点、08 原型身份、v2.2 目标/实现边界、macOS/deferred 边界和隐私排除，末尾写：

```text
This is a source ledger, not acceptance evidence.
```

`visual-brief.txt` 必须包含方案 A、七个 Image 2 使用页、禁用项、页面家族和“原 builder 仅保留内容骨架”的失效说明。`asset-prompts.txt` 先写 `status=not-generated`、`route=CRS API`、`model=gpt-image-2`，不得记录 endpoint 凭据或密钥。

---

### Task 2: 验证 CRS Image 2 路由，不泄露凭据

**Files:**

- Read: `/Users/defei/Library/Application Support/Codex API Client/codex-home/config.toml`
- Read: `/Users/defei/Library/Application Support/Codex API Client/codex-home/skills/.system/imagegen/scripts/image_gen.py`
- Create: `/private/tmp/codex-ai-native-friends-deck-20260817-v4/cover-prompt.txt`

- [ ] **Step 1: 只检查环境变量存在性**

Run:

```bash
if [ -n "${CRS_KEY:-}" ]; then
  echo 'CRS_KEY=set'
else
  echo 'BLOCKED: CRS_KEY is not set'
  exit 12
fi
```

Expected: 只输出 `CRS_KEY=set`；不得执行 `env`、`set`、`printenv CRS_KEY` 或任何会打印值的命令。

- [ ] **Step 2: 从当前桌面任务配置解析非秘密 Base URL**

Run with the current bundled Python:

```bash
CRS_IMAGE_BASE_URL="$($RUNTIME_PYTHON -c 'import tomllib; p="/Users/defei/Library/Application Support/Codex API Client/codex-home/config.toml"; d=tomllib.load(open(p,"rb")); print(d["model_providers"]["crs"]["base_url"])')"
case "$CRS_IMAGE_BASE_URL" in
  https://*) echo 'CRS base URL format=ok' ;;
  *) echo 'BLOCKED: invalid CRS base URL'; exit 13 ;;
esac
```

Expected: 只确认格式，不修改普通终端或桌面配置。若当前桌面配置不含 `model_providers.crs.base_url`，停止并报告，不硬编码历史 endpoint。普通终端配置继续保持独立，不因本任务改写 provider。

- [ ] **Step 3: 验证 Imagegen CLI 依赖**

Run:

```bash
$RUNTIME_PYTHON -c 'import openai; print("openai-package=ok")'
$RUNTIME_PYTHON '/Users/defei/Library/Application Support/Codex API Client/codex-home/skills/.system/imagegen/scripts/image_gen.py' --help >/dev/null
```

Expected: 两条命令 exit 0。不安装新包；缺失即报告能力阻断。

- [ ] **Step 4: 用 `apply_patch` 写封面最终提示词**

Exact file content:

```text
Use case: stylized-concept
Asset type: 16:9 editorial PowerPoint cover for a personal AI product experiment
Primary request: A refined abstract scene where a hazy human intention and a precise computational stream collaboratively shape one tangible deliverable object, suggesting conversation becoming code, evidence, and delivery.
Scene/backdrop: warm off-white editorial space with translucent fibers, layered paper-like planes, soft dimensional light, and a protected luminous outcome on the right.
Style/medium: high-end contemporary digital editorial illustration, tactile translucent materials, sophisticated internet-product aesthetic, restrained depth, not corporate stock art.
Composition/framing: 2048x1152 landscape; all visual energy on the right 55 percent; left 42 percent quiet, warm, low-detail, and high-contrast enough for large Chinese title; no central symmetry.
Lighting/mood: intelligent, optimistic, personal, calm, curious.
Color palette: electric periwinkle, clear aqua, warm off-white, graphite traces, one tiny warm coral accent.
Text (verbatim): ""
Constraints: no text, no logo, no watermark; atmosphere and metaphor only; no semantic diagram.
Avoid: robot, humanoid face, hands, handshake, brain, circuit board, binary digits, dashboard UI, neon tunnel, dark cyberpunk, generic AI orb.
```

- [ ] **Step 5: 以封面候选作为真实 Images API 能力检查**

Run as a networked command using the explicitly approved CRS route:

```bash
CRS_IMAGE_BASE_URL="$($RUNTIME_PYTHON -c 'import tomllib; p="/Users/defei/Library/Application Support/Codex API Client/codex-home/config.toml"; d=tomllib.load(open(p,"rb")); print(d["model_providers"]["crs"]["base_url"])')"
env \
  OPENAI_API_KEY="$CRS_KEY" \
  OPENAI_BASE_URL="$CRS_IMAGE_BASE_URL" \
  "$RUNTIME_PYTHON" \
  '/Users/defei/Library/Application Support/Codex API Client/codex-home/skills/.system/imagegen/scripts/image_gen.py' \
  generate \
  --model gpt-image-2 \
  --quality high \
  --size 2048x1152 \
  --prompt-file '/private/tmp/codex-ai-native-friends-deck-20260817-v4/cover-prompt.txt' \
  --out '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates/cover-ai-collaboration-v1.png'
```

Expected: 只向当前 CRS Base URL 发送请求，生成非空 PNG。若返回 401、403、404、模型不存在或 endpoint 不支持，立即停止；不得切到官方通道、`gpt-image-1.5` 或其他供应商。

- [ ] **Step 6: 全尺寸检查封面候选**

用 `view_image` 打开 `cover-ai-collaboration-v1.png`，检查：左侧 42% 低细节、右侧能量集中、无文字/Logo/禁用元素、无低清晰度。合格后复制为：

```bash
cp \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates/cover-ai-collaboration-v1.png' \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2/cover-ai-collaboration.png'
```

若不合格，只修改一个明确问题并生成 `cover-ai-collaboration-v2.png`；不得覆盖 v1。

---

### Task 3: 生成并检查其余六张 Image 2 素材

**Files:**

- Create: `/private/tmp/codex-ai-native-friends-deck-20260817-v4/image2-prompts.jsonl`
- Create: six candidate PNGs under `assets/candidates/`
- Create: six selected PNGs under `assets/image2/`

- [ ] **Step 1: 用 `apply_patch` 创建精确 JSONL**

Create one JSON object per line with these exact jobs:

```jsonl
{"out":"executor-shift-v1.png","model":"gpt-image-2","quality":"high","size":"2048x1152","use_case":"stylized-concept","prompt":"A high-end abstract editorial illustration about responsibility shifting from human operation to AI execution. A warm imperfect judgment stream enters from the left and a precise periwinkle computational field takes over execution on the right, while a quiet transparent software rail protects the transition. Landscape 16:9, strong diagonal movement, open center for native slide labels, visibly different from the cover. Warm off-white, graphite, electric periwinkle, clear aqua, tiny coral. No text, no logo, no watermark, no robot, no person, no hands, no handshake, no brain, no UI, no circuit board, no cyberpunk."}
{"out":"design-misjudgment-v1.png","model":"gpt-image-2","quality":"high","size":"2048x1152","use_case":"stylized-concept","prompt":"A refined editorial illustration about the mistaken belief that AI cannot understand design. On a pale warm field, scattered fragments of hierarchy, rhythm, alignment, density and composition begin as disorder with a thin coral scar, then resolve into one elegant coherent spatial composition in periwinkle and aqua. Landscape 16:9, visual transformation from left chaos to right order, generous negative space for a large first-person statement. No text, no letters, no logo, no watermark, no brain, no robot, no design-software UI, no paint palette, no cyberpunk."}
{"out":"human-ai-iteration-v1.png","model":"gpt-image-2","quality":"high","size":"2048x1152","use_case":"stylized-concept","prompt":"A contemporary editorial illustration of human-AI product iteration. Two materially different paths, one warm and tactile and one precise and luminous, repeatedly diverge, fail, loop back and reconnect, producing a visibly improved outcome after several imperfect cycles. The loop must not be a perfect circle. Landscape 16:9 with the main trajectory on the right two-thirds and calm space for native responsibility labels. Warm off-white, electric periwinkle, aqua, restrained coral. No text, no logo, no watermark, no people, no hands, no infinity symbol, no dashboard, no robot, no circuit board."}
{"out":"governed-delivery-system-v1.png","model":"gpt-image-2","quality":"high","size":"2048x1152","use_case":"stylized-concept","prompt":"A sophisticated dark editorial image of autonomous AI execution inside transparent guardrails. A luminous periwinkle execution current moves through layered boundaries, version planes and evidence checkpoints toward one tangible deliverable, with aqua recovery paths and a small warm human-decision signal. Landscape 16:9, dramatic but calm, left and center visual depth, clear upper-right area for a product-definition sentence. No text, no labels, no logo, no watermark, no robot, no humanoid, no cybersecurity lock icon, no dashboard, no neon city, no binary rain."}
{"out":"verifiable-delivery-loop-v1.png","model":"gpt-image-2","quality":"high","size":"2048x1152","use_case":"stylized-concept","prompt":"A high-end abstract editorial illustration for a Minimum Verifiable Delivery Loop. An incomplete loop exposes a visible failure gap, passes through a small human confirmation point and a recovery branch, then closes into a usable delivered object. Landscape 16:9, loop positioned left-center, right and lower-right remain quiet for six native conditions. Warm off-white, periwinkle, aqua, one coral confirmation accent, soft dimensional materials. No text, no logo, no watermark, no perfect infinity symbol, no circular arrows infographic, no robot, no UI, no circuit board, no cyberpunk."}
{"out":"closing-ai-handoff-v1.png","model":"gpt-image-2","quality":"high","size":"2048x1152","use_case":"stylized-concept","prompt":"A distinct reflective editorial illustration about responsible AI delivery. Human judgment is represented by a warm tactile signal, AI execution by a precise periwinkle stream, and deterministic software by a transparent aqua boundary; all three converge at one quiet luminous handoff point without becoming a person or handshake. Landscape 16:9; convergence on the left-center; right 42 percent clean, warm, low-detail for a closing statement and open question; composition must not resemble the cover. No text, no logo, no watermark, no hands, no handshake, no robot, no brain, no dashboard, no circuit board, no cyberpunk."}
```

- [ ] **Step 2: 通过 CRS 批量生成六个不同任务**

Run:

```bash
CRS_IMAGE_BASE_URL="$($RUNTIME_PYTHON -c 'import tomllib; p="/Users/defei/Library/Application Support/Codex API Client/codex-home/config.toml"; d=tomllib.load(open(p,"rb")); print(d["model_providers"]["crs"]["base_url"])')"
env \
  OPENAI_API_KEY="$CRS_KEY" \
  OPENAI_BASE_URL="$CRS_IMAGE_BASE_URL" \
  "$RUNTIME_PYTHON" \
  '/Users/defei/Library/Application Support/Codex API Client/codex-home/skills/.system/imagegen/scripts/image_gen.py' \
  generate-batch \
  --input '/private/tmp/codex-ai-native-friends-deck-20260817-v4/image2-prompts.jsonl' \
  --out-dir '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates' \
  --concurrency 3
```

Expected: 六个语义文件全部非空；不使用 `n` 生成不同任务；网络仅发往当前 CRS Base URL。

- [ ] **Step 3: 创建七图素材 montage**

Run:

```bash
$RUNTIME_PYTHON \
  "$SKILL_DIR/container_tools/create_montage.py" \
  --input_dir '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates' \
  --output_file '/private/tmp/codex-ai-native-friends-deck-20260817-v4/qa/image2-candidates-montage.png'
```

Expected: 七张候选可同时比较，构图不重复，色彩与材质属于同一世界但不是同一张图的变体。

- [ ] **Step 4: 逐张全尺寸检查并选择**

用 `view_image` 逐张打开六张候选；检查各自留白方向、禁用元素、模糊、错误文字、重复构图和裁切风险。合格后运行：

```bash
cp '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates/executor-shift-v1.png' '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2/executor-shift.png'
cp '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates/design-misjudgment-v1.png' '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2/design-misjudgment.png'
cp '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates/human-ai-iteration-v1.png' '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2/human-ai-iteration.png'
cp '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates/governed-delivery-system-v1.png' '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2/governed-delivery-system.png'
cp '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates/verifiable-delivery-loop-v1.png' '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2/verifiable-delivery-loop.png'
cp '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/candidates/closing-ai-handoff-v1.png' '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2/closing-ai-handoff.png'
```

不合格时只针对一个问题生成 `-v2`，保留 v1。最终 `assets/image2/` 必须恰好七张 PNG。

- [ ] **Step 5: 更新素材证据账本**

用 `apply_patch` 更新 `asset-prompts.txt`：为每张选中图记录 `slide`、`model=gpt-image-2`、`route=CRS API`、提示词、候选文件、选中稳定路径、是否迭代和检查结论。不得记录 `CRS_KEY`、Authorization header 或密钥长度。

---

### Task 4: 建立可维护的原生 PPT 构建器

**Files:**

- Create: `src/theme.mjs`
- Create: `src/assets.mjs`
- Create: `src/notes.mjs`
- Create: `src/registry.mjs`
- Create: `src/verify-contract.mjs`
- Create: `src/build-deck.mjs`

- [ ] **Step 1: 创建主题与低层 helper**

`theme.mjs` 必须导出以下接口：

```js
export const SLIDE_SIZE = Object.freeze({ width: 1280, height: 720 });
export const COLORS = Object.freeze({
  warmWhite: "#F7F8FC",
  white: "#FFFFFF",
  paleBlue: "#EEF2F8",
  graphite: "#151821",
  secondary: "#5C6475",
  periwinkle: "#6377FF",
  aqua: "#55D6C2",
  coral: "#FF8A6B",
  deep: "#171A27",
  line: "#D8DDE8",
});
export const FONTS = Object.freeze({ zh: "PingFang SC", en: "Helvetica Neue" });

export function addText(slide, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name: style.name,
    position,
    fill: style.fill ?? "none",
    line: style.line ?? { style: "solid", fill: "none", width: 0 },
    borderRadius: style.borderRadius,
  });
  shape.text = text;
  shape.text.style = {
    typeface: style.typeface ?? FONTS.zh,
    fontSize: style.fontSize ?? 24,
    bold: style.bold ?? false,
    color: style.color ?? COLORS.graphite,
    alignment: style.alignment ?? "left",
    verticalAlignment: style.verticalAlignment ?? "top",
    lineSpacing: style.lineSpacing ?? 1.08,
    insets: style.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
    autoFit: "none",
    wrap: "square",
  };
  return shape;
}

export function addRule(slide, position, style = {}) {
  return slide.shapes.add({
    geometry: "line",
    position,
    fill: "none",
    line: { style: style.dash ?? "solid", fill: style.color ?? COLORS.line, width: style.width ?? 2 },
  });
}

export function addSemanticNode(slide, text, position, style = {}) {
  return addText(slide, text, position, {
    fill: style.fill ?? COLORS.white,
    line: { style: "solid", fill: style.stroke ?? COLORS.line, width: style.lineWidth ?? 1.5 },
    borderRadius: style.borderRadius ?? 14,
    fontSize: style.fontSize ?? 22,
    bold: style.bold ?? true,
    color: style.color ?? COLORS.graphite,
    alignment: style.alignment ?? "center",
    verticalAlignment: "middle",
    insets: { top: 8, right: 10, bottom: 8, left: 10 },
    name: style.name,
  });
}

export function addSlideTitle(slide, text, options = {}) {
  if (text.includes("\n")) throw new Error(`Slide title must remain one line: ${text}`);
  return addText(slide, text, options.position ?? { left: 72, top: 50, width: 1136, height: 66 }, {
    name: options.name,
    fontSize: options.fontSize ?? 50,
    bold: true,
    color: options.color ?? COLORS.graphite,
    lineSpacing: 0.96,
  });
}

export function addFooter(slide, physical, appendix = null) {
  if (physical === 1) return;
  addText(slide, appendix ? `附录 A${appendix}` : String(physical).padStart(2, "0"),
    { left: 72, top: 680, width: 150, height: 20 },
    { fontSize: 15, bold: Boolean(appendix), color: appendix ? COLORS.periwinkle : COLORS.secondary });
  addText(slide, "AI × PRODUCT × DELIVERY",
    { left: 930, top: 680, width: 278, height: 20 },
    { fontSize: 13, color: COLORS.secondary, alignment: "right", typeface: FONTS.en });
}
```

禁止导出 `addAmbient`、`addFlowNode`、默认阴影卡片或装饰圆点 helper。`addSemanticNode` 只用于确有边界意义的 Gate、版本或对象。

- [ ] **Step 2: 创建素材加载与唯一使用合同**

`assets.mjs` 必须导出：

```js
import fs from "node:fs/promises";
import path from "node:path";

const ASSET_ROOT = "/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2";
const PROTOTYPE08 = "/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/产品代码/prototypes/08-content-full-deck-review-v7-inline-feedback.jpg";

export const IMAGE2_USAGE = Object.freeze({
  1: "cover-ai-collaboration.png",
  5: "executor-shift.png",
  6: "design-misjudgment.png",
  9: "human-ai-iteration.png",
  12: "governed-delivery-system.png",
  16: "verifiable-delivery-loop.png",
  19: "closing-ai-handoff.png",
});

const usedImage2 = new Set();

async function addRaster(slide, filePath, position, options = {}) {
  const bytes = await fs.readFile(filePath);
  const blob = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  return slide.images.add({
    blob,
    contentType: options.contentType ?? (filePath.endsWith(".jpg") ? "image/jpeg" : "image/png"),
    alt: options.alt,
    prompt: options.prompt,
    fit: options.fit ?? "cover",
    position,
    crop: options.crop,
    geometry: options.geometry ?? "rect",
    borderRadius: options.borderRadius,
  });
}

export async function addImage2(slide, physical, position, options = {}) {
  const fileName = IMAGE2_USAGE[physical];
  if (!fileName) throw new Error(`Physical slide ${physical} has no Image 2 contract`);
  if (usedImage2.has(fileName)) throw new Error(`Image 2 asset reused: ${fileName}`);
  usedImage2.add(fileName);
  return addRaster(slide, path.join(ASSET_ROOT, fileName), position, options);
}

export async function addPrototype08(slide, position, options = {}) {
  return addRaster(slide, PROTOTYPE08, position, { ...options, contentType: "image/jpeg" });
}

export function assertAllImage2UsedExactlyOnce() {
  const expected = Object.values(IMAGE2_USAGE);
  if (new Set(expected).size !== 7) throw new Error("Image 2 contract must contain seven unique files");
  if (usedImage2.size !== 7) throw new Error(`Expected seven Image 2 assets in the deck, got ${usedImage2.size}`);
}
```

`addImage2` 必须维护已使用集合；相同文件第二次使用时抛错。08 原型不进入 Image 2 使用集合。

- [ ] **Step 3: 创建来源备注矩阵**

`notes.mjs` 必须导出 `SOURCE_PATHS`、`sourcesForContentId(contentId, physical)` 和：

```js
export function addSourcesNotes(slide, { sources, speakerCue, boundary }) {
  if (!Array.isArray(sources) || sources.length === 0) {
    throw new Error("Every slide requires a non-empty sources array");
  }
  slide.speakerNotes.textFrame.setText([
    `[Speaker cue]\n${speakerCue}`,
    `[Boundary]\n${boundary}`,
    "[Sources]",
    ...sources.map((source, index) => `${index + 1}. ${source}`),
  ].join("\n\n"));
}
```

物理第 1、5、6、9、12、16、19 页必须增加 `asset-prompts.txt`；第 10 页增加当前 Git 时间点；第 11 页增加 08 原型；目标合同声明增加对应产品/系统/UI 基线。

- [ ] **Step 4: 创建注册表与纯合同检查**

`registry.mjs` 必须定义 27 个具名 builder 并导出：

```js
import {
  addMain01Cover, addMain02StartingPoint, addMain03PptDefinition,
  addMain04GenerateVsDeliver, addMain05ExecutorShift, addMain06DesignMisjudgment,
  addMain07WhyAiUnderstandsDesign, addMain08EngineeringDesignKnowledge,
  addMain09HumanAiDevelopmentLoop, addMain10FiveDefinitions,
} from "./slides-main-01-10.mjs";
import {
  addMain11ProductBecomesLight, addMain12ProductDefinition,
  addMain13FourLayerArchitecture, addMain14GateOverview,
  addMain15ExperienceObject, addMain16AiEraMvp,
  addMain17RequirementDrift, addMain18TraditionalSoftwareRole,
  addMain19Closing,
} from "./slides-main-11-19.mjs";
import {
  addAppendixA1RoleResponsibility, addAppendixA2EvidenceFirst,
  addAppendixA3FactsCannotBeInferred, addAppendixA4MissionToG0,
  addAppendixA5G1ToG2, addAppendixA6G3ToG4,
  addAppendixA7ExperienceEvolution, addAppendixA8SingleSourceOfTruth,
} from "./slides-appendix.mjs";

export const MAIN_CONTENT_IDS = Object.freeze([1,2,3,4,5,6,7,8,9,10,14,15,16,17,21,23,24,26,27]);
export const APPENDIX_CONTENT_IDS = Object.freeze([11,12,13,18,19,20,22,25]);
export const PHYSICAL_CONTENT_IDS = Object.freeze([...MAIN_CONTENT_IDS, ...APPENDIX_CONTENT_IDS]);
export const SLIDE_BUILDERS = Object.freeze([
  { physical: 1, contentId: 1, role: "main-cover", build: addMain01Cover },
  { physical: 2, contentId: 2, role: "main", build: addMain02StartingPoint },
  { physical: 3, contentId: 3, role: "main", build: addMain03PptDefinition },
  { physical: 4, contentId: 4, role: "main", build: addMain04GenerateVsDeliver },
  { physical: 5, contentId: 5, role: "main", build: addMain05ExecutorShift },
  { physical: 6, contentId: 6, role: "main", build: addMain06DesignMisjudgment },
  { physical: 7, contentId: 7, role: "main", build: addMain07WhyAiUnderstandsDesign },
  { physical: 8, contentId: 8, role: "main", build: addMain08EngineeringDesignKnowledge },
  { physical: 9, contentId: 9, role: "main", build: addMain09HumanAiDevelopmentLoop },
  { physical: 10, contentId: 10, role: "main", build: addMain10FiveDefinitions },
  { physical: 11, contentId: 14, role: "main", build: addMain11ProductBecomesLight },
  { physical: 12, contentId: 15, role: "main", build: addMain12ProductDefinition },
  { physical: 13, contentId: 16, role: "main", build: addMain13FourLayerArchitecture },
  { physical: 14, contentId: 17, role: "main", build: addMain14GateOverview },
  { physical: 15, contentId: 21, role: "main", build: addMain15ExperienceObject },
  { physical: 16, contentId: 23, role: "main", build: addMain16AiEraMvp },
  { physical: 17, contentId: 24, role: "main", build: addMain17RequirementDrift },
  { physical: 18, contentId: 26, role: "main", build: addMain18TraditionalSoftwareRole },
  { physical: 19, contentId: 27, role: "main-closing", build: addMain19Closing },
  { physical: 20, contentId: 11, role: "appendix", appendixNumber: 1, build: addAppendixA1RoleResponsibility },
  { physical: 21, contentId: 12, role: "appendix", appendixNumber: 2, build: addAppendixA2EvidenceFirst },
  { physical: 22, contentId: 13, role: "appendix", appendixNumber: 3, build: addAppendixA3FactsCannotBeInferred },
  { physical: 23, contentId: 18, role: "appendix", appendixNumber: 4, build: addAppendixA4MissionToG0 },
  { physical: 24, contentId: 19, role: "appendix", appendixNumber: 5, build: addAppendixA5G1ToG2 },
  { physical: 25, contentId: 20, role: "appendix", appendixNumber: 6, build: addAppendixA6G3ToG4 },
  { physical: 26, contentId: 22, role: "appendix", appendixNumber: 7, build: addAppendixA7ExperienceEvolution },
  { physical: 27, contentId: 25, role: "appendix", appendixNumber: 8, build: addAppendixA8SingleSourceOfTruth },
]);
```

`verify-contract.mjs` 不创建 Presentation，使用以下完整检查：

```js
import { IMAGE2_USAGE } from "./assets.mjs";
import {
  MAIN_CONTENT_IDS,
  APPENDIX_CONTENT_IDS,
  PHYSICAL_CONTENT_IDS,
  SLIDE_BUILDERS,
} from "./registry.mjs";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(MAIN_CONTENT_IDS.length === 19, "Main deck must contain 19 slides");
assert(APPENDIX_CONTENT_IDS.length === 8, "Appendix must contain 8 slides");
assert(PHYSICAL_CONTENT_IDS.length === 27, "Deck must contain 27 slides");
assert(PHYSICAL_CONTENT_IDS[18] === 27, "Physical slide 19 must be content 27");
assert(PHYSICAL_CONTENT_IDS[19] === 11, "Physical slide 20 must be content 11");
assert(SLIDE_BUILDERS.length === 27, "Registry must contain 27 builders");
assert(new Set(PHYSICAL_CONTENT_IDS).size === 27, "Content IDs must be unique");
assert(new Set(SLIDE_BUILDERS.map(({ build }) => build.name)).size === 27, "Builder names must be unique");
assert(SLIDE_BUILDERS[18].role === "main-closing", "Physical slide 19 must be main-closing");

for (let index = 0; index < SLIDE_BUILDERS.length; index += 1) {
  const entry = SLIDE_BUILDERS[index];
  assert(entry.physical === index + 1, `Physical number mismatch at ${index + 1}`);
  assert(entry.contentId === PHYSICAL_CONTENT_IDS[index], `Content order mismatch at ${index + 1}`);
  if (index < 19) assert(entry.role !== "appendix", `Main slide ${index + 1} cannot be appendix`);
  if (index >= 19) assert(entry.appendixNumber === index - 18, `Appendix number mismatch at ${index + 1}`);
}

assert(Object.keys(IMAGE2_USAGE).join(",") === "1,5,6,9,12,16,19", "Image 2 physical pages must match the approved contract");
assert(new Set(Object.values(IMAGE2_USAGE)).size === 7, "Image 2 files must be unique");

console.log("main=19");
console.log("appendix=8");
console.log("total=27");
console.log("physical19=27");
console.log("physical20=11");
console.log("image2=7");
console.log("contract=pass");
```

- [ ] **Step 5: 创建 build entry**

每个 slide builder 接收 `(presentation, entry)`，创建并返回一个 slide。`build-deck.mjs` 使用以下完整入口：

```js
import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";
import { SLIDE_SIZE, COLORS } from "./theme.mjs";
import { assertAllImage2UsedExactlyOnce } from "./assets.mjs";
import { MAIN_CONTENT_IDS, APPENDIX_CONTENT_IDS, SLIDE_BUILDERS } from "./registry.mjs";

const OUTPUT_DIR = "/private/tmp/codex-ai-native-friends-deck-20260817-v4/output";
const OUTPUT_PPTX = path.join(OUTPUT_DIR, "当 AI 开始负责交付.pptx");

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const presentation = Presentation.create({ slideSize: SLIDE_SIZE });
  presentation.theme.colorScheme = {
    name: "AI Product Experiment Editorial",
    themeColors: {
      accent1: COLORS.periwinkle, accent2: COLORS.aqua, accent3: COLORS.coral,
      accent4: "#9A77FF", accent5: "#4CA5FF", accent6: "#8CBF61",
      bg1: COLORS.warmWhite, bg2: COLORS.paleBlue,
      tx1: COLORS.graphite, tx2: COLORS.secondary,
      dk1: COLORS.deep, dk2: "#242A42",
      lt1: COLORS.white, lt2: COLORS.paleBlue,
      hlink: COLORS.periwinkle, folHlink: "#9A77FF",
    },
  };

  for (const entry of SLIDE_BUILDERS) {
    const slide = await entry.build(presentation, entry);
    if (!slide) throw new Error(`Builder returned no slide: ${entry.build.name}`);
  }

  if (presentation.slides.items.length !== 27) throw new Error("Expected 27 slides");
  if (MAIN_CONTENT_IDS.length !== 19 || APPENDIX_CONTENT_IDS.length !== 8) throw new Error("Expected 19 main slides and 8 appendix slides");
  if (SLIDE_BUILDERS[18].role !== "main-closing") throw new Error("Physical slide 19 must be main-closing");
  assertAllImage2UsedExactlyOnce();

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(OUTPUT_DIR, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(OUTPUT_DIR, `${stem}.layout.json`), await layout.text());
  }

  await writeBlob(path.join(OUTPUT_DIR, "artifact-tool-montage.webp"), await presentation.export({
    format: "webp",
    montage: { format: "webp", columns: 5, background: COLORS.warmWhite },
    scale: 1,
  }));

  const snapshot = await presentation.inspect({ kind: "deck,slide,textbox,shape,image,table,notes,layout", maxChars: 500000 });
  await fs.writeFile(path.join(OUTPUT_DIR, "deck-inspect.ndjson"), snapshot.ndjson);
  const sources = (snapshot.ndjson.match(/\[Sources\]/g) ?? []).length;
  if (sources !== 27) throw new Error(`Expected 27 source blocks, got ${sources}`);

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(OUTPUT_PPTX);
  console.log(JSON.stringify({ main: 19, appendix: 8, total: 27, physical19: 27, physical20: 11, sources, image2: 7, output: OUTPUT_PPTX }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
```

---

### Task 5: 重构物理第 1–10 页的杂志化主分享

**Files:**

- Create: `src/slides-main-01-10.mjs`

| 物理页 | Function | 必须实现的方案 A 构图 | 禁止回退 |
|---:|---|---|---|
| 1 | `addMain01Cover` | 全幅封面图；左侧超大两行标题、短副标题、姓名日期；无页脚 | 不做右侧小图卡，不放功能列表 |
| 2 | `addMain02StartingPoint` | 三段斜向叙事从稀疏走向失控；第三段以珊瑚划痕和大句收束 | 不做三张等宽卡片 |
| 3 | `addMain03PptDefinition` | “推动一次真实决策”作为唯一核心；五层以纵深纸面/基线展开 | 不做五张卡片或圆形中心图 |
| 4 | `addMain04GenerateVsDeliver` | 一条由轻到重的责任链；后三段占更大视觉权重 | 不做七个等尺寸节点 |
| 5 | `addMain05ExecutorShift` | Image 2 全幅/大幅裁切；原生文字只标人、AI、软件三种责任 | 不做左右表格；不画人形 |
| 6 | `addMain06DesignMisjudgment` | Image 2 左乱右序；超大“AI 不懂设计”被珊瑚划掉；三句认知转折沿变化方向排布 | 不用三张认知卡 |
| 7 | `addMain07WhyAiUnderstandsDesign` | 五个超大动词形成编辑式字场；设计词作为低权重背景 | 不做五个圆点/徽章 |
| 8 | `addMain08EngineeringDesignKnowledge` | 一条知识固化轨迹，文本随轨迹分层；收束句独占底部 | 不做上下两排八节点 |
| 9 | `addMain09HumanAiDevelopmentLoop` | Image 2 不完美循环；原生标签标注人判断、AI 执行、证据 | 不做七节点圆环 |
| 10 | `addMain10FiveDefinitions` | 真实 Git HEAD/数量/日期作为证据；五个阶段数字大小不均、沿演进轨迹展开 | 不做均匀时间线和五卡片 |

- [ ] **Step 1: 实现第 1–4 页并运行语法检查**

Run:

```bash
$RUNTIME_NODE --check '/private/tmp/codex-ai-native-friends-deck-20260817-v4/src/slides-main-01-10.mjs'
```

Expected: exit 0；四页标题保持单行；仍不执行 builder。

- [ ] **Step 2: 实现第 5–7 页并运行语法检查**

三页使用两张不同 Image 2 与一张纯排版页；所有图内无文字，原生文字可编辑。

Expected: exit 0；第 5/6 页分别登记 Image 2 物理页 5/6。

- [ ] **Step 3: 实现第 8–10 页并运行纯合同检查**

Run:

```bash
$RUNTIME_NODE '/private/tmp/codex-ai-native-friends-deck-20260817-v4/src/verify-contract.mjs'
```

Expected: 在全注册表完成前明确报告缺失页，不创建 PPTX；完成注册表后输出 `contract=pass`。

---

### Task 6: 重构物理第 11–19 页并锁定正式收尾

**Files:**

- Create: `src/slides-main-11-19.mjs`

| 物理页 | Function | 必须实现的方案 A 构图 | 事实边界 |
|---:|---|---|---|
| 11 | `addMain11ProductBecomesLight` | 08 原型大幅局部 + 被删除的复杂度痕迹 + 对话/两审核页/Runtime 收敛 | 显示“已确认交互参考，不代表真实 Runtime / 宿主验收” |
| 12 | `addMain12ProductDefinition` | 深色 Image 2 + 一句产品定义；AI/人/系统责任以三条原生文字排布 | 明示目标合同与待迁移边界进入备注 |
| 13 | `addMain13FourLayerArchitecture` | 四层使用纵深、不同宽度和真实交付方向；治理层横向托底 | 不声称全部层已最终完成 |
| 14 | `addMain14GateOverview` | 一条穿过 Mission/G0–G4/复盘的门槛轨道；Gate 有清晰门槛语义 | 不做七张等宽卡片 |
| 15 | `addMain15ExperienceObject` | 一个被放大的经验对象；字段用编辑式标注线展开 | 经验可降级、拆分、回滚 |
| 16 | `addMain16AiEraMvp` | Image 2 不完整闭环 + `Minimum Verifiable Delivery Loop` 大定义 | macOS 当前目标；Windows/WPS deferred |
| 17 | `addMain17RequirementDrift` | 六个真相源以不同张力拉扯实现；中心结果不是卡片 | 测试不证明最新需求或真实验收 |
| 18 | `addMain18TraditionalSoftwareRole` | 原生对比表去除 Office 默认感；底部治理骨架为视觉主轴 | 不表达传统软件落后或被取代 |
| 19 | `addMain19Closing` | 独立收尾 Image 2；右侧结论与开放问题；左侧三方责任汇合 | 不写谢谢；不提示附录；不复用封面 |

- [ ] **Step 1: 实现第 11–14 页**

连接线先于 Gate/层对象创建；08 原型只裁切展示真实存在的局部，不修改原图内容。

- [ ] **Step 2: 实现第 15–18 页**

第 18 页使用原生 PowerPoint table 或等价的原生行列对象，正文不小于 22 px；视觉重点在“治理骨架”。

- [ ] **Step 3: 实现第 19 页并增加收尾断言**

Required code:

```js
if (PHYSICAL_CONTENT_IDS[18] !== 27) throw new Error("Physical slide 19 must be content 27");
if (SLIDE_BUILDERS[18].role !== "main-closing") throw new Error("Physical slide 19 must be the formal closing");
```

Run `node --check`；仍不 authoring。

---

### Task 7: 重构附录 A1–A8

**Files:**

- Create: `src/slides-appendix.mjs`

| 附录 | Function | 构图合同 |
|---|---|---|
| A1 | `addAppendixA1RoleResponsibility` | 超大错误编号 01；旧假设淡出，责任证据与 later choice 进入；保留 `isolated-review-task` |
| A2 | `addAppendixA2EvidenceFirst` | 上方旧链退灰，下方证据先行链成为主轴；不做两排卡片 |
| A3 | `addAppendixA3FactsCannotBeInferred` | Mission/G0 不等式 + Review Bridge 事实轨道；每一步允许独立失败 |
| A4 | `addAppendixA4MissionToG0` | 内容责任轨道，G0 是唯一突出门；技术对象全名进备注 |
| A5 | `addAppendixA5G1ToG2` | 视觉合同轨道，设计硬门/工程硬门为双门；不显示用户确认图标 |
| A6 | `addAppendixA6G3ToG4` | 人类确认点使用珊瑚；真实 PowerPoint、hash、送达和用户验收分开 |
| A7 | `addAppendixA7ExperienceEvolution` | 晋升与回滚双向同等可见；不画单向永远进化循环 |
| A8 | `addAppendixA8SingleSourceOfTruth` | 最新决定到真实证据的单一传播链；保持附录身份，不做第二次结束 |

- [ ] **Step 1: 实现 A1–A3 并检查文案边界**

Run:

```bash
rg -n '多 Agent 已证明|已理解.*已完成|ready.*证明已打开' \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/src/slides-appendix.mjs'
```

Expected: no misleading match；A1 明确独立实例证据边界。

- [ ] **Step 2: 实现 A4–A6 的连续 Gate 轨道**

三页共享线条语义，但每页主门、信息重心和留白不同；不得复制同一六节点模板。

- [ ] **Step 3: 实现 A7–A8 并锁定附录编号**

Required check:

```js
for (let index = 19; index < 27; index += 1) {
  const expected = index - 18;
  if (SLIDE_BUILDERS[index].appendixNumber !== expected) {
    throw new Error(`Expected appendix A${expected} at physical slide ${index + 1}`);
  }
}
```

---

### Task 8: 首次 authoring 前的静态审查

**Files:**

- Inspect: all `src/*.mjs`
- Create: `/private/tmp/codex-ai-native-friends-deck-20260817-v4/qa/static-check.txt`

- [ ] **Step 1: 检查所有 JavaScript 语法**

Run:

```bash
for file in /private/tmp/codex-ai-native-friends-deck-20260817-v4/src/*.mjs; do
  "$RUNTIME_NODE" --check "$file"
done
```

Expected: every file exit 0。

- [ ] **Step 2: 运行纯合同测试**

Run:

```bash
$RUNTIME_NODE '/private/tmp/codex-ai-native-friends-deck-20260817-v4/src/verify-contract.mjs'
```

Expected:

```text
main=19
appendix=8
total=27
physical19=27
physical20=11
image2=7
contract=pass
```

- [ ] **Step 3: 扫描旧弱视觉模式和禁用文案**

Run:

```bash
rg -n -i \
  'addAmbient|addFlowNode|卡片墙|dashboard|robot|humanoid|binary rain|T(BD)|T(ODO)|place(holder)|lorem|click to|兼容 Windows|兼容 WPS|四个目标已通过' \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/src'
```

Expected: no match。允许在 Image 2 alt text 中出现“no robot”等否定描述时，记录具体文件/行并确认不属于可见文案。

- [ ] **Step 4: 验证素材和来源矩阵**

Run:

```bash
find '/private/tmp/codex-ai-native-friends-deck-20260817-v4/assets/image2' -maxdepth 1 -type f -name '*.png' | wc -l
```

Expected: `7`。静态检查还必须证明每个物理页都有非空 source array。

---

### Task 9: 首次 authoring、PPTX 导出与结构检查

**Files:**

- Execute: `src/build-deck.mjs`
- Create: one PPTX, 27 Artifact Tool PNGs, 27 layout JSONs, montage and inspect NDJSON

- [ ] **Step 1: 立即在首次 authoring 前运行 marker，且只运行一次**

Run with current runtime variables:

```bash
RUNTIME_NODE="$RUNTIME_NODE" \
RUNTIME_NODE_MODULES="$RUNTIME_NODE_MODULES" \
RUNTIME_BIN_DIR="$RUNTIME_BIN_DIR" \
"$RUNTIME_NODE" \
"$SKILL_DIR/container_tools/mark_artifact_operation_started.mjs" \
--operation-kind create \
--expected-output-count 1 \
--output-format pptx
```

Expected: success。任何重建或 QA 修复都不得重复 marker。

- [ ] **Step 2: 立即运行 v4 builder**

Run:

```bash
RUNTIME_NODE="$RUNTIME_NODE" \
RUNTIME_NODE_MODULES="$RUNTIME_NODE_MODULES" \
RUNTIME_BIN_DIR="$RUNTIME_BIN_DIR" \
"$RUNTIME_NODE" \
'/private/tmp/codex-ai-native-friends-deck-20260817-v4/src/build-deck.mjs'
```

Expected: 一个非空 PPTX、27 个 PNG、27 个 layout JSON、一个 montage、一个 inspect NDJSON；summary 显示 19/8/27、physical19=27、physical20=11、sources=27、image2=7。

- [ ] **Step 3: 检查输出数量和 PPTX zip 结构**

Run:

```bash
test -s '/private/tmp/codex-ai-native-friends-deck-20260817-v4/output/当 AI 开始负责交付.pptx'
find '/private/tmp/codex-ai-native-friends-deck-20260817-v4/output' -name 'slide-*.png' | wc -l
find '/private/tmp/codex-ai-native-friends-deck-20260817-v4/output' -name 'slide-*.layout.json' | wc -l
unzip -l '/private/tmp/codex-ai-native-friends-deck-20260817-v4/output/当 AI 开始负责交付.pptx' | rg 'ppt/slides/slide[0-9]+\.xml' | wc -l
```

Expected: `27`, `27`, `27`。

---

### Task 10: PowerPoint 渲染、自动检查与整套节奏检查

**Files:**

- Create: rendered slide directory
- Create: `/private/tmp/codex-ai-native-friends-deck-20260817-v4/qa/deck-montage.webp`

- [ ] **Step 1: 使用 bundled renderer 渲染 27 页**

Run:

```bash
RUNTIME_NODE="$RUNTIME_NODE" \
RUNTIME_NODE_MODULES="$RUNTIME_NODE_MODULES" \
RUNTIME_BIN_DIR="$RUNTIME_BIN_DIR" \
"$RUNTIME_PYTHON" \
"$SKILL_DIR/container_tools/render_slides.py" \
'/private/tmp/codex-ai-native-friends-deck-20260817-v4/output/当 AI 开始负责交付.pptx'
```

Expected: `slide-1.png` through `slide-27.png`。

- [ ] **Step 2: 创建渲染 montage**

Run:

```bash
"$RUNTIME_PYTHON" \
"$SKILL_DIR/container_tools/create_montage.py" \
--input_dir '/private/tmp/codex-ai-native-friends-deck-20260817-v4/output/当 AI 开始负责交付' \
--output_file '/private/tmp/codex-ai-native-friends-deck-20260817-v4/qa/deck-montage.webp'
```

Expected: 缩略图 19 明显收尾，缩略图 20 才出现附录；七张 Image 2 页分布均匀且不形成连续生成图画册。

- [ ] **Step 3: 运行溢出检查**

Run:

```bash
RUNTIME_NODE="$RUNTIME_NODE" \
RUNTIME_NODE_MODULES="$RUNTIME_NODE_MODULES" \
RUNTIME_BIN_DIR="$RUNTIME_BIN_DIR" \
"$RUNTIME_PYTHON" \
"$SKILL_DIR/container_tools/slides_test.py" \
'/private/tmp/codex-ai-native-friends-deck-20260817-v4/output/当 AI 开始负责交付.pptx'
```

Expected: no overflow。任何 warning 必须映射到具体物理页并全尺寸查看。

- [ ] **Step 4: 扫描 inspect**

Run:

```bash
rg -n -i \
  'T(BD)|T(ODO)|lorem|place(holder)|click to|兼容 Windows|兼容 WPS|四个目标已通过|继续看附录' \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/output/deck-inspect.ndjson'
```

Expected: no match；`[Sources]` count = 27。

---

### Task 11: 27 页全尺寸视觉 QA 与修复

**Files:**

- Create: `/private/tmp/codex-ai-native-friends-deck-20260817-v4/qa/qa-ledger.txt`
- Modify: v4 `src/*.mjs`

- [ ] **Step 1: 先查看整套 montage**

用 `view_image` 检查：视觉像互联网电子杂志而非产品说明；相邻页轮廓变化；七张生成图构图不同；深色页不连续；第 19 页正式结束；附录是同一系统但不抢主线。

- [ ] **Step 2: 逐张全尺寸查看物理第 1–10 页**

每页记录 `pass` 或具体问题，重点检查：Image 2 裁切、标题单行、大字可读、斜向叙事、原生文字与图像留白、Git 证据口径、是否仍有卡片墙感。

- [ ] **Step 3: 逐张全尺寸查看物理第 11–19 页**

重点检查：08 原型边界标签、深色产品定义、四层纵深、Gate 轨道、经验标注线、MVP 不完整闭环、对比表字号和第 19 页收尾。确认第 19 页没有“谢谢”或附录提示。

- [ ] **Step 4: 逐张全尺寸查看附录 A1–A8**

确认错误编号、事实链和三张 Gate 页不使用同一模板；A7 晋升/回滚同等可见；A8 保持附录身份。

- [ ] **Step 5: 修复所有问题，不重复 marker**

使用 `apply_patch` 修改源文件；优先缩短可见文案、改变构图或裁切，不把正文缩小到 22 px 以下。每次修复后重新运行 builder、renderer 和受影响页全尺寸检查。

- [ ] **Step 6: 最终重跑全套检查**

重复 Task 8 的静态合同、Task 9 builder、Task 10 render/montage/overflow/inspect，但不重复 marker。`qa-ledger.txt` 必须包含物理第 1–27 页最终 `pass`。

---

### Task 12: 最终交付与事实说明

**Files:**

- Create: `/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx`

- [ ] **Step 1: 复制最终 PPTX 并核对哈希**

Run:

```bash
cp \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/output/当 AI 开始负责交付.pptx' \
  '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx'
shasum -a 256 \
  '/private/tmp/codex-ai-native-friends-deck-20260817-v4/output/当 AI 开始负责交付.pptx' \
  '/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app/分享材料/当 AI 开始负责交付.pptx'
```

Expected: 两个 SHA-256 完全相同。除用户另行要求，不把二进制 PPTX、生成图或 v4 临时源码提交到 Git。

- [ ] **Step 2: 交付说明保持事实分层**

最终说明必须包含：

- 19 页主分享 + 8 页附录；第 19 页自然结束；
- 7 张图通过 CRS API 的 `gpt-image-2` 生成，提示词记录在本地临时证据文件；
- 语义关系原生可编辑；
- 已完成 27 页渲染、溢出、inspect、montage 和逐页全尺寸 QA；
- 没有把 v2.2 目标合同包装成全部已实现；
- 本轮技术 QA 不称为 AI PPT Studio G2/G4，也不称为真实 macOS PowerPoint 正式验收。

---

## Plan self-review

- **Spec coverage:** 方案 A、七张 Image 2、CRS 路由、页面家族、19+8 顺序、事实边界和原生可编辑要求均有对应任务。
- **CRS boundary:** Base URL 从当前桌面任务的 CRS provider 配置读取；普通终端配置保持独立；只检查 `CRS_KEY` 是否存在；命令不打印、持久化或记录密钥；失败不回退官方通道。
- **Image 2 boundary:** 七个不同任务使用七个独立 job；生成图不包含文字或语义流程；每张只使用一次并全尺寸检查。
- **Visual upgrade:** v4 不复用 v3 builder；禁止 `addAmbient`、`addFlowNode` 和默认卡片 helper；主要页面轮廓逐页明确。
- **Native editability:** 责任、流程、Gate、架构、表格和文字由 Artifact Tool 原生对象表达；08 原型与七张生成图是可替换位图。
- **Closing:** 物理第 19 页内容 ID 27、role `main-closing`；物理第 20 页才是 A1。
- **Marker:** 首次 builder authoring 前成功运行一次，之后任何修复不重复。
- **QA:** 27 页 Artifact Tool PNG/layout、bundled render、montage、overflow、inspect 和逐页全尺寸检查全部覆盖。
- **Privacy:** 不使用客户事实、凭据、Bearer token、未授权截图或敏感项目名；不在账本记录 CRS 密钥。
- **Incomplete-step scan:** 计划中没有未完成标记、未选择分支或“类似前面”的省略步骤；七个提示词、路径、命令、物理页和通过条件均已确定。

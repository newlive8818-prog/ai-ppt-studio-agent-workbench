# 《当 AI 开始负责交付》Guizang Web Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The user has already approved inline execution in the current session; do not dispatch subagents or pause for another execution-choice gate.

**Goal:** 基于 `guizang-ppt-skill` 的 Swiss 模板生成一份 `B · 瑞士国际主义 + IKB`、27 页、可直接演讲的单文件网页 PPT，其中物理第 1–19 页构成约 30 分钟的完整主讲，物理第 20–27 页为附录 A1–A8。

**Architecture:** 以 skill 自带 `assets/template-swiss.html` 为唯一运行底座，保留翻页、WebGL/ASCII、演讲者视图、备注、计时、观众屏同步、ESC 总览和低功耗运行时；只替换模板的示例页与 `SPEAKER_NOTES`。所有可见流程、责任、Gate 和架构关系使用 Swiss 登记版式中的 HTML/CSS 原生对象表达，不生成图片，不引入第二套视觉系统。

**Tech Stack:** 单文件 HTML、模板内联 CSS/JavaScript、Motion One 本地副本、Lucide CDN、guizang presenter runtime、Node.js 校验脚本、Codex in-app Browser。

---

## 文件边界

- Modify: `产品代码/docs/superpowers/specs/2026-08-16-ai-native-product-friends-sharing-deck-design.md`（只保留本轮已经写入的 guizang 路线修正，并做范围校验）
- Create: `产品代码/docs/superpowers/plans/2026-08-17-ai-native-product-friends-sharing-guizang-web-deck.md`（本计划）
- Create: `分享材料/当 AI 开始负责交付-guizang-swiss-web/index.html`（最终网页演示稿）
- Create: `分享材料/当 AI 开始负责交付-guizang-swiss-web/大纲-v1.md`（页序、版式、节奏、备注索引）
- Create: `分享材料/当 AI 开始负责交付-guizang-swiss-web/assets/motion.min.js`（来自 skill 的本地 Motion One 回退）
- Create: `分享材料/当 AI 开始负责交付-guizang-swiss-web/images/.gitkeep`（保留空图片目录，不默认生成图片）
- Preserve: `分享材料/当 AI 开始负责交付-朋友分享版.pptx`
- Preserve: `分享材料/当 AI 开始负责交付.pptx`

当前工作树包含大量既有修改；本计划不执行 `git reset`、`git clean`、全仓格式化或提交，也不改动上述文件边界之外的产品代码、测试、Widget、MCP 和四份产品基线。

### Task 1: 校验内容合同与创建交付骨架

- [ ] **Step 1: 校验已确认设计稿没有空占位符、冲突标记或 Markdown 空白错误**

Run:

```bash
git diff --check -- 产品代码/docs/superpowers/specs/2026-08-16-ai-native-product-friends-sharing-deck-design.md
rg -n "<<<<<<<|=======|>>>>>>>|TBD|TODO|\[必填\]" 产品代码/docs/superpowers/specs/2026-08-16-ai-native-product-friends-sharing-deck-design.md
```

Expected: `git diff --check` 无输出并返回 0；`rg` 不命中冲突标记和空占位符。历史方案中的“已废止”说明可以保留，但不得被当作本轮实施项。

- [ ] **Step 2: 验证设计稿引用的项目内相对路径存在**

Run: 使用一个只读 Node 脚本提取 Markdown 相对链接，并逐项检查目标是否存在。

Expected: 所有项目内相对链接均能解析；外部链接和纯锚点跳过。

- [ ] **Step 3: 创建隔离的分享目录并从 Swiss 模板复制运行时**

Create exactly:

```text
分享材料/当 AI 开始负责交付-guizang-swiss-web/
├── index.html
├── 大纲-v1.md
├── assets/
│   └── motion.min.js
└── images/
    └── .gitkeep
```

`index.html` 必须以 `<SKILL_ROOT>/assets/template-swiss.html` 为底座；`motion.min.js` 必须与 `<SKILL_ROOT>/assets/motion.min.js` 字节一致。

### Task 2: 制作 27 页 Swiss 演示稿

- [ ] **Step 1: 写入固定页面映射、主题节奏与版式合同**

| 物理页 | 内容 ID | `data-slide-id` | Sxx | 主题 | 主讲计划 |
|---:|---:|---|---|---|---:|
| 1 | 1 | `01-cover` | S01 | accent | 0.8 |
| 2 | 2 | `02-generation-gap` | S03 | light | 1.4 |
| 3 | 3 | `03-ppt-definition` | S05 | dark | 1.5 |
| 4 | 4 | `04-generation-vs-delivery` | S11 | light | 1.4 |
| 5 | 5 | `05-executor-shift` | S08 | dark | 1.5 |
| 6 | 6 | `06-design-misjudgment` | S09 | light | 1.2 |
| 7 | 7 | `07-ai-understands-design` | S13 | dark | 1.4 |
| 8 | 8 | `08-design-engineering` | S11 | light | 1.5 |
| 9 | 9 | `09-human-ai-development-loop` | S14 | dark | 1.5 |
| 10 | 10 | `10-five-product-definitions` | S11 | light | 1.6 |
| 11 | 14 | `11-lightweight-product` | S08 | dark | 1.4 |
| 12 | 15 | `12-product-definition` | S03 | accent | 1.4 |
| 13 | 16 | `13-four-layer-system` | S19 | light | 1.5 |
| 14 | 17 | `14-responsibility-gates` | S11 | dark | 1.6 |
| 15 | 21 | `15-experience-moat` | S16 | light | 1.4 |
| 16 | 23 | `16-verifiable-mvp` | S14 | dark | 1.4 |
| 17 | 24 | `17-truth-drift` | S13 | light | 1.3 |
| 18 | 26 | `18-software-governance` | S08 | dark | 1.5 |
| 19 | 27 | `19-closing-question` | S10 | split | 1.6 |
| 20 | 11 | `a1-role-overload` | S13 | light | — |
| 21 | 12 | `a2-conclusion-first` | S08 | dark | — |
| 22 | 13 | `a3-false-completion` | S11 | light | — |
| 23 | 18 | `a4-mission-to-g0` | S11 | dark | — |
| 24 | 19 | `a5-g1-to-g2` | S05 | light | — |
| 25 | 20 | `a6-g3-to-g4` | S11 | dark | — |
| 26 | 22 | `a7-experience-evolution` | S14 | light | — |
| 27 | 25 | `a8-single-source-of-truth` | S11 | dark | — |

主讲分钟合计为 26.9 分钟，不超过 30 分钟的 90% 预算；附录不写 `minutes`，不进入默认主讲预算。正文共使用 S03、S05、S08、S09、S11、S13、S14、S16、S19 九种登记版式，加封面 S01 与收尾 S10，共十一种 S 编号。

- [ ] **Step 2: 替换模板示例页**

Requirements:

- `<title>` 改为 `当 AI 开始负责交付 · AI PPT Studio 朋友分享`。
- 只使用模板现有类、登记 Sxx 骨架和必要的 inline style；不得新增风格 A 类名。
- 每页具有唯一 `data-slide-id`、`data-layout`、`data-animate` 和 `light` / `dark` / `accent` / `split` 主题身份。
- 封面用 IKB 满屏 ASCII 版；第 19 页用左 IKB + ASCII、右 paper takeaway 的正式收尾，并在右侧提出开放问题。
- 第 19 页不提示附录；第 20 页开始显示 `附录 A1`，第 27 页显示 `附录 A8`。
- 大字号使用 `min(Xvw, Yvh)` 双约束和 200–300 轻字重。
- 不使用新增渐变、阴影、圆角、多 accent、SVG `<text>`、虚构 KPI、百分比或 benchmark。
- `17 天 / 101 次提交 / 截至 2026-08-17 / HEAD 9aa0808` 只出现在第 10 页及其备注；备注明确“提交量只表示实验密度，不证明产品成功”。

- [ ] **Step 3: 写入 27 条 `SPEAKER_NOTES`**

Requirements:

- 顺序与 slide 完全一致，`id` 一一对应。
- 每条都包含 `id`、`title`、`purpose`、`talk`、`transition`；主讲页再包含 `section` 与 `minutes`。
- 主讲 `talk` 默认 3–5 条；附录保留 3 条短提词，不计入主讲分钟。
- 不写逐字稿，不新增未经来源支持的现场事实，不把 v2.2 目标合同描述成已经全部实现。
- 第 19 页的 `transition` 明确进入朋友讨论 / Q&A；A1–A8 只作为被点名追问时的备用深挖页。

- [ ] **Step 4: 生成 `大纲-v1.md`**

大纲逐页记录：物理页码、对外编号、内容 ID、slide ID、章节、Sxx、主题、页面目的、观众可见结论、建议时长、转场。文件开头注明主讲 19 页、附录 8 页、主讲计划 26.9 分钟与交付物为 guizang 网页 PPT，不是 PPTX。

### Task 3: 静态与运行时校验

- [ ] **Step 1: 运行 skill 原生校验器**

Run:

```bash
node <SKILL_ROOT>/scripts/validate-presenter-mode.mjs <DECK>/index.html --target-minutes 30
node <SKILL_ROOT>/scripts/check-presenter-runtime-sync.mjs
node <SKILL_ROOT>/scripts/validate-swiss-deck.mjs <DECK>/index.html
```

Expected: 27 slides / 27 notes；presenter runtime sync 通过；Swiss locked mode 通过。附录未设置 `minutes` 时 presenter 校验允许报告 partial timing，但主讲 1–19 页的手工合计必须保持 26.9 分钟。

- [ ] **Step 2: 按成品 checklist 做 P0 / P1 扫描**

生成成品后完整读取 `<SKILL_ROOT>/references/checklist.md`，逐项检查并修复。至少执行：

```bash
rg -n "\[必填\]|<<<<<<<|=======|>>>>>>>|<svg[\\s\\S]*<text|data-layout=\"P2[34]" <DECK>/index.html
```

并以脚本确认：27 个唯一 slide ID、27 个备注 ID、物理页 1–19 与 20–27 的边界、至少 8 个不同 Sxx、无连续三页相同主题、`images/` 没有未绑定图片、`motion.min.js` 与 skill 资产 hash 一致。

- [ ] **Step 3: 检查本轮文件范围**

Run:

```bash
git diff --check -- 产品代码/docs/superpowers/specs/2026-08-16-ai-native-product-friends-sharing-deck-design.md 产品代码/docs/superpowers/plans/2026-08-17-ai-native-product-friends-sharing-guizang-web-deck.md 分享材料/当\ AI\ 开始负责交付-guizang-swiss-web/index.html 分享材料/当\ AI\ 开始负责交付-guizang-swiss-web/大纲-v1.md
```

Expected: 无空白错误；没有覆盖既有两份 PPTX 或其他产品代码。

### Task 4: 浏览器逐页与演讲模式 QA

- [ ] **Step 1: 用 Codex in-app Browser 打开本地 `index.html`**

使用 Browser 的 DOM / accessibility 语义操作检查，不用 Computer Use。确认加载后浏览器控制台无本轮 HTML 引入的错误；网络字体或 CDN 不可用时，本地字体栈与本地 Motion 回退仍可工作。

- [ ] **Step 2: 检查观众视图**

在 1600×900 及一个小屏尺寸验证：27 页左右键翻页、滚轮/触屏不会造成纵向页面滚动、ESC 总览、B 低功耗切换、首页、主讲收尾、A1 起始页和 A8 尾页。逐页检查标题断行、文本溢出、底部导航安全区、直角/无阴影/单 accent、主题节奏和 Sxx 结构。

- [ ] **Step 3: 检查演讲者模式**

验证 `P` 进入演讲模式、当前/下一页预览保持 16:9、备注与页面一一对应、首页/上一页/下一页/尾页、ESC 宫格、计时开始/暂停/继续/重置、排练记录、观众屏打开/同步/关闭/重新打开，以及退出后观众屏关闭或显示结束遮罩。

- [ ] **Step 4: 修复并重跑全部校验**

任何 P0 / P1、运行时或视觉问题都在 `index.html` / `大纲-v1.md` 内修复；修复后重新运行 Task 3 的三条原生校验与本轮范围检查，直至无错误。

### Task 5: 交付

- [ ] **Step 1: 提供可点击的 `index.html` 与 `大纲-v1.md`**

交付说明必须准确称为“guizang 单文件网页 PPT”，不称为原生 PPTX；说明 `←/→`、`ESC`、`B`、`P` 四个最常用操作。

- [ ] **Step 2: 报告验证证据与边界**

说明 27 页、19+8 页序、26.9 分钟主讲备注预算、原生 validator 结果和浏览器 QA 结果；同时声明这些本地检查不等于 AI PPT Studio 的 G0–G4 或 macOS PowerPoint 正式验收。

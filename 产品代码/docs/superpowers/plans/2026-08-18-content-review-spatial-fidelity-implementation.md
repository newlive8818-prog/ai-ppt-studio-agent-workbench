# Content Review Spatial Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变内容审核业务合同的前提下，把 `ContentFullDeckReviewPage` 还原为 08 原型确认的紧凑连续阅读结构，并建立 `1280 × 720` 首屏几何验收和独立用户 UI 验收边界。

**Architecture:** 保留现有 React 业务组件、ContentReviewProjection、PageDecision、草稿和批次逻辑，只修改内容审核页的语义标识、页头/章节/deck intro DOM 与 CSS。空间合同由纯 Node 断言函数定义，由真实 Chromium runner 采集 bounding boxes 后调用；DOM 存在、浏览器几何、截图和用户验收分别记录。

**Tech Stack:** React 19、TypeScript、Vitest、Testing Library、Node.js test runner、Playwright、CSS、Markdown 验收记录。

---

## Scope and file ownership

**Create:**

- `产品代码/docs/validation/2026-08-18-content-review-spatial-fidelity-acceptance.md`：只记录本轮内容页证据和用户验收状态。

**Modify:**

- `产品代码/scripts/v22-ui-acceptance-evidence.mjs`：定义可单元测试的内容首屏空间合同。
- `产品代码/tests/v22-prototype-fidelity.test.mjs`：验证空间合同失败关闭，并确认 Browser runner 消费该合同。
- `产品代码/widget/src/content-review/ContentFullDeckReviewPage.test.tsx`：先冻结内容页语义结构和阅读顺序。
- `产品代码/widget/src/content-review/ContentReviewResponsive.test.tsx`：先冻结章节单行定位和现有 PageDecision 响应式合同。
- `产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx`：增加稳定语义标识、细进度轨和紧凑阅读文案；不改变数据写入。
- `产品代码/widget/src/styles/content-review.css`：还原紧凑页头、章节条、deck intro、章节头和首屏空间预算。
- `产品代码/scripts/run-v22-ui-acceptance.mjs`：增加 1280×720 实际 bounding-box 验收和首屏截图。

**Do not modify:**

- `产品代码/widget/src/visual-review/**`
- `产品代码/widget/src/styles/visual-review.css`
- `产品代码/src/ai_ppt_studio/**`
- `产品代码/mcp/**`
- PPT 运行数据目录

---

### Task 1: Add a fail-closed content spatial contract

**Files:**

- Modify: `产品代码/tests/v22-prototype-fidelity.test.mjs`
- Modify: `产品代码/scripts/v22-ui-acceptance-evidence.mjs`

- [ ] **Step 1: Write the failing Node tests**

Extend the import in `tests/v22-prototype-fidelity.test.mjs`:

```js
import {
  CONTENT_REVIEW_SPATIAL_CONTRACT,
  assertContentReviewSpatialFidelity,
} from "../scripts/v22-ui-acceptance-evidence.mjs";
```

Add a valid measurement helper and one test that verifies each approved limit fails closed:

```js
function validContentSpatialMeasurement() {
  return {
    viewport: { width: 1280, height: 720 },
    header: { x: 16, y: 0, width: 1248, height: 82 },
    chapterNav: { x: 16, y: 90, width: 1248, height: 48 },
    deckIntro: { x: 16, y: 146, width: 1248, height: 118 },
    firstChapterHeading: { x: 16, y: 276, width: 1248, height: 58 },
    firstSlideHeading: { x: 16, y: 342, width: 1248, height: 116 },
    firstReadingGrid: { x: 16, y: 458, width: 1248, height: 420 },
    scrollWidth: 1280,
    clientWidth: 1280,
  };
}

test("content spatial fidelity fails closed for oversized chrome, hidden first-page reading, and overflow", () => {
  assert.deepEqual(CONTENT_REVIEW_SPATIAL_CONTRACT, {
    viewport: { width: 1280, height: 720 },
    maxHeaderHeight: 96,
    maxChapterNavHeight: 64,
    maxDeckIntroHeight: 160,
  });
  assert.doesNotThrow(() => assertContentReviewSpatialFidelity(validContentSpatialMeasurement()));
  for (const invalid of [
    { header: { ...validContentSpatialMeasurement().header, height: 97 } },
    { chapterNav: { ...validContentSpatialMeasurement().chapterNav, height: 65 } },
    { deckIntro: { ...validContentSpatialMeasurement().deckIntro, height: 161 } },
    { firstReadingGrid: { ...validContentSpatialMeasurement().firstReadingGrid, y: 720 } },
    { scrollWidth: 1281 },
  ]) {
    assert.throws(() => assertContentReviewSpatialFidelity({
      ...validContentSpatialMeasurement(),
      ...invalid,
    }));
  }
});
```

- [ ] **Step 2: Run the Node test and verify RED**

Run:

```bash
node --test tests/v22-prototype-fidelity.test.mjs
```

Expected: FAIL because `CONTENT_REVIEW_SPATIAL_CONTRACT` and `assertContentReviewSpatialFidelity` are not exported.

- [ ] **Step 3: Implement the minimal pure contract**

Add to `scripts/v22-ui-acceptance-evidence.mjs` after `finiteViewport`:

```js
export const CONTENT_REVIEW_SPATIAL_CONTRACT = Object.freeze({
  viewport: Object.freeze({ width: 1280, height: 720 }),
  maxHeaderHeight: 96,
  maxChapterNavHeight: 64,
  maxDeckIntroHeight: 160,
});

export function assertContentReviewSpatialFidelity(measurement) {
  const viewport = finiteViewport(measurement?.viewport);
  const expected = CONTENT_REVIEW_SPATIAL_CONTRACT.viewport;
  if (viewport.width !== expected.width || viewport.height !== expected.height) {
    throw new Error(`Content spatial fidelity requires ${expected.width}x${expected.height}; received ${viewport.width}x${viewport.height}.`);
  }
  const header = finiteRect(measurement?.header, "Content header");
  const chapterNav = finiteRect(measurement?.chapterNav, "Content chapter navigation");
  const deckIntro = finiteRect(measurement?.deckIntro, "Content deck intro");
  const firstChapterHeading = finiteRect(measurement?.firstChapterHeading, "First chapter heading");
  const firstSlideHeading = finiteRect(measurement?.firstSlideHeading, "First slide heading");
  const firstReadingGrid = finiteRect(measurement?.firstReadingGrid, "First reading grid");
  if (header.height > CONTENT_REVIEW_SPATIAL_CONTRACT.maxHeaderHeight) throw new Error("Content header exceeds the spatial budget.");
  if (chapterNav.height > CONTENT_REVIEW_SPATIAL_CONTRACT.maxChapterNavHeight) throw new Error("Content chapter navigation exceeds the spatial budget.");
  if (deckIntro.height > CONTENT_REVIEW_SPATIAL_CONTRACT.maxDeckIntroHeight) throw new Error("Content deck intro exceeds the spatial budget.");
  const order = [header, chapterNav, deckIntro, firstChapterHeading, firstSlideHeading, firstReadingGrid];
  for (let index = 0; index < order.length - 1; index += 1) {
    if (order[index].y > order[index + 1].y) throw new Error("Content review regions are not in the approved reading order.");
  }
  if (firstReadingGrid.y >= viewport.height) throw new Error("First-page reading content does not enter the initial viewport.");
  if (!Number.isFinite(measurement?.scrollWidth) || !Number.isFinite(measurement?.clientWidth)
      || measurement.scrollWidth > measurement.clientWidth + 1) {
    throw new Error("Content review has horizontal overflow.");
  }
  return { viewport, header, chapterNav, deckIntro, firstChapterHeading, firstSlideHeading, firstReadingGrid };
}
```

- [ ] **Step 4: Run the Node test and verify GREEN**

Run:

```bash
node --test tests/v22-prototype-fidelity.test.mjs
```

Expected: all Node tests PASS.

---

### Task 2: Freeze the semantic reading structure before changing the page

**Files:**

- Modify: `产品代码/widget/src/content-review/ContentFullDeckReviewPage.test.tsx`
- Modify: `产品代码/widget/src/content-review/ContentReviewResponsive.test.tsx`
- Modify: `产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx`

- [ ] **Step 1: Add failing DOM semantics to the existing 08 rhythm test**

In `ContentFullDeckReviewPage.test.tsx`, extend `renders the approved 08 deck rhythm from positional chapter projection`:

```ts
expect(head).toHaveAttribute("data-content-review-header");
expect(head?.querySelector("[data-content-review-progress-track]")).not.toBeNull();
expect(chapterNav).toHaveAttribute("data-content-review-chapter-nav");
expect(deckIntro).toHaveAttribute("data-content-review-deck-intro");
expect(container.querySelectorAll("[data-content-review-first-reading-grid]")).toHaveLength(1);
expect(deckIntro).toHaveTextContent("本稿阅读导语");
expect(deckIntro).not.toHaveTextContent("本轮审核说明");
```

- [ ] **Step 2: Add failing responsive source assertions**

Add to `ContentReviewResponsive.test.tsx`:

```ts
it("keeps the chapter navigator as one compact horizontal strip", () => {
  expect(css).toMatch(/\.content-review-chapter-nav\s*\{[^}]*flex-wrap:\s*nowrap[^}]*overflow-x:\s*auto/s);
  expect(css).toMatch(/\.content-review-chapter-nav-item\s*\{[^}]*flex:\s*0\s+0\s+auto/s);
  expect(css).not.toMatch(/\.content-review-chapter-nav-item\s*\{[^}]*flex:\s*1\s+1\s+320px/s);
});
```

- [ ] **Step 3: Run focused Widget tests and verify RED**

Run:

```bash
npm run test:widget -- ContentFullDeckReviewPage ContentReviewResponsive
```

Expected: FAIL because semantic data attributes, progress track, compact intro copy and single-line navigation are not implemented.

- [ ] **Step 4: Add the minimal semantic DOM**

Modify `ContentFullDeckReviewPage.tsx` without changing event handlers or bridge calls:

```tsx
<header className="content-review-head content-review-header" data-content-review-header>
  {/* existing identity, progress and actions */}
  <div
    className="content-review-progress-track"
    data-content-review-progress-track
    role="progressbar"
    aria-label="全稿审核完成进度"
    aria-valuemin={0}
    aria-valuemax={slides.length}
    aria-valuenow={completed}
  >
    <span style={{ width: `${slides.length ? (completed / slides.length) * 100 : 0}%` }} />
  </div>
</header>
```

Add `data-content-review-chapter-nav` and `data-content-review-deck-intro` to the existing nav and intro. Change the intro label/title to:

```tsx
<p className="content-review-kicker">本稿阅读导语</p>
<h2 id="content-review-deck-intro-title">完整售前阅读稿</h2>
```

Change `chapter.slides.map((slide) =>` to `chapter.slides.map((slide, slideIndex) =>` and add exactly once:

```tsx
<div
  className="content-slide-reading-grid"
  data-content-review-first-reading-grid={chapterIndex === 0 && slideIndex === 0 ? "true" : undefined}
>
```

- [ ] **Step 5: Run the DOM test and verify its semantic portion passes**

Run:

```bash
npm run test:widget -- ContentFullDeckReviewPage
```

Expected: the DOM semantics pass; the responsive test remains RED until Task 3 changes CSS.

---

### Task 3: Restore the compact 08 reading rhythm in CSS

**Files:**

- Modify: `产品代码/widget/src/styles/content-review.css`
- Test: `产品代码/widget/src/content-review/ContentReviewResponsive.test.tsx`

- [ ] **Step 1: Implement the compact page shell and header**

Replace the page/header/navigation/intro/chapter rules with the following behavior:

```css
.content-review-page { width: 100%; min-width: 0; padding: 0 clamp(12px, 1.5vw, 22px) 48px; }
.content-review-header { position: sticky; z-index: 10; top: 0; display: grid; grid-template-columns: minmax(240px, 1fr) minmax(210px, .65fr) minmax(280px, auto); gap: 8px 16px; align-items: center; width: 100%; max-width: 1680px; margin: 0 auto; padding: 10px 14px 12px; border: 0; border-bottom: 1px solid #dbe1e9; background: rgb(255 255 255 / 97%); backdrop-filter: blur(16px); }
.content-review-header h1 { margin: 0 0 2px; font-size: clamp(17px, 1.5vw, 21px); line-height: 1.2; }
.content-review-header p { margin: 0; color: #667085; font-size: 10px; }
.content-review-progress { display: flex; flex-wrap: wrap; align-items: baseline; gap: 3px 8px; }
.content-review-progress strong { font-size: 16px; }
.content-review-counts { display: flex; flex-basis: 100%; flex-wrap: wrap; gap: 3px 7px; }
.content-review-progress-track { grid-column: 1 / -1; height: 3px; overflow: hidden; background: #e8ecf2; }
.content-review-progress-track > span { display: block; height: 100%; background: #275fc4; transition: width 160ms ease; }
```

- [ ] **Step 2: Implement the single-line chapter strip and compact intro**

```css
.content-review-outline { display: flex; gap: 5px; width: 100%; max-width: 1680px; margin: 8px auto; }
.content-review-chapter-nav { flex-wrap: nowrap; align-items: center; overflow-x: auto; scrollbar-width: thin; padding-bottom: 2px; }
.content-review-chapter-nav-item { display: flex; min-width: max-content; flex: 0 0 auto; gap: 3px; align-items: center; padding: 3px; border: 1px solid #d6dde7; border-radius: 999px; background: #fff; }
.content-review-outline .content-review-chapter-link { display: flex; min-height: 30px; align-items: center; border: 0; border-radius: 999px; padding: 5px 8px; background: transparent; color: #334155; font-size: 10px; font-weight: 800; }
.content-review-chapter-pages { display: flex; flex: 0 0 auto; flex-wrap: nowrap; gap: 2px; }
.content-review-deck-intro { width: 100%; max-width: 1680px; margin: 8px auto; padding: 12px 14px; border: 0; border-radius: 12px; background: #16233a; color: #fff; }
.content-review-deck-intro h2 { margin: 4px 0 5px; font-size: clamp(17px, 1.5vw, 21px); line-height: 1.3; }
.content-review-deck-intro > p:not(.content-review-kicker) { max-width: 1080px; margin: 4px 0; color: #cbd5e1; font-size: 10px; line-height: 1.5; }
.content-review-deck-intro .content-review-kicker { color: #9eacc2 !important; font-size: 9px !important; }
```

Keep `.content-review-summary` as a separate light end-of-deck block; do not share the dark intro rules with it.

- [ ] **Step 3: Compact chapter and slide lead-in without removing content**

```css
.content-review-document { display: grid; gap: 10px; width: 100%; max-width: 1680px; margin: 0 auto; }
.content-review-chapter-heading { display: grid; grid-template-columns: 32px minmax(0, 1fr) auto; gap: 3px 9px; align-items: center; padding: 8px 2px 7px; }
.content-review-chapter-heading > p:first-child { grid-row: 1 / span 2; grid-column: 1; display: grid; width: 32px; height: 32px; place-items: center; border-radius: 9px; background: #17233a; color: #fff; font-size: 9px; letter-spacing: 0; }
.content-review-chapter-heading h2 { grid-column: 2; margin: 0; font-size: clamp(16px, 1.5vw, 20px); line-height: 1.25; }
.content-review-chapter-heading > p:nth-of-type(2) { grid-column: 2; }
.content-review-chapter-heading > p:last-child { grid-column: 3; grid-row: 1 / span 2; }
.content-review-chapter-slides { display: grid; gap: 10px; }
.content-slide-heading { padding: 11px 13px; }
.content-slide-heading h2 { margin: 5px 0; font-size: clamp(17px, 1.6vw, 22px); }
.content-slide-heading p { margin: 2px 0; font-size: 11px; }
```

Update the `max-width: 900px` block so the header and chapter heading return to one column without restoring card-wall navigation. Preserve the existing 380px PageDecision rules exactly.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
npm run test:widget -- ContentFullDeckReviewPage ContentReviewResponsive ContentReviewLongDeck
```

Expected: all focused content-review test files PASS.

---

### Task 4: Make the real Browser runner enforce 1280×720 geometry

**Files:**

- Modify: `产品代码/tests/v22-prototype-fidelity.test.mjs`
- Modify: `产品代码/scripts/run-v22-ui-acceptance.mjs`

- [ ] **Step 1: Add the failing runner-consumption assertion**

Extend the final Node test:

```js
assert.match(runnerSource, /assertContentReviewSpatialFidelity/);
assert.match(runnerSource, /data-content-review-first-reading-grid/);
assert.match(runnerSource, /firstViewportScreenshot/);
```

- [ ] **Step 2: Run Node test and verify RED**

Run:

```bash
node --test tests/v22-prototype-fidelity.test.mjs
```

Expected: FAIL because the runner does not yet consume the spatial contract.

- [ ] **Step 3: Add runner import and viewport height parameter**

Import `assertContentReviewSpatialFidelity`. Change:

```js
async function openPage(file, width, height = 900) {
  const context = await browser.newContext({ viewport: { width, height }, reducedMotion: "reduce" });
```

Change `checkReview` to accept `height = 900`, include height in identity, and call `openPage(file, width, height)`.

- [ ] **Step 4: Measure and assert the reference viewport**

Inside the content branch, when `width === 1280 && height === 720`, evaluate:

```js
const spatialFidelity = await page.evaluate(() => {
  const readRect = (selector) => {
    const element = document.querySelector(selector);
    if (!element) throw new Error(`Missing spatial fidelity element: ${selector}`);
    const rect = element.getBoundingClientRect();
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
  };
  return {
    viewport: { width: window.innerWidth, height: window.innerHeight },
    header: readRect("[data-content-review-header]"),
    chapterNav: readRect("[data-content-review-chapter-nav]"),
    deckIntro: readRect("[data-content-review-deck-intro]"),
    firstChapterHeading: readRect("[data-content-chapter] .content-review-chapter-heading"),
    firstSlideHeading: readRect("[data-content-slide] .content-slide-heading"),
    firstReadingGrid: readRect("[data-content-review-first-reading-grid]"),
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  };
});
assertContentReviewSpatialFidelity(spatialFidelity);
const firstViewportScreenshot = previewPath(`${identity}-first-viewport.png`);
await page.screenshot({ path: firstViewportScreenshot, fullPage: false });
```

Add `spatialFidelity` and `firstViewportScreenshot` to the content result. Run 1280×720 in addition to the existing 360/760/1000/1440 checks. Update the result-count assertion from 8 to 10.

- [ ] **Step 5: Run Node test and verify GREEN**

Run:

```bash
node --test tests/v22-prototype-fidelity.test.mjs
```

Expected: all Node tests PASS.

- [ ] **Step 6: Run deterministic Browser acceptance**

Run:

```bash
npm run accept:v22-ui
```

Expected: PASS with a report containing the 1280×720 content spatial measurement and first-viewport screenshot. If Chromium cannot launch due sandbox/host permission, record the exact CapabilityGap and rerun only through an approved execution environment; do not weaken the assertion.

---

### Task 5: Verify, record evidence, and commit one reversible implementation

**Files:**

- Create: `产品代码/docs/validation/2026-08-18-content-review-spatial-fidelity-acceptance.md`
- Verify all modified files from Tasks 1–4

- [ ] **Step 1: Write the scoped acceptance record**

Record:

```markdown
- branch and commit under test
- reference prototype and 1280×720 spatial thresholds
- RED evidence for Node/Widget tests
- GREEN focused tests
- full Widget/typecheck/build results
- Browser geometry result and first-viewport screenshot path
- real-host evidence: false unless current real receipts exist
- userUiAcceptance: pending
- untouched scopes: visual review, Runtime, MCP, PPT runtime data
```

- [ ] **Step 2: Run fresh verification**

Run:

```bash
git diff --check
npm run test:widget -- ContentFullDeckReviewPage ContentReviewResponsive ContentReviewLongDeck
node --test tests/v22-prototype-fidelity.test.mjs
npm run test:widget
npm run typecheck
npm run build
npm run accept:v22-ui
```

Expected: all deterministic commands PASS; Browser output names the current report and screenshot paths. Any failure keeps the phase incomplete.

- [ ] **Step 3: Inspect the complete diff and scope**

Run:

```bash
git status --short
git diff --stat
git diff -- 00-唯一研发基线索引-v1.0.md 03-UI设计与交互规范-v1.0.md 产品代码/widget/src/content-review 产品代码/widget/src/styles/content-review.css 产品代码/scripts/run-v22-ui-acceptance.mjs 产品代码/scripts/v22-ui-acceptance-evidence.mjs 产品代码/tests/v22-prototype-fidelity.test.mjs 产品代码/docs/validation/2026-08-18-content-review-spatial-fidelity-acceptance.md
```

Expected: no visual-review, Runtime, MCP, PPT data, unrelated baseline or unrelated user file appears.

- [ ] **Step 4: Commit the verified implementation**

```bash
git add 产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx 产品代码/widget/src/content-review/ContentFullDeckReviewPage.test.tsx 产品代码/widget/src/content-review/ContentReviewResponsive.test.tsx 产品代码/widget/src/styles/content-review.css 产品代码/scripts/run-v22-ui-acceptance.mjs 产品代码/scripts/v22-ui-acceptance-evidence.mjs 产品代码/tests/v22-prototype-fidelity.test.mjs 产品代码/docs/validation/2026-08-18-content-review-spatial-fidelity-acceptance.md
git commit -m "fix: restore content review spatial fidelity"
```

- [ ] **Step 5: Handoff for user acceptance**

Report the commit, exact verification counts, report path and first-viewport screenshot. Keep `userUiAcceptance: pending`. Do not enter the visual-review phase until the user explicitly accepts the rendered content page.

---

## Plan self-review

- **Spec coverage:** compact header, progress track, chapter strip, compact deck intro, chapter rhythm, first-page body in 1280×720, PageDecision preservation, long deck, evidence boundaries, user acceptance and rollback each map to a task.
- **Scope:** only content UI, content tests, shared acceptance helper/runner and scoped validation record change; visual UI, Runtime, MCP and PPT data are excluded.
- **TDD:** every new contract or changed behavior begins with a failing Node/Widget assertion and records the expected failure before implementation.
- **Type consistency:** DOM selectors used by React, tests and Browser runner are identical; the pure geometry helper consumes one stable measurement shape.
- **No placeholders:** every implementation step names exact files, code, commands and expected results.
- **Versioning:** the implementation remains one independently revertible commit after the already committed design/baseline version.

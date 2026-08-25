import { spawnSync } from "node:child_process";
import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outputDirectory = path.join(root, "output", "playwright", "v16-ui");
const temporaryRoot = await import("node:fs/promises").then(({ mkdtemp }) =>
  mkdtemp(path.join(os.tmpdir(), "ai-ppt-v16-ui.")),
);
await mkdir(outputDirectory, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function run(command, args, label, extraEnv = {}) {
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: "utf8",
    env: { ...process.env, ...extraEnv },
  });
  if (result.status !== 0) {
    throw new Error(`${label} failed: ${result.stderr || result.stdout || `exit ${result.status}`}`);
  }
  return result.stdout.trim();
}

async function playwrightModule() {
  const moduleRoots = [
    process.env.CODEX_NODE_MODULES?.trim(),
    path.join(os.homedir(), ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node", "node_modules"),
  ].filter(Boolean);
  for (const moduleRoot of moduleRoots) {
    const entry = path.join(moduleRoot, "playwright", "index.mjs");
    try {
      await access(entry);
      return import(pathToFileURL(entry).href);
    } catch (_missing) {
      // Continue to the next explicit Codex runtime candidate.
    }
  }
  throw new Error("A bundled Codex runtime containing Playwright is required.");
}

function previewPath(file) {
  return path.join(outputDirectory, file);
}

function longProjectionHtml(sourceHtml, reviewType, pageCount) {
  const marker = "window.__AI_PPT_PREVIEW__=";
  const start = sourceHtml.indexOf(marker);
  const end = sourceHtml.indexOf(";</script>", start);
  assert(start >= 0 && end > start, `Unable to locate ${reviewType} preview payload`);
  const payloadStart = start + marker.length;
  const data = JSON.parse(sourceHtml.slice(payloadStart, end));
  const prefix = reviewType === "content" ? "slide-" : "visual-slide-";
  const standing = data.review.sections.filter((section) => !section.anchor.startsWith(prefix));
  const template = data.review.sections.find((section) => section.anchor.startsWith(prefix));
  assert(template, `${reviewType} preview does not contain a page template`);
  const longChinese = "完整长文档必须逐字保留全部正文、讲解稿、来源与页面合同，不得摘要、截断、隐藏或依赖分页加载。";
  const longToken = `unbroken-${"z".repeat(180)}.source.json#paragraph-999`;
  const pages = Array.from({ length: pageCount }, (_, index) => {
    const serial = String(index + 1).padStart(3, "0");
    const nextAnchor = reviewType === "content" ? `slide-long-${serial}` : `visual-slide-long-${serial}`;
    const cloned = JSON.parse(JSON.stringify(template).replaceAll(template.anchor, nextAnchor));
    cloned.title = `第 ${index + 1} 页·${longChinese}${serial}`;
    const visible = cloned.fields.find((field) => ["visible_content", "visible_copy"].includes(field.label));
    if (visible) visible.value = [`第 ${index + 1} 页完整正文`, `${longChinese}${serial}`, longToken];
    const notes = cloned.fields.find((field) => field.label === "speaker_notes");
    if (notes) notes.value = `${longChinese.repeat(2)}${serial}`;
    return cloned;
  });
  data.review.sections = [...standing, ...pages];
  data.review.outline = data.review.sections.map(({ anchor, title }) => ({ anchor, title }));
  data.review.title = `${pageCount} 页${reviewType === "content" ? "内容蓝图" : "视觉合同"}完整性验收`;
  const serialized = JSON.stringify(data).replaceAll("<", "\\u003c");
  return sourceHtml.slice(0, payloadStart) + serialized + sourceHtml.slice(end);
}

const seedOutput = run(
  "python3",
  [path.join(root, "scripts", "seed-v16-ui-project.py"), temporaryRoot],
  "schema 3 UI seed",
);
const seed = JSON.parse(seedOutput);
const previewEnv = { AI_PPT_PREVIEW_OUTPUT_DIR: outputDirectory };
run(
  process.execPath,
  [path.join(root, "scripts", "create-widget-preview.mjs"), seed.project_root, seed.workspace_config, "blueprint"],
  "workbench preview",
  { ...previewEnv, AI_PPT_CONTENT_REVIEW_PREVIEWS: "1" },
);
for (const reviewType of ["visual"]) {
  run(
    process.execPath,
    [path.join(root, "scripts", "create-review-preview.mjs"), seed.project_root, seed.workspace_config, reviewType],
    `${reviewType} review preview`,
    previewEnv,
  );
}

const visualPreview = await readFile(previewPath("ai-ppt-visual-review-preview.html"), "utf8");
await writeFile(
  previewPath("ai-ppt-visual-review-long-120.html"),
  longProjectionHtml(visualPreview, "visual", 120),
  "utf8",
);

const { chromium } = await playwrightModule();
const browser = await chromium.launch({ headless: true });
const results = [];
const longDocumentResults = [];
const contentSidebarResults = [];

async function openPage(file, width, deviceScaleFactor = 1) {
  const context = await browser.newContext({
    viewport: { width, height: 900 },
    deviceScaleFactor,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto(pathToFileURL(previewPath(file)).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts?.ready);
  return { context, page, consoleErrors };
}

async function overflowMetrics(page) {
  return page.evaluate(() => ({
    innerWidth: window.innerWidth,
    bodyScrollWidth: document.body.scrollWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
  }));
}

function assertNoOverflow(metrics, identity) {
  assert(metrics.bodyScrollWidth <= metrics.innerWidth + 1, `${identity}: body horizontal overflow`);
  assert(metrics.documentScrollWidth <= metrics.innerWidth + 1, `${identity}: document horizontal overflow`);
}

async function checkWorkbench(width) {
  const identity = `workbench@${width}`;
  const { context, page, consoleErrors } = await openPage("ai-ppt-workbench-preview.html", width);
  try {
    await page.waitForSelector(".compact-app-shell");
    const mountMs = await page.evaluate(() => performance.now() - (window.__AI_PPT_ACCEPTANCE_START__ || 0));
    const base = await overflowMetrics(page);
    assertNoOverflow(base, identity);
    const navigationTargets = await page.locator(".stable-navigation .nav-item").evaluateAll((nodes) =>
      nodes.map((node) => {
        const rect = node.getBoundingClientRect();
        return { width: rect.width, height: rect.height };
      }),
    );
    assert(navigationTargets.every(({ width: itemWidth, height }) => itemWidth >= 40 && height >= 40), `${identity}: navigation target below 40px`);
    await page.waitForSelector(".content-review-document");
    assert((await page.locator(".content-review-document").count()) === 1, `${identity}: blueprint must render one complete UI-03 document`);
    assert((await page.locator(".compact-primary-action").count()) === 0, `${identity}: review-ready UI-03 must not fall back to a compact action card`);

    const bodyText = await page.locator("body").textContent();
    for (const forbidden of ["展开完整工作台", "联系表", "下载 PPTX", "验收交付并通过 G4", "返回聊天"]) {
      assert(!bodyText.includes(forbidden), `${identity}: forbidden control remains: ${forbidden}`);
    }

    await page.locator(".nav-item").filter({ hasText: "制作与交付" }).click();
    assert((await page.locator('[data-testid^="binary-gate-"]').count()) === 4, `${identity}: four binary quality gates required`);
    assert((await page.locator('[data-testid^="target-"]').count()) === 4, `${identity}: four supported target profiles required`);
    const targetRows = await page.locator('[data-testid^="target-"]').evaluateAll((nodes) =>
      nodes.map((node) => ({
        targetId: node.getAttribute("data-testid")?.replace("target-", ""),
        hash: node.getAttribute("data-pptx-sha256"),
        text: node.textContent || "",
      })),
    );
    const requiredRows = targetRows.filter(({ targetId }) => targetId === "macos-powerpoint");
    const deferredRows = targetRows.filter(({ targetId }) => targetId !== "macos-powerpoint");
    assert(requiredRows.length === 1 && requiredRows[0].hash?.length === 64, `${identity}: current required target must bind one SHA-256`);
    assert(
      deferredRows.length === 3 && deferredRows.every(({ hash, text }) => !hash && text.includes("延期 · 当前版本不验收")),
      `${identity}: deferred profiles must have no SHA-256 or pass state`,
    );
    const targetHashes = targetRows.map(({ hash }) => hash);
    assertNoOverflow(await overflowMetrics(page), `${identity}/delivery`);

    await page.locator(".nav-item").filter({ hasText: "内容蓝图" }).click();
    const screenshot = previewPath(`workbench-${width}.png`);
    await page.screenshot({ path: screenshot, fullPage: true });
    assert(consoleErrors.length === 0, `${identity}: console errors: ${consoleErrors.join(" | ")}`);
    results.push({
      surface: "workbench",
      width,
      zoomPercent: 100,
      mountMs,
      ...base,
      primaryActionCount: 0,
      contentReviewDocumentCount: 1,
      targetHashes,
      consoleErrors,
      screenshot,
    });
  } finally {
    await context.close();
  }
}

async function persistentControls(page, identity) {
  const controls = [
    page.getByRole("button", { name: "视觉合同" }),
    page.getByRole("button", { name: "目录" }),
    page.getByRole("button", { name: /^标记 \d+$/ }),
    page.getByRole("button", { name: "保存标记" }),
  ];
  for (const control of controls) {
    assert(await control.isVisible(), `${identity}: a persistent review control is not visible`);
    const box = await control.boundingBox();
    assert(box && box.x >= 0 && box.x + box.width <= (await page.viewportSize()).width + 1, `${identity}: a persistent control is unreachable`);
  }
}

async function checkReview(reviewType, width, deviceScaleFactor) {
  const zoomPercent = deviceScaleFactor * 100;
  const surface = `${reviewType}-review`;
  const identity = `${surface}@${width}/${zoomPercent}%`;
  const file = `ai-ppt-${reviewType}-review-preview.html`;
  const { context, page, consoleErrors } = await openPage(file, width, deviceScaleFactor);
  try {
    await page.waitForSelector(".review-app-shell");
    const mountMs = await page.evaluate(() => performance.now() - (window.__AI_PPT_ACCEPTANCE_START__ || 0));
    const metrics = await overflowMetrics(page);
    assertNoOverflow(metrics, identity);
    await persistentControls(page, identity);
    const header = await page.locator(".review-header").boundingBox();
    assert(header && Math.abs(header.height - 64) < 0.5, `${identity}: header must remain 64px`);
    assert((await page.locator(".review-outline.open").count()) === 0, `${identity}: outline must start closed`);

    const pageCount = Number(await page.locator(".review-sheet-list").getAttribute("data-review-page-count"));
    const anchors = await page.locator("[data-review-page-anchor]").evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-review-page-anchor")),
    );
    assert(pageCount > 0 && anchors.length === pageCount, `${identity}: complete review pages are missing`);
    assert(new Set(anchors).size === pageCount, `${identity}: review page anchors are not unique`);

    const bodyText = await page.locator("body").textContent();
    assert(bodyText.includes("解释来源"), `${identity}: complete speaker notes are missing`);
    for (const forbidden of ["返回聊天", "版本历史", "样张画廊", "下载 PPTX", "拖动加宽"]) {
      assert(!bodyText.includes(forbidden), `${identity}: forbidden review control remains: ${forbidden}`);
    }

    const documentBefore = await page.locator(".review-document-view").boundingBox();
    const scrollBefore = await page.evaluate(() => window.scrollY);
    await page.getByRole("button", { name: "目录" }).click();
    const outline = page.getByRole("dialog", { name: "审阅目录" });
    await outline.waitFor();
    await page.waitForFunction(() => document.querySelector(".review-outline.open")?.contains(document.activeElement));
    const documentAfter = await page.locator(".review-document-view").boundingBox();
    const scrollAfter = await page.evaluate(() => window.scrollY);
    assert(documentBefore && documentAfter && documentBefore.x === documentAfter.x && documentBefore.width === documentAfter.width, `${identity}: outline changed document geometry`);
    assert(scrollBefore === scrollAfter, `${identity}: outline changed document scroll position`);

    const marksTrigger = page.getByRole("button", { name: /^标记 \d+$/ });
    await marksTrigger.click();
    const marks = page.getByRole("dialog", { name: "审阅标记" });
    await marks.waitFor();
    assert((await page.getByRole("dialog", { name: "审阅目录" }).count()) === 0, `${identity}: drawers are not mutually exclusive`);
    await page.waitForFunction(() => document.querySelector(".review-comment-drawer.open")?.contains(document.activeElement));
    await page.keyboard.press("Escape");
    await marks.waitFor({ state: "hidden" });
    await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label")?.startsWith("标记 "));

    assert(consoleErrors.length === 0, `${identity}: console errors: ${consoleErrors.join(" | ")}`);
    const zoomSuffix = zoomPercent === 100 ? "" : "-zoom-200";
    const screenshot = previewPath(`${surface}-${width}${zoomSuffix}.png`);
    await page.screenshot({ path: screenshot, fullPage: true });
    results.push({
      surface,
      width,
      zoomPercent,
      deviceScaleFactor,
      mountMs,
      headerHeight: header.height,
      pageCount,
      uniquePageAnchors: new Set(anchors).size,
      documentGeometryStable: true,
      focusRestored: true,
      ...metrics,
      consoleErrors,
      screenshot,
    });
  } finally {
    await context.close();
  }
}

async function checkVisualProfessionalReview(width) {
  const identity = `visual-professional-review@${width}`;
  const { context, page, consoleErrors } = await openPage("ai-ppt-visual-review-preview.html", width);
  try {
    await page.waitForSelector(".visual-professional-page");
    const mountMs = await page.evaluate(() => performance.now() - (window.__AI_PPT_ACCEPTANCE_START__ || 0));
    const metrics = await overflowMetrics(page);
    assertNoOverflow(metrics, identity);
    assert((await page.locator("[data-anchor-tab]").count()) === 3, `${identity}: exactly three anchor slots are required`);
    assert((await page.locator(".anchor-workbench").count()) === 1, `${identity}: anchor workbench is missing`);
    assert((await page.locator(".anchor-feedback-composer").count()) === 1, `${identity}: below-canvas composer is missing`);
    assert((await page.locator(".feedback-panel").count()) === 1, `${identity}: feedback batch panel is missing`);

    const anchorPanelBox = await page.locator(".anchor-review-layout").boundingBox();
    await page.getByRole("tab", { name: "完整视觉合同" }).click();
    await page.locator(".contract-document-head").waitFor();
    assert((await page.locator(".anchor-evidence-strip").count()) === 1, `${identity}: Anchor Evidence is missing`);
    assert((await page.locator(".visual-contract-list").count()) === 1, `${identity}: complete slide contract list is missing`);
    assert((await page.locator(".contract-page").count()) > 0, `${identity}: slide visual contracts are missing`);
    assert((await page.locator(".field-mark-button").count()) > 0, `${identity}: field mark controls are missing`);

    const documentBefore = await page.locator(".visual-contract-document").boundingBox();
    await page.getByRole("button", { name: "目录" }).click();
    const outlineDialog = page.getByRole("dialog", { name: "视觉合同目录" });
    await outlineDialog.waitFor();
    const documentAfter = await page.locator(".visual-contract-document").boundingBox();
    assert(documentBefore && documentAfter && documentBefore.x === documentAfter.x && documentBefore.width === documentAfter.width, `${identity}: outline overlay changed contract geometry`);
    await outlineDialog.getByRole("button", { name: "关闭" }).click();
    await page.locator(".field-mark-button").first().click();
    const markDialog = page.getByRole("dialog", { name: "合同标记" });
    await markDialog.waitFor();
    assert((await page.locator(".feedback-panel").textContent()).includes("尚未加入反馈"), `${identity}: anchor and contract review states are not isolated`);
    await markDialog.getByRole("button", { name: "关闭" }).click();

    const forbiddenNavigation = page.locator(
      [
        ".workspace-sidebar",
        ".compact-navigation",
        ".stable-navigation",
        ".product-navigation",
        "[aria-label='产品导航']",
        "[data-product-navigation]",
      ].join(", "),
    );
    assert((await forbiddenNavigation.count()) === 0, `${identity}: forbidden product navigation DOM remains`);
    assert(anchorPanelBox, `${identity}: anchor layout was not measurable`);
    assert(consoleErrors.length === 0, `${identity}: console errors: ${consoleErrors.join(" | ")}`);
    const screenshot = previewPath(`visual-professional-review-${width}.png`);
    await page.screenshot({ path: screenshot, fullPage: false });
    results.push({ surface: "visual-professional", width, mountMs, ...metrics, consoleErrors, screenshot });
  } finally {
    await context.close();
  }
}

async function checkLongDocument(reviewType, pageCount) {
  const file = `ai-ppt-${reviewType}-review-long-${pageCount}.html`;
  const identity = `${reviewType}-review-long-${pageCount}`;
  const { context, page, consoleErrors } = await openPage(file, 1000);
  try {
    await page.waitForSelector(`[data-review-page-count="${pageCount}"]`);
    const mountMs = await page.evaluate(() => performance.now() - (window.__AI_PPT_ACCEPTANCE_START__ || 0));
    const anchors = await page.locator("[data-review-page-anchor]").evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-review-page-anchor")),
    );
    const metrics = await overflowMetrics(page);
    const firstPageStyle = await page.locator("[data-review-page-anchor]").first().evaluate((node) => {
      const style = getComputedStyle(node);
      return { contentVisibility: style.contentVisibility, containIntrinsicSize: style.containIntrinsicSize };
    });
    const text = await page.locator("body").textContent();
    assert(mountMs < 2_000, `${identity}: ${mountMs.toFixed(1)}ms exceeds 2-second budget`);
    assert(anchors.length === pageCount && new Set(anchors).size === pageCount, `${identity}: incomplete or duplicate page anchors`);
    assert(text.includes(`第 ${pageCount} 页完整正文`), `${identity}: last page content is missing`);
    assert(text.includes("unbroken-"), `${identity}: long unbroken source is missing`);
    assert(firstPageStyle.contentVisibility === "auto", `${identity}: progressive rendering CSS is missing`);
    assertNoOverflow(metrics, identity);
    assert(consoleErrors.length === 0, `${identity}: console errors: ${consoleErrors.join(" | ")}`);
    longDocumentResults.push({
      reviewType,
      pageCount,
      mountMs,
      uniquePageAnchors: new Set(anchors).size,
      ...firstPageStyle,
      ...metrics,
      consoleErrors,
    });
  } finally {
    await context.close();
  }
}

async function contentSidebarPage(file, width) {
  const opened = await openPage(file, width);
  await opened.page.waitForSelector(".content-review-document, .content-review-progress");
  return opened;
}

async function checkContentSidebarResponsive(width) {
  const identity = `content-sidebar-ready-10@${width}`;
  const { context, page, consoleErrors } = await contentSidebarPage("content-review-ready-10.html", width);
  try {
    const metrics = await overflowMetrics(page);
    assertNoOverflow(metrics, identity);
    const documentBox = await page.locator(".content-review-document").boundingBox();
    assert(documentBox && documentBox.x <= 1 && documentBox.width >= width - 2, `${identity}: content document does not use the full available width`);
    const columnCount = await page.locator(".content-slide-main").first().evaluate((node) =>
      getComputedStyle(node).gridTemplateColumns.split(" ").filter(Boolean).length,
    );
    assert(columnCount === (width >= 900 ? 2 : 1), `${identity}: responsive content/evidence columns are incorrect`);
    const anchors = await page.locator("article.content-slide-section").evaluateAll((nodes) => nodes.map((node) => node.id));
    assert(anchors.length === 10 && new Set(anchors).size === 10, `${identity}: 10 unique full-deck anchors required`);
    const bodyText = await page.locator("body").textContent();
    for (const required of ["页面实际文字", "图片与材料", "完整逐字稿", "问题—要求—方案映射", "承接上一页", "进入下一页"]) {
      assert(bodyText.includes(required), `${identity}: missing complete review content: ${required}`);
    }
    for (const forbidden of ["待确认目录框架", "待授权展开全部页面", "框架确认", "整稿展开授权", "希望客户形成的判断"]) {
      assert(!bodyText.includes(forbidden), `${identity}: obsolete content workflow remains: ${forbidden}`);
    }
    await page.locator(".content-evidence-item").first().scrollIntoViewIfNeeded();
    const evidenceImageCount = await page.locator(".content-evidence-item img").count();
    assert(evidenceImageCount > 0, `${identity}: accepted 08 reference requires at least one rendered key-evidence image`);
    await page.locator(".content-evidence-item img").first().waitFor();
    const lazyImages = await page.locator(".content-evidence-item img").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("loading")));
    assert(lazyImages.every((value) => value === "lazy"), `${identity}: evidence images must lazy-load`);
    assert(bodyText.includes("没有图片的页面不强制提供图片"), `${identity}: image-free pages must remain explicitly valid`);
    const unclipped = await page.locator(".visible-copy-row p, .speaker-notes-block p").evaluateAll((nodes) => nodes.every((node) => {
      const style = getComputedStyle(node);
      return style.textOverflow !== "ellipsis" && style.webkitLineClamp === "none";
    }));
    assert(unclipped, `${identity}: core copy or notes are truncated`);

    const before = await page.locator(".content-review-document").boundingBox();
    await page.getByRole("button", { name: "目录定位" }).click();
    await page.getByRole("dialog", { name: "全稿目录" }).waitFor();
    const after = await page.locator(".content-review-document").boundingBox();
    assert(before && after && before.x === after.x && before.width === after.width, `${identity}: directory overlay changed document geometry`);
    await page.keyboard.press("Escape");

    assert(consoleErrors.length === 0, `${identity}: console errors: ${consoleErrors.join(" | ")}`);
    const screenshot = previewPath(`content-sidebar-ready-10-${width}.png`);
    await page.screenshot({ path: screenshot, fullPage: false });
    contentSidebarResults.push({ scenario: "ready-10", width, columnCount, anchors: anchors.length, ...metrics, screenshot, consoleErrors });
  } finally {
    await context.close();
  }
}

async function checkContentProgress(file, requiredText) {
  const { context, page, consoleErrors } = await contentSidebarPage(file, 900);
  try {
    const text = await page.locator("body").textContent();
    assert(text.includes(requiredText), `${file}: expected progress state is missing`);
    assert((await page.locator("article.content-slide-section").count()) === 0, `${file}: draft pages leaked before internal passage`);
    assert(consoleErrors.length === 0, `${file}: console errors: ${consoleErrors.join(" | ")}`);
    contentSidebarResults.push({ scenario: file, width: 900, progressOnly: true, consoleErrors });
  } finally {
    await context.close();
  }
}

async function checkMixedAndReadyBatch() {
  {
    const { context, page, consoleErrors } = await contentSidebarPage("content-review-mixed-24.html", 1200);
    try {
      const footer = page.locator(".review-batch-footer");
      assert((await footer.textContent()).includes("23 / 24"), "mixed-decisions-24: 23 / 24 progress is missing");
      assert(await footer.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" }).isDisabled(), "mixed-decisions-24: incomplete batch must stay disabled");
      assert((await page.locator("article.content-slide-section").count()) === 24, "mixed-decisions-24: all 24 pages must render");
      assert(consoleErrors.length === 0, `mixed-decisions-24: console errors: ${consoleErrors.join(" | ")}`);
      contentSidebarResults.push({ scenario: "mixed-decisions-24", width: 1200, progress: "23 / 24", batchEnabled: false, consoleErrors });
    } finally {
      await context.close();
    }
  }
  {
    const { context, page, consoleErrors } = await contentSidebarPage("content-review-ready-24.html", 1200);
    try {
      const footer = page.locator(".review-batch-footer");
      assert((await footer.textContent()).includes("24 / 24"), "ready-24: 24 / 24 progress is missing");
      const submit = footer.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" });
      assert(await submit.isEnabled(), "ready-24: complete clean batch must be enabled");
      await submit.click();
      await page.getByText("已提交，等待整套修改方案。").waitFor();
      const calls = await page.evaluate(() => window.__AI_PPT_PREVIEW_CALLS__ || {});
      assert(calls.submit_content_review_batch === 1, "ready-24: batch must submit exactly once");
      assert(calls.sendFollowUp === 1, "ready-24: submit must trigger exactly one Codex follow-up");
      assert(consoleErrors.length === 0, `ready-24: console errors: ${consoleErrors.join(" | ")}`);
      contentSidebarResults.push({ scenario: "ready-24", width: 1200, progress: "24 / 24", batchEnabled: true, calls, consoleErrors });
    } finally {
      await context.close();
    }
  }
}

async function checkRetainedDraft(file, expectedError) {
  const { context, page, consoleErrors } = await contentSidebarPage(file, 900);
  try {
    const first = page.locator("article.content-slide-section").first();
    await first.getByRole("radio", { name: "需要修改" }).check();
    const comment = first.getByRole("textbox", { name: "审核意见" });
    const draft = "保留这条未保存的完整修改意见，用于验证失败恢复。";
    await comment.fill(draft);
    await first.getByRole("button", { name: "保存本页判断" }).click();
    await first.getByRole("alert").waitFor();
    assert((await first.getByRole("alert").textContent()).includes(expectedError), `${file}: expected save error is missing`);
    assert(await first.getByRole("radio", { name: "需要修改" }).isChecked(), `${file}: selected decision was lost`);
    assert(await comment.inputValue() === draft, `${file}: comment draft was lost`);
    const submit = page.getByRole("button", { name: "完成本轮审核，交给 Codex 集中处理" });
    assert(await submit.isDisabled(), `${file}: failed/conflicted draft must block submission`);
    assert(consoleErrors.length === 0, `${file}: console errors: ${consoleErrors.join(" | ")}`);
    contentSidebarResults.push({ scenario: file, width: 900, draftRetained: true, batchEnabled: false, consoleErrors });
  } finally {
    await context.close();
  }
}

async function checkFrozenAndVersionStates() {
  for (const [file, scenario] of [
    ["content-review-submitted-frozen.html", "submitted-frozen"],
    ["content-review-plan-proposed.html", "plan-proposed"],
  ]) {
    const { context, page, consoleErrors } = await contentSidebarPage(file, 900);
    try {
      assert((await page.locator(".page-decision-editor.frozen").count()) === 24, `${scenario}: all decisions must be frozen`);
      assert((await page.getByText("已提交，等待整套修改方案。").count()) === 1, `${scenario}: submitted state is missing`);
      assert(consoleErrors.length === 0, `${scenario}: console errors: ${consoleErrors.join(" | ")}`);
      contentSidebarResults.push({ scenario, width: 900, frozen: 24, consoleErrors });
    } finally {
      await context.close();
    }
  }
  {
    const { context, page, consoleErrors } = await contentSidebarPage("content-review-new-version-zero.html", 900);
    try {
      assert((await page.locator("article.content-slide-section").count()) === 24, "new-version-zero: all pages must render");
      assert((await page.locator(".decision-saved-summary").count()) === 0, "new-version-zero: old decisions must not be inherited");
      assert((await page.locator(".review-batch-footer").textContent()).includes("0 / 24"), "new-version-zero: progress must restart at zero");
      assert(consoleErrors.length === 0, `new-version-zero: console errors: ${consoleErrors.join(" | ")}`);
      contentSidebarResults.push({ scenario: "new-version-zero-decisions", width: 900, progress: "0 / 24", inherited: 0, consoleErrors });
    } finally {
      await context.close();
    }
  }
}

async function checkContentLong60() {
  const { context, page, consoleErrors } = await contentSidebarPage("content-review-long-60.html", 1440);
  try {
    const anchors = await page.locator("article.content-slide-section").evaluateAll((nodes) => nodes.map((node) => node.id));
    assert(anchors.length === 60 && new Set(anchors).size === 60, "long-review-60: all page anchors must exist exactly once");
    assert((await page.locator("#content-slide-S60").count()) === 1, "long-review-60: last page is missing");
    assert((await page.locator("body").textContent()).includes("第 60 页逐字稿完整保留"), "long-review-60: final speaker notes are missing");
    const metrics = await overflowMetrics(page);
    assertNoOverflow(metrics, "long-review-60@1440");
    assert(consoleErrors.length === 0, `long-review-60: console errors: ${consoleErrors.join(" | ")}`);
    contentSidebarResults.push({ scenario: "long-review-60", width: 1440, anchors: 60, ...metrics, consoleErrors });
  } finally {
    await context.close();
  }
}

try {
  for (const width of [480, 900, 1200, 1440]) await checkContentSidebarResponsive(width); // 480, 900, 1200, 1440
  for (const width of [360, 760, 1440]) await checkVisualProfessionalReview(width);
} finally {
  await browser.close();
}

const report = {
  ok: true,
  checkedAt: new Date().toISOString(),
  evidenceScope: "deterministic schema 3 browser contract evidence; not real Codex host or desktop PowerPoint/WPS proof",
  seed: {
    schemaVersion: seed.schema_version,
    projectRoot: seed.project_root,
    evidenceIdentity: seed.evidence_identity,
    pptxSha256: seed.pptx_sha256,
  },
  screenshotCount: results.length,
  results,
  longDocumentResults,
  contentSidebarResults,
};
assert(results.length === 3, `Expected 3 visual screenshots, received ${results.length}`);
assert(longDocumentResults.length === 0, "Legacy visual long-document checks must not run");
assert(contentSidebarResults.length === 4, `Expected 4 content review checks, received ${contentSidebarResults.length}`);
const reportPath = previewPath("v16-ui-acceptance.json");
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${reportPath}\n`);

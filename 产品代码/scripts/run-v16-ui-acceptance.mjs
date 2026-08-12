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
  previewEnv,
);
for (const reviewType of ["content", "visual"]) {
  run(
    process.execPath,
    [path.join(root, "scripts", "create-review-preview.mjs"), seed.project_root, seed.workspace_config, reviewType],
    `${reviewType} review preview`,
    previewEnv,
  );
}

const contentPreview = await readFile(previewPath("ai-ppt-content-review-preview.html"), "utf8");
const visualPreview = await readFile(previewPath("ai-ppt-visual-review-preview.html"), "utf8");
await writeFile(
  previewPath("ai-ppt-content-review-long-60.html"),
  longProjectionHtml(contentPreview, "content", 60),
  "utf8",
);
await writeFile(
  previewPath("ai-ppt-visual-review-long-120.html"),
  longProjectionHtml(visualPreview, "visual", 120),
  "utf8",
);

const { chromium } = await playwrightModule();
const browser = await chromium.launch({ headless: true });
const results = [];
const longDocumentResults = [];

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
    assert((await page.locator(".compact-primary-action").count()) === 1, `${identity}: blueprint requires exactly one primary action`);

    const bodyText = await page.locator("body").textContent();
    for (const forbidden of ["展开完整工作台", "联系表", "下载 PPTX", "验收交付并通过 G4", "返回聊天"]) {
      assert(!bodyText.includes(forbidden), `${identity}: forbidden control remains: ${forbidden}`);
    }

    await page.locator(".nav-item").filter({ hasText: "制作与交付" }).click();
    assert((await page.locator('[data-testid^="binary-gate-"]').count()) === 4, `${identity}: four binary quality gates required`);
    assert((await page.locator('[data-testid^="target-"]').count()) === 4, `${identity}: four desktop targets required`);
    const targetHashes = await page.locator('[data-testid^="target-"]').evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-pptx-sha256")),
    );
    assert(new Set(targetHashes).size === 1 && targetHashes[0]?.length === 64, `${identity}: targets must share one SHA-256`);
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
      primaryActionCount: 1,
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
    page.getByRole("button", { name: "内容审阅" }),
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

try {
  for (const width of [360, 420, 480]) await checkWorkbench(width);
  for (const reviewType of ["content", "visual"]) {
    for (const width of [760, 1000, 1440]) await checkReview(reviewType, width, 1);
    for (const width of [760, 1000, 1440]) await checkReview(reviewType, width, 2);
  }
  await checkLongDocument("content", 60);
  await checkLongDocument("visual", 120);
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
};
assert(results.length === 15, `Expected 15 screenshots, received ${results.length}`);
assert(longDocumentResults.length === 2, "Expected 60/120-page performance results");
const reportPath = previewPath("v16-ui-acceptance.json");
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${reportPath}\n`);

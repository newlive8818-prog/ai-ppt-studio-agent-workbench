import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  LOCAL_PREVIEW_DISCLAIMER,
  LOCAL_PREVIEW_EVIDENCE,
  PROTOTYPE_FIDELITY_REQUIREMENTS,
  assertInteractionEvidenceCoverage,
  assertPrototypeFidelityCounts,
  atomicPublishAcceptanceReport,
  captureEvidencePair,
  completeAcceptanceRun,
  computeCandidateRegion,
} from "./v22-ui-acceptance-evidence.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outputDirectory = path.join(root, "output", "playwright", "v22-ui");
await mkdir(outputDirectory, { recursive: true });
const runId = `run-${randomUUID()}`;
const runDirectory = path.join(outputDirectory, "runs", runId);
await mkdir(path.dirname(runDirectory), { recursive: true });
await mkdir(runDirectory);

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

async function loadPlaywright() {
  const userHome = process.env.HOME?.trim() || process.env.USERPROFILE?.trim();
  const roots = [
    process.env.CODEX_NODE_MODULES?.trim(),
    userHome && path.join(userHome, ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node", "node_modules"),
  ].filter(Boolean);
  for (const moduleRoot of roots) {
    const entry = path.join(moduleRoot, "playwright", "index.mjs");
    try {
      await access(entry);
      return import(pathToFileURL(entry).href);
    } catch (_missing) {
      // Try the next explicit bundled Runtime candidate.
    }
  }
  throw new Error("A bundled Codex Runtime containing Playwright is required.");
}

const previewPath = (file) => path.join(runDirectory, file);

function transformPreviewPayload(sourceHtml, label, transform) {
  const marker = "window.__AI_PPT_PREVIEW__=";
  const start = sourceHtml.indexOf(marker);
  const end = sourceHtml.indexOf(";window.__AI_PPT_PREVIEW_ASSETS__=", start);
  assert(start >= 0 && end > start, `Unable to locate ${label} preview payload`);
  const payloadStart = start + marker.length;
  const data = JSON.parse(sourceHtml.slice(payloadStart, end));
  transform(data);
  return `${sourceHtml.slice(0, payloadStart)}${JSON.stringify(data).replaceAll("<", "\\u003c")}${sourceHtml.slice(end)}`;
}

function longProjectionHtml(sourceHtml, reviewType, count) {
  return transformPreviewPayload(sourceHtml, reviewType, (data) => {
    if (reviewType === "content") {
      const template = data.review.slides[0];
      data.review.slides = Array.from({ length: count }, (_, index) => ({
        ...structuredClone(template),
        slide_id: `S${String(index + 1).padStart(3, "0")}`,
        order: index + 1,
        neutral_title: `第 ${index + 1} 页完整内容验收`,
        visible_copy_blocks: [{ block_id: `copy-${index + 1}`, identity: "方案建议", text: `第 ${index + 1} 页完整正文` }],
        speaker_notes: `第 ${index + 1} 页完整演讲备注`,
      }));
      data.review.decisions = [];
      data.review.progress = { completed: 0, total: count, remaining: count, unsaved: 0 };
    } else {
      const template = data.review.slide_visual_contracts[0];
      data.review.slide_visual_contracts = Array.from({ length: count }, (_, index) => ({
        ...structuredClone(template),
        slide_id: `S${String(index + 1).padStart(3, "0")}`,
        order: index + 1,
        neutral_title: `第 ${index + 1} 页视觉合同完整性验收`,
        page_task: `完整保留第 ${index + 1} 页视觉需求`,
      }));
    }
  });
}

function savedUnverifiedProjectionHtml(sourceHtml) {
  return transformPreviewPayload(sourceHtml, "saved/unverified visual", (data) => {
    const review = data.review;
    const slide = review.slide_visual_contracts[0];
    const revision = review.revision;
    const savedAt = "2026-08-17T12:01:00Z";
    const createdAt = "2026-08-17T12:00:00Z";
    review.contract_review_marks_ref = `artifact://visual-contract-review-mark-set/${"f".repeat(64)}`;
    review.contract_review_marks = {
      mark_set_id: "local-preview-saved-unverified",
      project_id: review.project_id,
      review_session_id: review.review_session_id,
      visual_contract_ref: review.visual_contract_ref,
      source_version: review.source_version,
      revision,
      marks: [{
        mark_id: "local-preview-mark-1",
        target_type: "contract-field",
        slide_id: slide.slide_id,
        deck_section_id: "",
        target_key: "page_task",
        selected_text: "",
        context_before: "",
        context_after: "",
        comment: "本地验收已保存标记",
        visual_contract_ref: review.visual_contract_ref,
        source_version: review.source_version,
        revision,
        created_at: createdAt,
        created_by: "user",
      }],
      persistence_status: "saved",
      host_notification_status: "unavailable",
      ai_receipt_status: "unverified",
      saved_at: savedAt,
    };
  });
}

const seed = JSON.parse(run(
  "python3",
  [path.join(root, "scripts", "seed-v16-ui-project.py")],
  "schema 3 UI seed",
));
const previewEnv = { AI_PPT_PREVIEW_OUTPUT_DIR: runDirectory };
for (const [reviewType, sessionId] of [
  ["content", seed.content_review_session_id],
  ["visual", seed.visual_review_session_id],
]) {
  run(
    process.execPath,
    [path.join(root, "scripts", "create-review-preview.mjs"), seed.project_root, seed.workspace_config, reviewType, sessionId],
    `${reviewType} review preview`,
    previewEnv,
  );
}

for (const [reviewType, count] of [["content", 60], ["visual", 120]]) {
  const source = await readFile(previewPath(`ai-ppt-${reviewType}-review-preview.html`), "utf8");
  await writeFile(
    previewPath(`ai-ppt-${reviewType}-review-long-${count}.html`),
    longProjectionHtml(source, reviewType, count),
    "utf8",
  );
}
const visualPreviewHtml = await readFile(previewPath("ai-ppt-visual-review-preview.html"), "utf8");
await writeFile(
  previewPath("ai-ppt-visual-review-saved-unverified.html"),
  savedUnverifiedProjectionHtml(visualPreviewHtml),
  "utf8",
);

const { chromium } = await loadPlaywright();
const browser = await chromium.launch({ headless: true });
const results = [];
const interactionEvidence = [];

async function openPage(file, width) {
  const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (message) => message.type() === "error" && consoleErrors.push(message.text()));
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto(pathToFileURL(previewPath(file)).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts?.ready);
  return { context, page, consoleErrors };
}

async function metrics(page) {
  return page.evaluate(() => ({
    innerWidth: window.innerWidth,
    bodyScrollWidth: document.body.scrollWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
  }));
}

async function settleLayout(page) {
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(
    () => requestAnimationFrame(() => requestAnimationFrame(resolve)),
  )));
}

async function assertLoadedImages(images, identity) {
  const count = await images.count();
  assert(count > 0, `${identity}: no rendered images`);
  for (let index = 0; index < count; index += 1) {
    const image = images.nth(index);
    await image.scrollIntoViewIfNeeded();
    await image.waitFor({ state: "visible" });
    await image.evaluate((element) => element.decode?.().catch(() => undefined));
    const loaded = await image.evaluate((element) => ({
      complete: element.complete,
      naturalWidth: element.naturalWidth,
      naturalHeight: element.naturalHeight,
    }));
    assert(
      loaded.complete && loaded.naturalWidth > 0 && loaded.naturalHeight > 0,
      `${identity}: image ${index + 1} did not load ${JSON.stringify(loaded)}`,
    );
  }
}

function assertNoOverflow(value, identity) {
  assert(value.bodyScrollWidth <= value.innerWidth + 1, `${identity}: body overflow`);
  assert(value.documentScrollWidth <= value.innerWidth + 1, `${identity}: document overflow`);
}

async function assertPrototypeFidelity(page, surface) {
  const counts = {};
  for (const requirement of PROTOTYPE_FIDELITY_REQUIREMENTS[surface]) {
    counts[requirement.key] = await page.locator(requirement.selector).count();
  }
  assertPrototypeFidelityCounts(surface, counts);
  return counts;
}

async function captureInteractionEvidence(target, state, mode) {
  const screenshotPath = previewPath(`${state}.png`);
  await target.screenshot({ path: screenshotPath });
  interactionEvidence.push({ state, screenshot: screenshotPath, mode });
  return screenshotPath;
}

async function assertVisualContractTextReadable(page, identity) {
  const slideReadableSelector = [
    ".visual-contract-field p",
    ".visual-contract-field li",
    ".contract-object-value dd",
  ].join(", ");
  const documentReadableSelector = [
    ".visual-contract-title-page h1",
    ".visual-contract-title-page p",
    '[data-contract-logical-object="anchor-slide-evidence"] li',
    '[data-contract-logical-object="anchor-slide-evidence"] dd',
  ].join(", ");
  const clipped = new Map();
  for (const item of await page.locator(documentReadableSelector).evaluateAll((elements) => elements.flatMap((element) => {
    const text = element.textContent?.trim();
    if (!text || element.scrollWidth <= element.clientWidth + 1) return [];
    return [{
      element: `${element.tagName.toLowerCase()}.${element.className}`,
      text: text.slice(0, 100),
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }];
  }))) clipped.set(`${item.element}:${item.text}`, item);
  for (const contract of await page.locator(".visual-slide-contract").all()) {
    await contract.scrollIntoViewIfNeeded();
    for (const item of await contract.locator(slideReadableSelector).evaluateAll((elements) => elements.flatMap((element) => {
      const text = element.textContent?.trim();
      if (!text || element.scrollWidth <= element.clientWidth + 1) return [];
      return [{
        element: `${element.tagName.toLowerCase()}.${element.className}`,
        text: text.slice(0, 100),
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
      }];
    }))) clipped.set(`${item.element}:${item.text}`, item);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  assert(clipped.size === 0, `${identity}: clipped visual-contract text ${JSON.stringify([...clipped.values()])}`);
}

async function revealDeferredContentForScreenshot(page) {
  await page.addStyleTag({
    content: ".content-review-slide,.visual-slide-contract{content-visibility:visible!important}",
  });
  await settleLayout(page);
}

async function checkReview(reviewType, width) {
  const identity = `${reviewType}-review@${width}`;
  const { context, page, consoleErrors } = await openPage(`ai-ppt-${reviewType}-review-preview.html`, width);
  try {
    await page.waitForSelector(reviewType === "content" ? ".content-review-page" : ".visual-professional-page");
    const layout = await metrics(page);
    assertNoOverflow(layout, identity);
    let objectCount;
    let evidenceLayer = false;
    let materialSourceCount = 0;
    let stickyProof = null;
    const prototypeFidelity = {};
    if (reviewType === "content") {
      prototypeFidelity["content-review"] = await assertPrototypeFidelity(page, "content-review");
      objectCount = await page.locator("[data-content-slide]").count();
      assert(objectCount === 3, `${identity}: expected 3 content pages, received ${objectCount}`);
      const materialCards = page.locator(".content-material-card");
      assert(await materialCards.count() >= objectCount, `${identity}: every content page needs a material image`);
      for (let index = 0; index < await materialCards.count(); index += 1) {
        const card = materialCards.nth(index);
        await card.scrollIntoViewIfNeeded();
        await card.locator("img.content-material-image").waitFor();
      }
      await assertLoadedImages(page.locator("img.content-material-image"), `${identity} material`);
      const materialSources = await page.locator("img.content-material-image").evaluateAll(
        (images) => images.map((image) => image.currentSrc || image.src),
      );
      materialSourceCount = new Set(materialSources).size;
      assert(
        materialSourceCount >= objectCount,
        `${identity}: content pages reuse the same rendered material ${JSON.stringify(materialSources)}`,
      );
      assert(
        await page.locator(".content-material-image-slot .asset-placeholder").count() === 0,
        `${identity}: material placeholder remained after loading`,
      );

      const decisionOptions = page.locator(".page-decision-option");
      assert(await decisionOptions.count() === objectCount * 4, `${identity}: incomplete PageDecision controls`);
      for (const option of await decisionOptions.all()) {
        const height = await option.evaluate((element) => element.getBoundingClientRect().height);
        assert(height >= 42, `${identity}: PageDecision target is ${height}px high`);
      }
      if (width === 360) {
        const positions = await page.locator("[data-content-slide]").first().locator(".page-decision-option").evaluateAll(
          (elements) => elements.map((element) => {
            const rect = element.getBoundingClientRect();
            return { top: Math.round(rect.top), left: rect.left, right: rect.right };
          }),
        );
        const rows = new Map();
        positions.forEach((position) => rows.set(position.top, [...(rows.get(position.top) || []), position]));
        assert(rows.size === 2, `${identity}: PageDecision is not a 2x2 grid ${JSON.stringify(positions)}`);
        assert([...rows.values()].every((row) => row.length === 2), `${identity}: PageDecision row does not contain two choices`);
      }

      assert(/^S\d+$/.test(seed.content_review_draft.slide_id), `${identity}: unsafe draft slide identity`);
      const draftPage = page.locator(`#content-${seed.content_review_draft.slide_id}`);
      if (width === 1000) {
        await captureInteractionEvidence(
          draftPage,
          "content-before-feedback",
          "current-content-page-before-non-approved-feedback",
        );
      }
      const modify = draftPage.getByRole("radio", { name: "需要修改" });
      const editSaved = draftPage.getByRole("button", { name: "编辑意见" });
      if (await editSaved.count()) await editSaved.click();
      else await modify.click();
      const comment = draftPage.getByRole("textbox", { name: `${seed.content_review_draft.slide_id} 审核意见` });
      await comment.fill(seed.content_review_draft.comment);
      assert(await modify.isChecked(), `${identity}: modify draft was not selected`);
      assert(await comment.inputValue() === seed.content_review_draft.comment, `${identity}: modify draft comment was not retained`);
      if (width === 1000) {
        await captureInteractionEvidence(
          draftPage,
          "content-after-non-approved-feedback",
          "current-content-page-after-non-approved-feedback",
        );
      }

      const evidenceButton = page.getByRole("button", { name: /来源证据$/ }).first();
      assert(await evidenceButton.count(), `${identity}: read-only evidence entry missing`);
      await evidenceButton.click();
      const dialog = page.getByRole("dialog", { name: /来源证据$/ });
      await dialog.waitFor();
      assert((await dialog.textContent()).includes("只读辅助层"), `${identity}: evidence layer is not read-only`);
      await dialog.getByRole("button", { name: "关闭证据" }).click();
      evidenceLayer = true;
    } else {
      if (width === 760) {
        await page.setViewportSize({ width, height: 480 });
        await settleLayout(page);
      }
      const anchorTabs = page.locator('.anchor-tabs [role="tab"]');
      objectCount = await anchorTabs.count();
      assert(objectCount === 3, `${identity}: expected 3 anchor pages, received ${objectCount}`);
      const layoutGeometry = await page.locator(".anchor-review-layout").evaluate((layout) => {
        const main = layout.querySelector(".anchor-review-main").getBoundingClientRect();
        const assistant = layout.querySelector(".anchor-review-assistant").getBoundingClientRect();
        return { main: { top: main.top, left: main.left, right: main.right }, assistant: { top: assistant.top, left: assistant.left } };
      });
      if (width >= 760) {
        assert(
          layoutGeometry.main.right <= layoutGeometry.assistant.left + 1,
          `${identity}: wide anchor review is not two columns ${JSON.stringify(layoutGeometry)}`,
        );
      } else {
        assert(
          layoutGeometry.main.top < layoutGeometry.assistant.top,
          `${identity}: narrow anchor main content must precede the assistant ${JSON.stringify(layoutGeometry)}`,
        );
      }

      for (let index = 0; index < objectCount; index += 1) {
        await anchorTabs.nth(index).click();
        await assertLoadedImages(page.locator('img[alt$="锚点页成果"]'), `${identity} anchor ${index + 1}`);
        assert(await page.locator(".anchor-canvas .asset-placeholder").count() === 0, `${identity}: anchor placeholder remained`);
      }
      await anchorTabs.first().click();
      const comparisonButton = page.getByRole("button", { name: "与上一版对比" });
      assert(await comparisonButton.isEnabled(), `${identity}: previous-version comparison is unavailable`);
      await comparisonButton.click();
      const comparison = page.getByRole("dialog", { name: /前后版本对比$/ });
      await comparison.waitFor();
      await assertLoadedImages(comparison.locator("img"), `${identity} comparison`);
      assert(await comparison.locator(".asset-placeholder").count() === 0, `${identity}: comparison placeholder remained`);
      await comparison.getByRole("button", { name: "关闭对比" }).click();

      if (width === 1000) {
        await captureInteractionEvidence(
          page.locator(".region-feedback-editor"),
          "anchor-before-rectangle-feedback",
          "anchor-editor-before-rectangle-feedback",
        );
      }

      if (width === 760 || width === 1000) {
        await page.getByRole("button", { name: "开始标注" }).click();
        const canvas = page.locator(".anchor-canvas");
        const canvasBox = await canvas.boundingBox();
        assert(canvasBox, `${identity}: anchor canvas has no interactive geometry`);
        await page.mouse.move(canvasBox.x + 24, canvasBox.y + 24);
        await page.mouse.down();
        await page.mouse.move(canvasBox.x + Math.min(220, canvasBox.width - 24), canvasBox.y + Math.min(130, canvasBox.height - 24));
        await page.mouse.up();
        await page.getByRole("textbox", { name: "当前框选区域反馈" }).waitFor();
        const candidate = page.locator(".anchor-region.candidate");
        await candidate.waitFor();
        const candidateBox = await candidate.boundingBox();
        const currentCanvasBox = await canvas.boundingBox();
        assert(
          candidateBox && currentCanvasBox && candidateBox.width > 0 && candidateBox.height > 0,
          `${identity}: candidate region has no positive geometry`,
        );
        const candidateRegion = computeCandidateRegion({
          candidateRect: candidateBox,
          canvasRect: currentCanvasBox,
          viewport: page.viewportSize(),
        });
        const composer = page.getByRole("textbox", { name: "当前框选区域反馈" });
        await composer.fill("调整该区域层级，保持原生可编辑并减少视觉噪声。");
        prototypeFidelity["visual-anchor"] = await assertPrototypeFidelity(page, "visual-anchor");
        if (width === 1000) {
          await captureInteractionEvidence(
            page.locator(".region-feedback-editor"),
            "anchor-after-rectangle-feedback",
            "anchor-editor-after-rectangle-feedback",
          );
        }
        await settleLayout(page);
        if (width === 760) {
          const stickyContract = await page.evaluate(() => {
            const header = document.querySelector(".visual-professional-header");
            const assistant = document.querySelector(".anchor-review-assistant");
            const headerRect = header.getBoundingClientRect();
            const assistantRect = assistant.getBoundingClientRect();
            const computed = getComputedStyle(assistant);
            return {
              position: computed.position,
              topInset: Number.parseFloat(computed.top),
              headerHeight: headerRect.height,
              assistantDocumentTop: assistantRect.top + window.scrollY,
              maxScrollY: document.documentElement.scrollHeight - window.innerHeight,
            };
          });
          assert(stickyContract.position === "sticky", `${identity}: assistant is not sticky ${JSON.stringify(stickyContract)}`);
          assert(
            stickyContract.topInset >= stickyContract.headerHeight,
            `${identity}: sticky inset is smaller than the responsive header ${JSON.stringify(stickyContract)}`,
          );
          const targetScrollY = stickyContract.assistantDocumentTop - stickyContract.topInset + 32;
          assert(
            targetScrollY <= stickyContract.maxScrollY,
            `${identity}: page cannot reach the assistant sticky state ${JSON.stringify({ ...stickyContract, targetScrollY })}`,
          );
          await page.evaluate((scrollY) => window.scrollTo(0, scrollY), targetScrollY);
          await settleLayout(page);
          const sticky = await page.evaluate(() => {
            const header = document.querySelector(".visual-professional-header").getBoundingClientRect();
            const assistantElement = document.querySelector(".anchor-review-assistant");
            const assistant = assistantElement.getBoundingClientRect();
            return {
              scrollY: window.scrollY,
              headerBottom: header.bottom,
              assistantTop: assistant.top,
              topInset: Number.parseFloat(getComputedStyle(assistantElement).top),
            };
          });
          assert(
            sticky.scrollY >= targetScrollY - 1
            && Math.abs(sticky.assistantTop - sticky.topInset) <= 1
            && sticky.assistantTop >= sticky.headerBottom - 1,
            `${identity}: assistant did not reach an uncovered sticky state ${JSON.stringify({ ...sticky, targetScrollY })}`,
          );
          stickyProof = { ...sticky, targetScrollY, annotationComposer: true, candidateRegion };
        }
        await page.evaluate(() => window.scrollTo(0, 0));
        await settleLayout(page);
      }

      await page.getByRole("tab", { name: "完整视觉合同" }).click();
      await page.waitForSelector(".visual-contract-document");
      objectCount = await page.locator(".visual-slide-contract").count();
      assert(objectCount === 3, `${identity}: full visual contract is incomplete (${objectCount}/3)`);
      if (width === 1000) {
        const anchorEvidence = page.locator('[data-contract-logical-object="anchor-slide-evidence"]');
        await anchorEvidence.scrollIntoViewIfNeeded();
        await captureInteractionEvidence(
          anchorEvidence,
          "contract-with-anchor-slide-evidence",
          "anchor-slide-evidence-current-visual-version",
        );
      }
      await page.getByRole("button", { name: "打开合同目录" }).click();
      const outline = page.getByRole("navigation", { name: "视觉合同章节定位" });
      prototypeFidelity["visual-contract"] = await assertPrototypeFidelity(page, "visual-contract");
      if (width === 1000) {
        await captureInteractionEvidence(
          page.locator(".visual-overlay-drawer"),
          "contract-directory-drawer",
          "overlay-contract-directory",
        );
      }
      const outlineButtons = outline.getByRole("button");
      await outlineButtons.last().click();
      await settleLayout(page);
      const directoryJump = await page.evaluate(() => {
        const header = document.querySelector(".visual-professional-header").getBoundingClientRect();
        const target = document.querySelector(".visual-slide-contract:last-child").getBoundingClientRect();
        return { headerBottom: header.bottom, targetTop: target.top };
      });
      assert(
        directoryJump.targetTop >= directoryJump.headerBottom - 1,
        `${identity}: directory target is covered by the header ${JSON.stringify(directoryJump)}`,
      );
      if (width === 1000) {
        await page.getByRole("button", { name: "打开标记记录" }).click();
        await captureInteractionEvidence(
          page.locator(".visual-overlay-drawer"),
          "contract-mark-drawer",
          "overlay-contract-mark-record",
        );
        await page.getByRole("dialog", { name: "合同标记记录" }).getByRole("button", { name: "关闭" }).click();
        await page.getByRole("tab", { name: "3 页锚点成果" }).click();
        const restoredComposer = page.getByRole("textbox", { name: "当前框选区域反馈" });
        assert(
          await restoredComposer.inputValue() === "调整该区域层级，保持原生可编辑并减少视觉噪声。",
          `${identity}: anchor feedback composer was not preserved across contract review`,
        );
        await page.getByRole("tab", { name: "完整视觉合同" }).click();
      }
      await assertVisualContractTextReadable(page, identity);
    }
    const deferredSelector = reviewType === "content" ? ".content-review-slide" : ".visual-slide-contract";
    const rawScreenshot = previewPath(`${identity}-raw.png`);
    const expandedEvidenceScreenshot = previewPath(`${identity}-expanded-evidence.png`);
    const evidence = await captureEvidencePair({
      rawPath: rawScreenshot,
      expandedPath: expandedEvidenceScreenshot,
      readProductionVisibility: () => page.locator(deferredSelector).last().evaluate(
        (element) => getComputedStyle(element).contentVisibility,
      ),
      captureRaw: async (screenshotPath) => {
        assertNoOverflow(await metrics(page), `${identity}-raw`);
        assert(consoleErrors.length === 0, `${identity}: ${consoleErrors.join(" | ")}`);
        await page.screenshot({ path: screenshotPath, fullPage: true });
      },
      revealAcceptanceOnly: () => revealDeferredContentForScreenshot(page),
      captureExpanded: async (screenshotPath) => {
        assertNoOverflow(await metrics(page), `${identity}-expanded-evidence`);
        await page.screenshot({ path: screenshotPath, fullPage: true });
      },
    });
    results.push({
      reviewType,
      width,
      objectCount,
      evidenceLayer,
      ...(materialSourceCount ? { materialSourceCount } : {}),
      ...(stickyProof ? { stickyProof } : {}),
      prototypeFidelity,
      ...layout,
      consoleErrors,
      ...evidence,
    });
  } finally {
    await context.close();
  }
}

async function checkSavedUnverifiedReceipt() {
  const identity = "visual-saved-unverified@1000";
  const { context, page, consoleErrors } = await openPage("ai-ppt-visual-review-saved-unverified.html", 1000);
  try {
    await page.getByRole("tab", { name: "完整视觉合同" }).click();
    await page.waitForSelector(".visual-contract-view");
    const receipt = page.locator('.visual-receipt-row[aria-label="合同标记保存事实"]');
    const receiptText = await receipt.textContent();
    assert(receiptText?.includes("持久化：已保存"), `${identity}: persistence fact missing`);
    assert(receiptText?.includes("宿主通知：不可用"), `${identity}: host unavailable fact missing`);
    assert(receiptText?.includes("AI 接收：未验证"), `${identity}: AI unverified fact missing`);
    assertNoOverflow(await metrics(page), identity);
    assert(consoleErrors.length === 0, `${identity}: ${consoleErrors.join(" | ")}`);
    await captureInteractionEvidence(
      receipt,
      "saved-unverified-receipt",
      "local-fixture-saved-host-unavailable-ai-unverified",
    );
  } finally {
    await context.close();
  }
}

async function checkLongReview(reviewType, count) {
  const { context, page, consoleErrors } = await openPage(`ai-ppt-${reviewType}-review-long-${count}.html`, 1000);
  try {
    if (reviewType === "visual") await page.getByRole("tab", { name: "完整视觉合同" }).click();
    const selector = reviewType === "content" ? "[data-content-slide]" : ".visual-slide-contract";
    await page.waitForSelector(selector);
    assert(await page.locator(selector).count() === count, `${reviewType}: incomplete long review`);
    assert((await page.locator("body").textContent()).includes(`第 ${count} 页`), `${reviewType}: final long-review page missing`);
    assertNoOverflow(await metrics(page), `${reviewType}-long-${count}`);
    assert(consoleErrors.length === 0, `${reviewType}-long-${count}: ${consoleErrors.join(" | ")}`);
  } finally {
    await context.close();
  }
}

const reportPath = path.join(outputDirectory, "v22-ui-acceptance.json");
const temporaryReportPath = path.join(outputDirectory, `.${runId}.tmp`);
await completeAcceptanceRun({
  runChecks: async () => {
    try {
      for (const reviewType of ["content", "visual"]) {
        for (const width of [360, 760, 1000, 1440]) await checkReview(reviewType, width);
      }
      await checkLongReview("content", 60);
      await checkLongReview("visual", 120);
      await checkSavedUnverifiedReceipt();
    } finally {
      await browser.close();
    }
    assert(results.length === 8, `Expected 8 screenshots, received ${results.length}`);
    assertInteractionEvidenceCoverage(interactionEvidence);
    return {
      ok: true,
      checkedAt: new Date().toISOString(),
      runDirectory,
      surfaces: ["content-review", "visual-review", "read-only-evidence-layer"],
      previewEvidence: { ...LOCAL_PREVIEW_EVIDENCE },
      disclaimer: LOCAL_PREVIEW_DISCLAIMER,
      seed,
      results,
      interactionEvidence,
    };
  },
  publishReport: (report) => atomicPublishAcceptanceReport({
    report,
    reportPath,
    temporaryPath: temporaryReportPath,
  }),
});
process.stdout.write(`${reportPath}\n`);

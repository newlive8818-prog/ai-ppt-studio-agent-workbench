import path from "node:path";
import { rename as renameFile, writeFile as writeReportFile } from "node:fs/promises";

export const LOCAL_PREVIEW_DISCLAIMER = "Raw screenshots preserve production CSS; expanded evidence screenshots use acceptance-only CSS. Not Codex Browser, host notification, AI receipt, Codex Presentations, or Microsoft PowerPoint proof. Not G3 or user acceptance proof.";

export const LOCAL_PREVIEW_EVIDENCE = Object.freeze({
  evidenceScope: "local-development-preview",
  proofEligible: false,
  realHostEvidence: false,
});

function freezeRequirements(requirements) {
  return Object.freeze(requirements.map((requirement) => Object.freeze(requirement)));
}

export const PROTOTYPE_FIDELITY_REQUIREMENTS = Object.freeze({
  "content-review": freezeRequirements([
    { key: "head", selector: ".content-review-vm-header", exact: 1, min: 1 },
    { key: "progress", selector: ".content-review-vm-progress", exact: 1, min: 1 },
    { key: "chapterNav", selector: ".content-review-vm-chapter-nav", exact: 1, min: 1 },
    { key: "deckIntro", selector: ".content-review-vm-deck-intro", exact: 1, min: 1 },
    { key: "chapters", selector: ".content-review-vm-chapter", min: 1 },
    { key: "slides", selector: "[data-content-review-vm-slide]", min: 1 },
    { key: "reviewSummary", selector: ".content-review-vm-summary", exact: 1, min: 1 },
  ]),
  "visual-anchor": freezeRequirements([
    { key: "topbar", selector: ".visual-review-topbar", exact: 1, min: 1 },
    { key: "projectIdentity", selector: ".visual-professional-project-identity", exact: 1, min: 1 },
    { key: "aiMark", selector: ".visual-professional-ai-mark", exact: 1, min: 1 },
    { key: "viewSwitch", selector: ".visual-professional-review-view-switch", exact: 1, min: 1 },
    { key: "workbench", selector: ".anchor-review-layout", exact: 1, min: 1 },
    { key: "main", selector: ".anchor-review-main", exact: 1, min: 1 },
    { key: "feedbackComposer", selector: ".anchor-feedback-composer", exact: 1, min: 1 },
  ]),
  "visual-contract": freezeRequirements([
    { key: "titlePage", selector: ".visual-contract-title-page", exact: 1, min: 1 },
    { key: "deckDesignSystem", selector: '[data-contract-logical-object="deck-design-system"]', exact: 1, min: 1 },
    { key: "anchorEvidence", selector: '[data-contract-logical-object="anchor-slide-evidence"]', exact: 1, min: 1 },
    { key: "slideContracts", selector: ".visual-slide-contract", min: 1 },
    { key: "outline", selector: ".visual-contract-outline", exact: 1, min: 1 },
    { key: "overlayDrawer", selector: ".visual-overlay-drawer", exact: 1, min: 1 },
  ]),
});

export const REQUIRED_INTERACTION_STATES = Object.freeze([
  "content-before-feedback",
  "content-after-non-approved-feedback",
  "anchor-before-rectangle-feedback",
  "anchor-after-rectangle-feedback",
  "contract-with-anchor-slide-evidence",
  "contract-directory-drawer",
  "contract-mark-drawer",
  "saved-unverified-receipt",
]);

export function assertPrototypeFidelityCounts(surface, counts) {
  const requirements = PROTOTYPE_FIDELITY_REQUIREMENTS[surface];
  if (!requirements) throw new Error(`Unknown prototype fidelity surface: ${surface}`);
  if (!counts || typeof counts !== "object" || Array.isArray(counts)) {
    throw new Error(`${surface} prototype fidelity counts must be an object.`);
  }
  for (const requirement of requirements) {
    const count = counts[requirement.key];
    if (!Number.isSafeInteger(count) || count < 0) {
      throw new Error(`${surface} ${requirement.key} selector count must be a non-negative integer.`);
    }
    if (requirement.exact !== undefined && count !== requirement.exact) {
      throw new Error(`${surface} ${requirement.key} expected exactly ${requirement.exact}, received ${count}.`);
    }
    if (count < requirement.min) {
      throw new Error(`${surface} ${requirement.key} expected at least ${requirement.min}, received ${count}.`);
    }
  }
  return counts;
}

export function assertInteractionEvidenceCoverage(entries) {
  if (!Array.isArray(entries)) throw new Error("Interaction evidence must be an array.");
  const seen = new Map();
  for (const entry of entries) {
    if (!entry || typeof entry !== "object" || typeof entry.state !== "string") {
      throw new Error("Interaction evidence entries require a state.");
    }
    if (!REQUIRED_INTERACTION_STATES.includes(entry.state)) {
      throw new Error(`Unknown interaction evidence state: ${entry.state}`);
    }
    if (typeof entry.screenshot !== "string" || !entry.screenshot.trim()) {
      throw new Error(`${entry.state} interaction evidence requires a screenshot path.`);
    }
    seen.set(entry.state, (seen.get(entry.state) || 0) + 1);
  }
  for (const state of REQUIRED_INTERACTION_STATES) {
    const count = seen.get(state) || 0;
    if (count !== 1) {
      throw new Error(`${state} interaction evidence must appear exactly once; received ${count}.`);
    }
  }
  return entries;
}

function finiteRect(value, label) {
  const fields = ["x", "y", "width", "height"];
  if (fields.some((field) => typeof value?.[field] !== "number" || !Number.isFinite(value[field]))) {
    throw new Error(`${label} geometry must contain finite number x, y, width, and height values.`);
  }
  return Object.fromEntries(fields.map((field) => [field, value[field]]));
}

function finiteViewport(value) {
  if (typeof value?.width !== "number" || !Number.isFinite(value.width)
      || typeof value?.height !== "number" || !Number.isFinite(value.height)
      || value.width <= 0 || value.height <= 0) {
    throw new Error("Candidate viewport must contain finite positive number width and height values.");
  }
  return { width: value.width, height: value.height };
}

function finiteNonNegativeDuration(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new Error(`${label} must be a finite non-negative number.`);
  }
  return value;
}

export function assertLongReviewMeasurement(value) {
  const expectedFields = [
    "reviewType", "count", "viewport", "navigationToReadyMs",
    "finalObjectAccessMs", "measurementMode", "complete",
    "finalObjectPresent", "noHorizontalOverflow", "consoleErrorCount",
  ];
  if (!value || typeof value !== "object" || Array.isArray(value)
      || Object.keys(value).length !== expectedFields.length
      || expectedFields.some((field) => !Object.hasOwn(value, field))) {
    throw new Error("Long review measurement must be a closed evidence object.");
  }
  if (value.reviewType !== "content" && value.reviewType !== "visual") {
    throw new Error("Long review type must be content or visual.");
  }
  if (!Number.isSafeInteger(value.count) || value.count < 1) {
    throw new Error("Long review count must be a positive safe integer.");
  }
  const viewport = finiteViewport(value.viewport);
  const navigationToReadyMs = finiteNonNegativeDuration(
    value.navigationToReadyMs,
    "Navigation-to-ready duration",
  );
  const finalObjectAccessMs = finiteNonNegativeDuration(
    value.finalObjectAccessMs,
    "Final-object access duration",
  );
  if (value.measurementMode !== "local-playwright-measurement-only") {
    throw new Error("Long review timing must remain local Playwright measurement-only evidence.");
  }
  if (value.complete !== true || value.finalObjectPresent !== true
      || value.noHorizontalOverflow !== true || value.consoleErrorCount !== 0) {
    throw new Error("Long review measurement requires complete, overflow-free, error-free evidence.");
  }
  return {
    reviewType: value.reviewType,
    count: value.count,
    viewport,
    navigationToReadyMs,
    finalObjectAccessMs,
    measurementMode: value.measurementMode,
    complete: true,
    finalObjectPresent: true,
    noHorizontalOverflow: true,
    consoleErrorCount: 0,
  };
}

export function assertLongReviewMeasurementCoverage(values) {
  if (!Array.isArray(values) || values.length !== 4) {
    throw new Error("Long review coverage requires exactly four measurements.");
  }
  const measurements = values.map(assertLongReviewMeasurement);
  const expectedIdentities = new Set([
    "content:10", "content:24", "content:60", "visual:120",
  ]);
  const identities = new Set(
    measurements.map(({ reviewType, count }) => `${reviewType}:${count}`),
  );
  if (identities.size !== expectedIdentities.size
      || [...expectedIdentities].some((identity) => !identities.has(identity))) {
    throw new Error("Long review coverage must contain each approved identity exactly once.");
  }
  return measurements;
}

export function assertAcceptanceEnvironment(value) {
  const fields = [
    "nodeVersion", "chromiumVersion", "platform", "release",
    "architecture", "runId",
  ];
  if (!value || typeof value !== "object" || Array.isArray(value)
      || Object.keys(value).length !== fields.length
      || fields.some((field) => !Object.hasOwn(value, field))) {
    throw new Error("Acceptance environment must be a closed runtime identity.");
  }
  return Object.fromEntries(fields.map((field) => {
    if (typeof value[field] !== "string" || !value[field].trim()) {
      throw new Error(`Acceptance environment ${field} must be a non-empty string.`);
    }
    return [field, value[field].trim()];
  }));
}

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
  if (header.height > CONTENT_REVIEW_SPATIAL_CONTRACT.maxHeaderHeight) {
    throw new Error("Content header exceeds the spatial budget.");
  }
  if (chapterNav.height > CONTENT_REVIEW_SPATIAL_CONTRACT.maxChapterNavHeight) {
    throw new Error("Content chapter navigation exceeds the spatial budget.");
  }
  if (deckIntro.height > CONTENT_REVIEW_SPATIAL_CONTRACT.maxDeckIntroHeight) {
    throw new Error("Content deck intro exceeds the spatial budget.");
  }
  const order = [header, chapterNav, deckIntro, firstChapterHeading, firstSlideHeading, firstReadingGrid];
  for (let index = 0; index < order.length - 1; index += 1) {
    if (order[index].y > order[index + 1].y) {
      throw new Error("Content review regions are not in the approved reading order.");
    }
  }
  if (firstReadingGrid.y >= viewport.height) {
    throw new Error("First-page reading content does not enter the initial viewport.");
  }
  if (!Number.isFinite(measurement?.scrollWidth)
      || !Number.isFinite(measurement?.clientWidth)
      || measurement.scrollWidth > measurement.clientWidth) {
    throw new Error("Content review has horizontal overflow.");
  }
  return {
    viewport,
    header,
    chapterNav,
    deckIntro,
    firstChapterHeading,
    firstSlideHeading,
    firstReadingGrid,
  };
}

export function computeCandidateRegion({ candidateRect, canvasRect, viewport }) {
  const candidate = finiteRect(candidateRect, "Candidate");
  const canvas = finiteRect(canvasRect, "Canvas");
  const measuredViewport = finiteViewport(viewport);
  if (canvas.width <= 0 || canvas.height <= 0) {
    throw new Error("Canvas geometry must have finite positive width and height values.");
  }
  const pixels = {
    x: candidate.x - canvas.x,
    y: candidate.y - canvas.y,
    width: candidate.width,
    height: candidate.height,
  };
  if (Object.values(pixels).some((field) => !Number.isFinite(field))
      || pixels.x < 0 || pixels.y < 0 || pixels.width <= 0 || pixels.height <= 0) {
    throw new Error("Candidate pixel geometry must be finite, non-negative, and positive-sized.");
  }
  const normalized = {
    x: pixels.x / canvas.width,
    y: pixels.y / canvas.height,
    width: pixels.width / canvas.width,
    height: pixels.height / canvas.height,
  };
  if (Object.values(normalized).some((field) => !Number.isFinite(field))
      || normalized.x < 0 || normalized.y < 0
      || normalized.width <= 0 || normalized.height <= 0
      || normalized.width > 1 || normalized.height > 1
      || normalized.x + normalized.width > 1
      || normalized.y + normalized.height > 1) {
    throw new Error("Candidate normalized geometry must be finite, positive, and bounded by the canvas.");
  }
  return { pixels, normalized, viewport: measuredViewport };
}

export async function captureEvidencePair({
  rawPath,
  expandedPath,
  readProductionVisibility,
  captureRaw,
  revealAcceptanceOnly,
  captureExpanded,
}) {
  for (const [name, callback] of Object.entries({
    readProductionVisibility,
    captureRaw,
    revealAcceptanceOnly,
    captureExpanded,
  })) {
    if (typeof callback !== "function") {
      throw new Error(`${name} must be a function.`);
    }
  }
  if (typeof rawPath !== "string" || !rawPath || typeof expandedPath !== "string" || !expandedPath) {
    throw new Error("Evidence screenshots require non-empty paths.");
  }
  if (rawPath === expandedPath) {
    throw new Error("Raw and expanded evidence screenshots require different paths.");
  }
  const visibility = await readProductionVisibility();
  if (visibility !== "auto") {
    throw new Error(`Raw screenshot requires production content-visibility auto; received ${visibility}.`);
  }
  await captureRaw(rawPath);
  await revealAcceptanceOnly();
  await captureExpanded(expandedPath);
  return {
    rawScreenshot: rawPath,
    rawScreenshotMode: "production-content-visibility-auto",
    expandedEvidenceScreenshot: expandedPath,
    expandedEvidenceScreenshotMode: "acceptance-only-content-visibility-visible",
  };
}

export async function atomicPublishAcceptanceReport({
  report,
  reportPath,
  temporaryPath,
  writeFile = writeReportFile,
  rename = renameFile,
}) {
  if (typeof writeFile !== "function" || typeof rename !== "function") {
    throw new Error("Atomic report publication requires writeFile and rename functions.");
  }
  if (typeof reportPath !== "string" || !reportPath
      || typeof temporaryPath !== "string" || !temporaryPath
      || reportPath === temporaryPath
      || path.dirname(reportPath) !== path.dirname(temporaryPath)) {
    throw new Error("Atomic report paths must be different files in the same directory.");
  }
  await writeFile(temporaryPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  await rename(temporaryPath, reportPath);
  return reportPath;
}

export async function completeAcceptanceRun({ runChecks, publishReport }) {
  if (typeof runChecks !== "function" || typeof publishReport !== "function") {
    throw new Error("Acceptance completion requires runChecks and publishReport functions.");
  }
  const report = await runChecks();
  await publishReport(report);
  return report;
}

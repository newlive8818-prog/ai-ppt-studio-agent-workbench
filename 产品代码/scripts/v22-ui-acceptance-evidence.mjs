import path from "node:path";
import { rename as renameFile, writeFile as writeReportFile } from "node:fs/promises";

export const LOCAL_PREVIEW_DISCLAIMER = "Raw screenshots preserve production CSS; expanded evidence screenshots use acceptance-only CSS. Not Codex Browser, host notification, AI receipt, Codex Presentations, or Microsoft PowerPoint proof. Not G3 or user acceptance proof.";

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

import assert from "node:assert/strict";
import test from "node:test";

import {
  LOCAL_PREVIEW_DISCLAIMER,
  assertAcceptanceEnvironment,
  assertLongReviewMeasurement,
  assertLongReviewMeasurementCoverage,
  atomicPublishAcceptanceReport,
  captureEvidencePair,
  completeAcceptanceRun,
  computeCandidateRegion,
} from "../scripts/v22-ui-acceptance-evidence.mjs";

const canvas = { x: 10, y: 20, width: 400, height: 200 };
const viewport = { width: 760, height: 480 };

const longReviewMeasurement = {
  reviewType: "visual",
  count: 120,
  viewport: { width: 1000, height: 900 },
  navigationToReadyMs: 1250.5,
  finalObjectAccessMs: 220.25,
  measurementMode: "local-playwright-measurement-only",
  complete: true,
  finalObjectPresent: true,
  noHorizontalOverflow: true,
  consoleErrorCount: 0,
};

test("long review evidence is closed, finite, successful, and measurement-only", () => {
  assert.deepEqual(assertLongReviewMeasurement(longReviewMeasurement), longReviewMeasurement);
  for (const invalid of [
    { navigationToReadyMs: -1 },
    { navigationToReadyMs: Number.POSITIVE_INFINITY },
    { finalObjectAccessMs: "220" },
    { measurementMode: "performance-passed" },
    { count: 0 },
    { viewport: { width: 0, height: 900 } },
    { complete: false },
    { finalObjectPresent: false },
    { noHorizontalOverflow: false },
    { consoleErrorCount: 1 },
  ]) assert.throws(() => assertLongReviewMeasurement({ ...longReviewMeasurement, ...invalid }));
});

test("acceptance environment requires the exact non-empty runtime identity", () => {
  const environment = {
    nodeVersion: "v25.8.2",
    chromiumVersion: "Chromium 140",
    platform: "darwin",
    release: "25.0.0",
    architecture: "arm64",
    runId: "run-1",
  };
  assert.deepEqual(assertAcceptanceEnvironment(environment), environment);
  for (const field of Object.keys(environment)) {
    assert.throws(() => assertAcceptanceEnvironment({ ...environment, [field]: "  " }));
  }
});

test("long review coverage requires each approved identity exactly once", () => {
  const measurements = [
    { ...longReviewMeasurement, reviewType: "content", count: 10 },
    { ...longReviewMeasurement, reviewType: "content", count: 24 },
    { ...longReviewMeasurement, reviewType: "content", count: 60 },
    longReviewMeasurement,
  ];
  assert.deepEqual(assertLongReviewMeasurementCoverage(measurements), measurements);
  assert.throws(() => assertLongReviewMeasurementCoverage(measurements.slice(0, 3)));
  assert.throws(() => assertLongReviewMeasurementCoverage([
    ...measurements,
    longReviewMeasurement,
  ]));
  assert.throws(() => assertLongReviewMeasurementCoverage([
    ...measurements.slice(0, 3),
    { ...longReviewMeasurement, count: 119 },
  ]));
});

test("candidate evidence is finite, bounded, normalized, and viewport-bound", () => {
  assert.deepEqual(computeCandidateRegion({
    candidateRect: { x: 50, y: 40, width: 200, height: 100 },
    canvasRect: canvas,
    viewport,
  }), {
    pixels: { x: 40, y: 20, width: 200, height: 100 },
    normalized: { x: 0.1, y: 0.1, width: 0.5, height: 0.5 },
    viewport,
  });
});

test("candidate evidence rejects even a tiny canvas overflow instead of clamping it", () => {
  assert.throws(() => computeCandidateRegion({
    candidateRect: { x: 409.999999999, y: 40, width: 0.000000002, height: 20 },
    canvasRect: canvas,
    viewport,
  }), /candidate|bounded/i);
});

test("candidate evidence rejects tiny negative origins and non-number inputs", () => {
  assert.throws(() => computeCandidateRegion({
    candidateRect: { x: 9.999999999, y: 40, width: 20, height: 20 },
    canvasRect: canvas,
    viewport,
  }), /candidate|bounded/i);
  for (const value of ["50", null, true]) {
    assert.throws(() => computeCandidateRegion({
      candidateRect: { x: value, y: 40, width: 20, height: 20 },
      canvasRect: canvas,
      viewport,
    }), /candidate|finite|number/i);
    assert.throws(() => computeCandidateRegion({
      candidateRect: { x: 50, y: 40, width: 20, height: 20 },
      canvasRect: { ...canvas, width: value },
      viewport,
    }), /canvas|finite|number/i);
    assert.throws(() => computeCandidateRegion({
      candidateRect: { x: 50, y: 40, width: 20, height: 20 },
      canvasRect: canvas,
      viewport: { ...viewport, width: value },
    }), /viewport|finite|number/i);
  }
});

for (const [name, candidateRect, canvasRect = canvas] of [
  ["negative origin", { x: 0, y: 40, width: 20, height: 20 }],
  ["right overflow", { x: 390, y: 40, width: 40, height: 20 }],
  ["zero canvas", { x: 10, y: 20, width: 1, height: 1 }, { ...canvas, width: 0 }],
  ["NaN", { x: Number.NaN, y: 20, width: 1, height: 1 }],
  ["Infinity", { x: 10, y: 20, width: Infinity, height: 1 }],
]) test(`candidate evidence rejects ${name}`, () => {
  assert.throws(() => computeCandidateRegion({ candidateRect, canvasRect, viewport }), /candidate|canvas|finite|bounded/i);
});

test("evidence pair captures raw before reveal and expanded after reveal", async () => {
  const events = [];
  const result = await captureEvidencePair({
    rawPath: "/tmp/raw.png",
    expandedPath: "/tmp/expanded.png",
    readProductionVisibility: async () => (events.push("read"), "auto"),
    captureRaw: async (path) => events.push(`raw:${path}`),
    revealAcceptanceOnly: async () => events.push("reveal"),
    captureExpanded: async (path) => events.push(`expanded:${path}`),
  });
  assert.deepEqual(events, ["read", "raw:/tmp/raw.png", "reveal", "expanded:/tmp/expanded.png"]);
  assert.equal(result.rawScreenshot, "/tmp/raw.png");
  assert.equal(result.rawScreenshotMode, "production-content-visibility-auto");
  assert.equal(result.expandedEvidenceScreenshot, "/tmp/expanded.png");
  assert.equal(result.expandedEvidenceScreenshotMode, "acceptance-only-content-visibility-visible");
});

test("evidence pair rejects non-auto visibility before capture and rejects same path", async () => {
  let sideEffects = 0;
  await assert.rejects(captureEvidencePair({
    rawPath: "/tmp/raw.png", expandedPath: "/tmp/expanded.png",
    readProductionVisibility: async () => "visible",
    captureRaw: async () => { sideEffects += 1; },
    revealAcceptanceOnly: async () => { sideEffects += 1; },
    captureExpanded: async () => { sideEffects += 1; },
  }), /production content-visibility/i);
  assert.equal(sideEffects, 0);
  await assert.rejects(captureEvidencePair({
    rawPath: "/tmp/same.png", expandedPath: "/tmp/same.png",
    readProductionVisibility: async () => (sideEffects += 1, "auto"),
    captureRaw: async () => { sideEffects += 1; },
    revealAcceptanceOnly: async () => { sideEffects += 1; },
    captureExpanded: async () => { sideEffects += 1; },
  }), /different paths/i);
  assert.equal(sideEffects, 0);
});

test("evidence pair validates every callback before reading visibility or causing side effects", async () => {
  const missing = Symbol("missing");
  const callbackNames = [
    "readProductionVisibility",
    "captureRaw",
    "revealAcceptanceOnly",
    "captureExpanded",
  ];
  for (const callbackName of callbackNames) {
    for (const invalid of [missing, undefined, null, false, 1, "callback", {}]) {
      const events = [];
      const callbacks = {
        readProductionVisibility: async () => (events.push("read"), "auto"),
        captureRaw: async () => events.push("raw"),
        revealAcceptanceOnly: async () => events.push("reveal"),
        captureExpanded: async () => events.push("expanded"),
      };
      if (invalid === missing) delete callbacks[callbackName];
      else callbacks[callbackName] = invalid;
      await assert.rejects(captureEvidencePair({
        rawPath: "/tmp/raw.png",
        expandedPath: "/tmp/expanded.png",
        ...callbacks,
      }), new RegExp(callbackName, "i"));
      assert.deepEqual(events, []);
    }
  }
});

test("acceptance report publication writes a same-directory temporary file before atomic rename", async () => {
  const events = [];
  const report = { ok: true, runDirectory: "/output/runs/run-1" };
  const result = await atomicPublishAcceptanceReport({
    report,
    reportPath: "/output/v22-ui-acceptance.json",
    temporaryPath: "/output/.v22-ui-acceptance.run-1.tmp",
    writeFile: async (target, contents) => events.push(["write", target, JSON.parse(contents)]),
    rename: async (from, to) => events.push(["rename", from, to]),
  });
  assert.deepEqual(events, [
    ["write", "/output/.v22-ui-acceptance.run-1.tmp", report],
    ["rename", "/output/.v22-ui-acceptance.run-1.tmp", "/output/v22-ui-acceptance.json"],
  ]);
  assert.equal(result, "/output/v22-ui-acceptance.json");
});

test("a runtime callback failure aborts the evidence round without publishing the current report", async () => {
  const failures = [
    ["readProductionVisibility", "read"],
    ["captureRaw", "raw"],
    ["revealAcceptanceOnly", "reveal"],
    ["captureExpanded", "expanded"],
  ];
  for (const [failedCallback, message] of failures) {
    const failure = new Error(message);
    let publishes = 0;
    await assert.rejects(completeAcceptanceRun({
      runChecks: () => captureEvidencePair({
        rawPath: "/output/runs/run-1/raw.png",
        expandedPath: "/output/runs/run-1/expanded.png",
        readProductionVisibility: async () => {
          if (failedCallback === "readProductionVisibility") throw failure;
          return "auto";
        },
        captureRaw: async () => {
          if (failedCallback === "captureRaw") throw failure;
        },
        revealAcceptanceOnly: async () => {
          if (failedCallback === "revealAcceptanceOnly") throw failure;
        },
        captureExpanded: async () => {
          if (failedCallback === "captureExpanded") throw failure;
        },
      }),
      publishReport: async () => { publishes += 1; },
    }), (caught) => caught === failure);
    assert.equal(publishes, 0);
  }
});

test("local preview disclaimer excludes every formal proof class", () => {
  for (const value of ["Codex Browser", "host notification", "AI receipt", "Codex Presentations", "Microsoft PowerPoint", "G3", "user acceptance"]) {
    assert.match(LOCAL_PREVIEW_DISCLAIMER, new RegExp(value, "i"));
  }
});

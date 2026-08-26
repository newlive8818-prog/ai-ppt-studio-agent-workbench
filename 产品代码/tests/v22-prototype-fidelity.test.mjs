import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  CONTENT_REVIEW_SPATIAL_CONTRACT,
  LOCAL_PREVIEW_EVIDENCE,
  PROTOTYPE_FIDELITY_REQUIREMENTS,
  REQUIRED_INTERACTION_STATES,
  assertContentReviewSpatialFidelity,
  assertInteractionEvidenceCoverage,
  assertPrototypeFidelityCounts,
} from "../scripts/v22-ui-acceptance-evidence.mjs";

const runnerSource = readFileSync(new URL("../scripts/run-v22-ui-acceptance.mjs", import.meta.url), "utf8");

const expectedSelectors = {
  "content-review": [
    ".content-review-vm-deck-intro",
    ".content-review-vm-chapter-nav",
    ".content-review-vm-chapter",
    "[data-content-review-vm-slide]",
    ".content-review-vm-summary",
  ],
  "visual-anchor": [
    ".visual-review-topbar",
    ".visual-professional-review-view-switch",
    ".anchor-review-layout",
    ".anchor-feedback-composer",
  ],
  "visual-contract": [
    ".visual-contract-title-page",
    '[data-contract-logical-object="anchor-slide-evidence"]',
    ".visual-slide-contract",
    ".visual-contract-outline",
    ".visual-overlay-drawer",
  ],
};

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

test("prototype fidelity requirements cover the approved 08, 07, and contract regions", () => {
  assert.deepEqual(Object.keys(PROTOTYPE_FIDELITY_REQUIREMENTS), Object.keys(expectedSelectors));
  for (const [surface, selectors] of Object.entries(expectedSelectors)) {
    const actual = PROTOTYPE_FIDELITY_REQUIREMENTS[surface].map((requirement) => requirement.selector);
    for (const selector of selectors) assert.ok(actual.includes(selector), `${surface} missing ${selector}`);
  }
});

test("every prototype region fails closed when its selector count is empty", () => {
  for (const [surface, requirements] of Object.entries(PROTOTYPE_FIDELITY_REQUIREMENTS)) {
    const valid = Object.fromEntries(requirements.map((requirement) => [
      requirement.key,
      requirement.exact ?? requirement.min,
    ]));
    assert.doesNotThrow(() => assertPrototypeFidelityCounts(surface, valid));
    for (const requirement of requirements) {
      const missing = { ...valid, [requirement.key]: 0 };
      assert.throws(
        () => assertPrototypeFidelityCounts(surface, missing),
        new RegExp(`${surface}.*${requirement.key}`, "i"),
      );
    }
  }
});

test("interaction evidence requires every approved before, after, drawer, and receipt state exactly once", () => {
  assert.deepEqual(REQUIRED_INTERACTION_STATES, [
    "content-before-feedback",
    "content-after-non-approved-feedback",
    "anchor-before-rectangle-feedback",
    "anchor-after-rectangle-feedback",
    "contract-with-anchor-slide-evidence",
    "contract-directory-drawer",
    "contract-mark-drawer",
    "saved-unverified-receipt",
  ]);
  const complete = REQUIRED_INTERACTION_STATES.map((state) => ({ state, screenshot: `/evidence/${state}.png` }));
  assert.doesNotThrow(() => assertInteractionEvidenceCoverage(complete));
  for (const state of REQUIRED_INTERACTION_STATES) {
    assert.throws(
      () => assertInteractionEvidenceCoverage(complete.filter((entry) => entry.state !== state)),
      new RegExp(state, "i"),
    );
  }
  assert.throws(
    () => assertInteractionEvidenceCoverage([...complete, complete[0]]),
    /duplicate|exactly once/i,
  );
});

test("local preview evidence can never claim real-host or formal proof", () => {
  assert.deepEqual(LOCAL_PREVIEW_EVIDENCE, {
    evidenceScope: "local-development-preview",
    proofEligible: false,
    realHostEvidence: false,
  });
  assert.equal(Object.isFrozen(LOCAL_PREVIEW_EVIDENCE), true);
});

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

test("browser runner consumes the fidelity contracts and scopes readability to each current slide contract", () => {
  assert.match(runnerSource, /assertContentReviewSpatialFidelity/);
  assert.match(runnerSource, /assertPrototypeFidelityCounts/);
  assert.match(runnerSource, /assertInteractionEvidenceCoverage/);
  assert.match(runnerSource, /PROTOTYPE_FIDELITY_REQUIREMENTS/);
  assert.match(runnerSource, /LOCAL_PREVIEW_EVIDENCE/);
  assert.match(runnerSource, /data-content-review-vm-slide.*content-review-vm-reading-grid/);
  assert.match(runnerSource, /firstViewportScreenshot/);
  assert.doesNotMatch(runnerSource, /\.visual-contract-title-page code/);
  assert.match(runnerSource, /contract\.locator\(slideReadableSelector\)/);
  for (const token of [
    "assertLongReviewMeasurement",
    "assertAcceptanceEnvironment",
    "performance.now()",
    "chromiumVersion",
    "longReviewMeasurements",
    "local-playwright-measurement-only",
  ]) assert.ok(runnerSource.includes(token), `browser runner missing ${token}`);
});

test("browser runner covers mixed image and zero-image content reviews", () => {
  assert.match(runnerSource, /mixedContentProjectionHtml/);
  assert.match(runnerSource, /content-review-vm-reading-grid--text-only/);
  assert.match(runnerSource, /content-review-vm-reading-grid--with-visuals/);
  assert.match(runnerSource, /本页暂无可审核的页面画面/);
  for (const count of [10, 24, 60]) {
    assert.match(runnerSource, new RegExp(`\\["content", ${count}\\]`));
  }
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  LOCAL_PREVIEW_EVIDENCE,
  PROTOTYPE_FIDELITY_REQUIREMENTS,
  REQUIRED_INTERACTION_STATES,
  assertInteractionEvidenceCoverage,
  assertPrototypeFidelityCounts,
} from "../scripts/v22-ui-acceptance-evidence.mjs";

const runnerSource = readFileSync(new URL("../scripts/run-v22-ui-acceptance.mjs", import.meta.url), "utf8");

const expectedSelectors = {
  "content-review": [
    ".content-review-deck-intro",
    ".content-review-chapter-nav",
    "[data-content-chapter]",
    ".content-review-summary",
  ],
  "visual-anchor": [
    ".visual-review-topbar",
    ".visual-professional-review-view-switch",
    ".anchor-review-layout",
    ".anchor-feedback-composer",
    ".anchor-review-assistant .anchor-batch-panel",
  ],
  "visual-contract": [
    ".visual-contract-title-page",
    '[data-contract-logical-object="anchor-slide-evidence"]',
    ".visual-slide-contract",
    ".visual-contract-outline",
    ".visual-overlay-drawer",
  ],
};

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

test("browser runner consumes the fidelity contracts and scopes readability to each current slide contract", () => {
  assert.match(runnerSource, /assertPrototypeFidelityCounts/);
  assert.match(runnerSource, /assertInteractionEvidenceCoverage/);
  assert.match(runnerSource, /PROTOTYPE_FIDELITY_REQUIREMENTS/);
  assert.match(runnerSource, /LOCAL_PREVIEW_EVIDENCE/);
  assert.doesNotMatch(runnerSource, /\.visual-contract-title-page code/);
  assert.match(runnerSource, /contract\.locator\(slideReadableSelector\)/);
});

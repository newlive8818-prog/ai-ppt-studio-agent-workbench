import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterAll, afterEach, describe, expect, it } from "vitest";

import { createBrowserReviewClient } from "../lib/browser-review-client";
import type {
  ContractMarkComposerState,
  ContractMarkDraftState,
} from "../review-draft/reviewDraftStore";
import type { VisualReviewSurfaceData } from "../types/visual-review";
import { VisualContractView } from "./VisualContractView";
import { toVisualReviewPageViewModel } from "./visual-review-page-view-model";

const SOURCE_ROOT = resolve(process.cwd());
const PYTHON_EXECUTABLE = process.env.AI_PPT_PYTHON || "python3";
const TEST_TMPDIR = tmpdir();
const TEST_PROJECT_PREFIX = "r3-text-anchor-test-";
const projectRoots = new Set<string>();
const originalFetch = globalThis.fetch;
const initialTempProjects = readdirSync(TEST_TMPDIR)
  .filter((name) => name.startsWith(TEST_PROJECT_PREFIX))
  .sort();
const canonicalReview = JSON.parse(readFileSync(
  `${SOURCE_ROOT}/widget/src/__fixtures__/review-projection.visual.json`,
  "utf8",
)).review as Record<string, unknown>;

interface Example {
  name: string;
  targetKey: string;
  selectedText: string;
  comment?: string;
  override?: string;
  numericTokenOrder?: boolean;
  longNumericTokenOrder?: boolean;
  mixedColorTokens?: boolean;
  occurrence?: number;
  deckSectionId?: "" | "visual-brief" | "deck-design-system";
  slideId?: string;
}

interface Seed {
  projectRoot: string;
  review: Record<string, unknown>;
  revision: number;
}

interface DispatchOutcome {
  accepted: boolean;
  error?: string;
  forgedRejected: boolean;
  forgedZeroWrite: boolean;
  markSetRef?: string;
  markSet?: Record<string, unknown>;
  snapshotRevision?: number;
}

function python<T>(code: string, payload: unknown): T {
  const result = spawnSync(PYTHON_EXECUTABLE, ["-c", code], {
    cwd: SOURCE_ROOT,
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
      TMPDIR: TEST_TMPDIR,
      PYTHONPATH: resolve(SOURCE_ROOT, "src"),
    },
    input: JSON.stringify(payload),
    encoding: "utf8",
  });
  if (result.status !== 0) throw new Error(result.stderr || result.stdout);
  return JSON.parse(result.stdout) as T;
}

function seedReview(example: Example): Seed {
  const projectRoot = mkdtempSync(join(TEST_TMPDIR, TEST_PROJECT_PREFIX));
  projectRoots.add(projectRoot);
  return python<Seed>(`import json, sys
from pathlib import Path
import tests.test_v22_visual_review_service as fixtures
from ai_ppt_studio.application.visual_review_service import VisualReviewService
from ai_ppt_studio.kernel.transactions import ProjectKernel

example = json.load(sys.stdin)
if example.get("override"):
    original = fixtures.valid_visual_brief
    def overridden(*args, **kwargs):
        value = original(*args, **kwargs)
        value["decision_task"] = example["override"]
        return value
    fixtures.valid_visual_brief = overridden

if example.get("numericTokenOrder"):
    original_design_system = fixtures.valid_design_system
    def overridden_design_system(*args, **kwargs):
        value = original_design_system(*args, **kwargs)
        value["typography_tokens"] = {
            "10": "ten-value",
            "2": "two-value",
            "body": "body-value",
        }
        return value
    fixtures.valid_design_system = overridden_design_system

if example.get("longNumericTokenOrder"):
    original_design_system = fixtures.valid_design_system
    def overridden_long_numeric_design_system(*args, **kwargs):
        value = original_design_system(*args, **kwargs)
        value["typography_tokens"] = {
            "1" * 5000: "business-value",
            "2": "two-value",
            "body": "body-value",
        }
        return value
    fixtures.valid_design_system = overridden_long_numeric_design_system

if example.get("mixedColorTokens"):
    original_design_system = fixtures.valid_design_system
    def overridden_mixed_color_design_system(*args, **kwargs):
        value = original_design_system(*args, **kwargs)
        value["color_tokens"] = {
            "a_semantic": "brand-blue",
            "b_accent": "#3157D5",
            "c_ink": "#172033",
        }
        return value
    fixtures.valid_design_system = overridden_mixed_color_design_system

root = Path(example["projectRoot"])
kernel = ProjectKernel.initialize(root, project_id="p1")
_, _, _, _, session, state = fixtures.seed_visual_review(kernel)
review = VisualReviewService(kernel).project(session["review_session_id"])
review["review_session"].pop("review_status", None)
print(json.dumps({
    "projectRoot": str(root),
    "review": review,
    "revision": state.revision,
}, ensure_ascii=False))`, { ...example, projectRoot });
}

function dispatchMark(projectRoot: string, body: Record<string, unknown>): DispatchOutcome {
  return python<DispatchOutcome>(`import copy, json, sys
from pathlib import Path
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError

input = json.load(sys.stdin)
root = Path(input["projectRoot"])
body = input["body"]
request = {
    "operation": "save-visual-contract-review-marks",
    "project_root": str(root),
    "expected_revision": body["expectedRevision"],
    "review_session_id": body["reviewSessionId"],
    "source_version": body["sourceVersion"],
    "marks": body["marks"],
}
before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
forged = copy.deepcopy(request)
forged["marks"][0]["context_before"] = "伪造或过期的前文"
try:
    dispatch_v16(forged)
    forged_rejected = False
except ContractValidationError:
    forged_rejected = True
after_forgery = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}

try:
    saved = dispatch_v16(request)["result"]
    accepted = True
    error = None
except ContractValidationError as exc:
    saved = {}
    accepted = False
    error = str(exc)

print(json.dumps({
    "accepted": accepted,
    "error": error,
    "forgedRejected": forged_rejected,
    "forgedZeroWrite": before == after_forgery,
    "markSetRef": saved.get("mark_set_ref"),
    "markSet": saved.get("mark_set"),
    "snapshotRevision": (saved.get("snapshot") or {}).get("revision"),
}, ensure_ascii=False))`, { projectRoot, body });
}

function Harness({ data, bridge, revision }: {
  data: ReturnType<typeof toVisualReviewPageViewModel>;
  bridge: ReturnType<typeof createBrowserReviewClient>;
  revision: number;
}) {
  const [drafts, setDrafts] = useState<ContractMarkDraftState[]>([]);
  const [composer, setComposer] = useState<ContractMarkComposerState | null>(null);
  return (
    <VisualContractView
      data={data}
      bridge={bridge}
      revision={revision}
      onRevision={() => undefined}
      commandIdentity="text-anchor-integration"
      drafts={drafts}
      composer={composer}
      onSliceChange={(nextDrafts, nextComposer) => {
        setDrafts(nextDrafts);
        setComposer(nextComposer);
      }}
      onClearSlice={() => {
        setDrafts([]);
        setComposer(null);
      }}
    />
  );
}

async function submitSelectedText(example: Example) {
  const seed = seedReview(example);
  const reviewFixture = structuredClone(canonicalReview);
  for (const key of [
    "project_id",
    "project_name",
    "review_session_id",
    "review_session",
    "source_version",
    "revision",
    "authoritative_revision",
    "visual_contract_ref",
    "visual_brief_ref",
    "visual_brief",
    "deck_design_system_ref",
    "deck_design_system",
    "anchor_slide_set_ref",
    "anchor_identity",
  ]) {
    reviewFixture[key] = structuredClone(seed.review[key]);
  }
  const runtimeSlide = (seed.review.slide_visual_contracts as Array<Record<string, unknown>>)
    .find((slide) => slide.slide_id === "S01");
  const fixtureSlide = (reviewFixture.slide_visual_contracts as Array<Record<string, unknown>>)
    .find((slide) => slide.slide_id === "S01");
  if (!runtimeSlide || !fixtureSlide) throw new Error("Missing S01 visual contract");
  for (const key of [
    "regions",
    "acceptance_criteria",
    "asset_roles",
    "powerpoint_implementation_requirements",
  ]) fixtureSlide[key] = structuredClone(runtimeSlide[key]);

  let reads = 0;
  let capturedPost: Record<string, unknown> | undefined;
  let outcome: DispatchOutcome | undefined;
  globalThis.fetch = async (path, init = {}) => {
    if (path === "/api/review") {
      const review = structuredClone(reviewFixture);
      const revision = reads++ === 0 ? seed.revision - 1 : seed.revision;
      review.authoritative_revision = revision;
      return new Response(JSON.stringify({
        ok: true,
        projectRoot: seed.projectRoot,
        reviewType: "visual-professional",
        sourceVersion: review.source_version,
        expectedRevision: revision,
        bridgeSessionId: "text-anchor-test-session",
        review,
      }));
    }
    if (path === "/api/host-open") {
      return new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: seed.revision,
      }));
    }
    if (path === "/api/heartbeat") return new Response("{}");
    expect(path).toBe("/api/visual/marks");
    expect(init.method).toBe("POST");
    capturedPost = JSON.parse(String(init.body)) as Record<string, unknown>;
    outcome = dispatchMark(seed.projectRoot, capturedPost);
    if (!outcome.accepted) {
      return new Response(JSON.stringify({
        ok: false,
        error: { code: "CONTRACT_VALIDATION_ERROR", message: outcome.error },
      }), { status: 400 });
    }
    return new Response(JSON.stringify({
      ok: true,
      markSetRef: outcome.markSetRef,
      markSet: outcome.markSet,
      snapshotRevision: outcome.snapshotRevision,
      hostNotificationStatus: "unavailable",
      aiReceiptStatus: "unverified",
    }));
  };

  window.history.replaceState({}, "", "/#token=text-anchor-test-token");
  const client = createBrowserReviewClient();
  let connected: VisualReviewSurfaceData | undefined;
  await client.connect((data) => { connected = data as VisualReviewSurfaceData; });
  if (!connected) throw new Error("Browser client did not return a visual review projection");
  const data = toVisualReviewPageViewModel(connected);
  render(<Harness data={data} bridge={client} revision={seed.revision} />);

  const deckSectionId = example.deckSectionId ?? "visual-brief";
  const field = [...document.querySelectorAll<HTMLElement>(`[data-contract-key="${example.targetKey}"]`)]
    .find((candidate) => (
      candidate.dataset.deckSectionId === deckSectionId
      && candidate.dataset.slideId === (example.slideId || "")
    ));
  if (!field) throw new Error(`Missing contract field ${example.targetKey}`);
  const leaf = [...field.querySelectorAll<HTMLElement>("[data-contract-anchor-leaf]")]
    .find((candidate) => (candidate.textContent || "").includes(example.selectedText));
  const text = [...(leaf?.childNodes || [])]
    .find((node): node is Text => (
      node.nodeType === Node.TEXT_NODE
      && Boolean(node.textContent?.includes(example.selectedText))
    ));
  if (!text) throw new Error(`Missing text leaf for ${example.selectedText}`);
  const occurrence = example.occurrence || 0;
  let offset = -1;
  for (let index = 0; index <= occurrence; index += 1) {
    offset = text.textContent?.indexOf(example.selectedText, offset + 1) ?? -1;
  }
  if (offset < 0) throw new Error(`Missing selected text ${example.selectedText}`);
  const range = document.createRange();
  range.setStart(text, offset);
  range.setEnd(text, offset + example.selectedText.length);
  const selection = window.getSelection();
  if (!selection) throw new Error("Selection API is unavailable");
  selection.removeAllRanges();
  selection.addRange(range);
  fireEvent.mouseUp(field);
  fireEvent.click(screen.getByRole("button", { name: "标记选中文字" }));
  fireEvent.change(screen.getByLabelText("合同标记意见"), {
    target: { value: example.comment ?? "请复核这段文字" },
  });
  fireEvent.click(screen.getByRole("button", { name: "加入合同标记" }));
  fireEvent.click(screen.getByRole("button", { name: "保存 1 条合同标记" }));
  await waitFor(() => expect(outcome).toBeDefined());
  if (outcome && !outcome.accepted) {
    throw new Error(`Runtime rejected Browser text anchor: ${outcome.error || "unknown error"}`);
  }
  await waitFor(() => expect(screen.getByText("合同标记已保存")).toBeTruthy());
  expect(screen.queryByRole("button", { name: "保存 1 条合同标记" })).toBeNull();

  const marks = capturedPost?.marks as Array<Record<string, unknown>> | undefined;
  const returnedMarks = outcome?.markSet?.marks as Array<Record<string, unknown>> | undefined;
  return { mark: marks?.[0], returnedMark: returnedMarks?.[0], outcome };
}

afterEach(() => {
  window.getSelection()?.removeAllRanges();
  cleanup();
  globalThis.fetch = originalFetch;
  for (const projectRoot of projectRoots) {
    rmSync(projectRoot, { recursive: true, force: true });
  }
  projectRoots.clear();
});

afterAll(() => {
  expect(globalThis.fetch).toBe(originalFetch);
  expect(
    readdirSync(TEST_TMPDIR)
      .filter((name) => name.startsWith(TEST_PROJECT_PREFIX))
      .sort(),
  ).toEqual(initialTempProjects);
});

describe("visual contract text anchor production boundary", () => {
  it.each([
    {
      name: "space-delimited field",
      targetKey: "decision_task",
      selectedText: "gamma",
      override: "alpha beta gamma delta",
      expectedBefore: "alpha beta",
      expectedAfter: "delta",
    },
    {
      name: "second duplicate occurrence",
      targetKey: "decision_task",
      selectedText: "alpha",
      override: "alpha beta alpha",
      occurrence: 1,
      expectedBefore: "alpha beta",
      expectedAfter: "",
    },
    {
      name: "ECMAScript whitespace with BOM",
      targetKey: "decision_task",
      selectedText: "beta",
      override: "\uFEFFalpha beta",
      expectedBefore: "alpha",
      expectedAfter: "",
    },
    {
      name: "ECMAScript internal BOM whitespace",
      targetKey: "decision_task",
      selectedText: "beta",
      override: "alpha\uFEFF beta",
      expectedBefore: "alpha",
      expectedAfter: "",
    },
    {
      name: "non-ECMAScript NEL character",
      targetKey: "decision_task",
      selectedText: "beta",
      override: "alpha\u0085beta",
      expectedBefore: "alpha\u0085",
      expectedAfter: "",
    },
  ] satisfies Array<Example & { expectedBefore: string; expectedAfter: string }>) (
    "accepts $name from the actual DOM Range and rejects forged context without writes",
    async ({ expectedBefore, expectedAfter, ...example }) => {
      const { mark, returnedMark, outcome } = await submitSelectedText(example);

      expect(mark).toEqual(expect.objectContaining({
        selected_text: example.selectedText,
        context_before: expectedBefore,
        context_after: expectedAfter,
        anchor_representation_version: "browser-v2",
      }));
      expect(returnedMark?.anchor_representation_version).toBe("browser-v2");
      expect(outcome).toEqual(expect.objectContaining({
        accepted: true,
        forgedRejected: true,
        forgedZeroWrite: true,
      }));
    },
  );

  it("anchors a structured field to values without persisting presentation labels", async () => {
    const example: Example = {
      name: "structured visual brief",
      targetKey: "five_second_test_contract",
      selectedText: "五秒后隐藏页面并记录第一判断",
    };
    const { mark, outcome } = await submitSelectedText(example);

    expect(mark?.selected_text).toBe(example.selectedText);
    expect(mark?.context_before).toBe("");
    expect(mark?.context_after).toMatch(/^读者形成与页面合同一致的核心判断/);
    expect(mark?.context_after).not.toMatch(/expected judgment|record fields/);
    expect(outcome).toEqual(expect.objectContaining({
      accepted: true,
      forgedRejected: true,
      forgedZeroWrite: true,
    }));
  });

  it("uses Unicode code-point windows for a repeated selection surrounded by non-BMP text", async () => {
    const surroundingText = "😀".repeat(100);
    const example: Example = {
      name: "second duplicate occurrence with non-BMP context",
      targetKey: "decision_task",
      selectedText: "目标",
      override: `${surroundingText}目标${surroundingText}目标${surroundingText}`,
      occurrence: 1,
    };
    const { mark, outcome } = await submitSelectedText(example);

    expect(mark).toEqual(expect.objectContaining({
      selected_text: example.selectedText,
      context_before: "😀".repeat(80),
      context_after: "😀".repeat(80),
    }));
    expect(outcome).toEqual(expect.objectContaining({
      accepted: true,
      forgedRejected: true,
      forgedZeroWrite: true,
    }));
  });

  it("matches Browser property order for integer-like token-map keys", async () => {
    const example: Example = {
      name: "integer-like typography token keys",
      targetKey: "typography_tokens",
      selectedText: "two-value",
      numericTokenOrder: true,
      deckSectionId: "deck-design-system",
    };
    const { mark, outcome } = await submitSelectedText(example);

    expect(mark?.selected_text).toBe(example.selectedText);
    expect(mark?.context_before).toBe("");
    expect(mark?.context_after).toMatch(/^ten-value body-value/);
    expect(outcome).toEqual(expect.objectContaining({
      accepted: true,
      forgedRejected: true,
      forgedZeroWrite: true,
    }));
  });

  it("treats an oversized numeric token key as an ordinary Browser property", async () => {
    const example: Example = {
      name: "oversized numeric typography token key",
      targetKey: "typography_tokens",
      selectedText: "business-value",
      longNumericTokenOrder: true,
      deckSectionId: "deck-design-system",
    };
    const { mark, outcome } = await submitSelectedText(example);

    expect(mark).toEqual(expect.objectContaining({
      selected_text: example.selectedText,
      context_before: "two-value",
      context_after: "body-value Microsoft YaHei PingFang SC",
      anchor_representation_version: "browser-v2",
    }));
    expect(outcome).toEqual(expect.objectContaining({
      accepted: true,
      forgedRejected: true,
      forgedZeroWrite: true,
    }));
  });

  it("preserves mixed semantic and CSS color tokens in the Browser anchor representation", async () => {
    const example: Example = {
      name: "mixed semantic and CSS color tokens",
      targetKey: "color_tokens",
      selectedText: "#3157D5",
      mixedColorTokens: true,
      deckSectionId: "deck-design-system",
    };
    const { mark, outcome } = await submitSelectedText(example);

    expect(mark).toEqual(expect.objectContaining({
      selected_text: example.selectedText,
      context_before: "brand-blue",
      context_after: "#172033",
      anchor_representation_version: "browser-v2",
    }));
    expect(outcome).toEqual(expect.objectContaining({
      accepted: true,
      forgedRejected: true,
      forgedZeroWrite: true,
    }));
  });

  it("preserves non-ECMAScript edge separators in the saved comment", async () => {
    const comment = "\u0085审阅意见\u001C";
    const example: Example = {
      name: "comment with non-ECMAScript edge separators",
      targetKey: "decision_task",
      selectedText: "gamma",
      override: "alpha beta gamma delta",
      comment,
    };
    const { mark, returnedMark, outcome } = await submitSelectedText(example);

    expect(mark?.comment).toBe(comment);
    expect(returnedMark?.comment).toBe(comment);
    expect(outcome).toEqual(expect.objectContaining({
      accepted: true,
      forgedRejected: true,
      forgedZeroWrite: true,
    }));
  });

  it.each([
    {
      name: "fallback font merged into typography",
      targetKey: "typography_tokens",
      selectedText: "PingFang SC",
      deckSectionId: "deck-design-system",
    },
    {
      name: "anchor specification projected from current anchor identity",
      targetKey: "anchor_specification",
      selectedText: "S01",
      deckSectionId: "deck-design-system",
    },
    {
      name: "boolean leaf in a slide contract",
      targetKey: "asset_roles",
      selectedText: "true",
      deckSectionId: "",
      slideId: "S01",
    },
    {
      name: "region object projected into Browser field order",
      targetKey: "regions",
      selectedText: "facts",
      deckSectionId: "",
      slideId: "S01",
    },
    {
      name: "acceptance criterion projected into Browser field order",
      targetKey: "acceptance_criteria",
      selectedText: "must-follow",
      deckSectionId: "",
      slideId: "S01",
    },
    {
      name: "nested PowerPoint requirement projected into Browser field order",
      targetKey: "powerpoint_implementation_requirements",
      selectedText: "primary-subject",
      deckSectionId: "",
      slideId: "S01",
    },
  ] satisfies Example[])(
    "accepts $name using the same Browser and Runtime anchor representation",
    async (example) => {
      const { mark, outcome } = await submitSelectedText(example);

      expect(mark?.selected_text).toBe(example.selectedText);
      expect(outcome).toEqual(expect.objectContaining({
        accepted: true,
        forgedRejected: true,
        forgedZeroWrite: true,
      }));
    },
  );
});

import { afterEach, describe, expect, it, vi } from "vitest";

import type { ContentReviewSurfaceData } from "../types/content-review";
import type { VisualReviewPageViewModel } from "../visual-review/visual-review-page-view-model";
import {
  DESIGN_SYSTEM_FIELD_ORDER,
  REVIEWABLE_SLIDE_FIELD_KEYS,
  VISUAL_BRIEF_FIELD_ORDER,
} from "../visual-review/visual-contract-field-contract";
import {
  REVIEW_DRAFT_MAX_RAW_BYTES,
  applyReviewDraftUpdate,
  clonePlainData,
  createReviewDraftContext,
  createReviewDraftEnvelope,
  discardReviewDraft,
  loadReviewDraft,
  reviewDraftPageIdentity,
  reviewDraftStorageKey,
  saveReviewDraft,
  validateReviewDraftEnvelope,
  type ContentReviewDraftContext,
  type ContentReviewDraftUi,
  type ReviewDraftStorage,
  type VisualReviewDraftContext,
  type VisualReviewDraftUi,
} from "./reviewDraftStore";

function nestedPlainData(depth: number): unknown {
  let value: unknown = "leaf";
  for (let index = 0; index < depth; index += 1) value = { child: value };
  return value;
}

function contentContext(overrides: Partial<ContentReviewDraftContext> = {}): ContentReviewDraftContext {
  return {
    reviewType: "content",
    projectId: "project-1",
    reviewSessionId: "content-session-1",
    sourceVersion: "content-v1",
    sourceRevision: 7,
    lineage: { readingBlueprintRef: `artifact://reading-deck-blueprint/${"a".repeat(64)}` },
    slideIds: ["S01", "S02"],
    ...overrides,
  };
}

function visualContext(overrides: Partial<VisualReviewDraftContext> = {}): VisualReviewDraftContext {
  return {
    reviewType: "visual",
    projectId: "project-1",
    reviewSessionId: "visual-session-1",
    sourceVersion: "visual-v1",
    sourceRevision: 8,
    lineage: {
      visualContractRef: `artifact://visual-contract/${"b".repeat(64)}`,
      anchorSlideSetRef: `artifact://anchor-slide-set/${"c".repeat(64)}`,
      deckDesignSystemRef: `artifact://deck-design-system/${"d".repeat(64)}`,
    },
    anchorSlideIds: ["A01", "A02"],
    visualContractFields: {
      S01: ["composition_intent", "page_family"],
      S02: ["composition_intent"],
    },
    visualBriefFields: [...VISUAL_BRIEF_FIELD_ORDER],
    deckDesignSystemFields: ["typography_tokens"],
    ...overrides,
  };
}

function contentUi(): ContentReviewDraftUi {
  return {
    view: "document",
    current_slide_id: "S01",
    page_drafts: [{ slide_id: "S01", decision: "modify", comment: "调整问题表述" }],
    logical_scroll: { object_id: "S01", offset: 320 },
  };
}

function visualUi(): VisualReviewDraftUi {
  return {
    view: "contract",
    current_anchor_slide_id: "A01",
    anchor_feedback_drafts: [{
      feedback_id: "feedback-1",
      anchor_slide_id: "A01",
      normalized_region: { x: 0.1, y: 0.2, width: 0.3, height: 0.25 },
      comment: "降低标题重量",
      created_at: "2026-08-15T00:00:00.123456Z",
    }],
    anchor_feedback_composer: {
      anchor_slide_id: "A01",
      candidate_region: { x: 0.15, y: 0.25, width: 0.2, height: 0.2 },
      editing_feedback_id: "feedback-1",
      comment: "编辑锚点意见",
    },
    contract_mark_drafts: [{
      mark_id: "mark-1",
      target_type: "contract-field",
      slide_id: "S01",
      deck_section_id: "",
      target_key: "composition_intent",
      selected_text: "",
      context_before: "",
      context_after: "",
      comment: "收紧因果链",
      created_at: "2026-08-15T00:00:01+08:00",
    }],
    contract_mark_composer: {
      editing_mark_id: "mark-1",
      target_type: "contract-field",
      slide_id: "S01",
      deck_section_id: "",
      target_key: "composition_intent",
      selected_text: "",
      context_before: "",
      context_after: "",
      comment: "编辑合同意见",
    },
    anchor_logical_scroll: { object_id: "A01", offset: 640 },
    contract_logical_scroll: { object_id: "deck-design-system", offset: 280 },
  };
}

function visualTextRangeEditingUi(): VisualReviewDraftUi {
  const ui = visualUi();
  ui.contract_mark_drafts[0] = {
    ...ui.contract_mark_drafts[0],
    target_type: "text-range",
    selected_text: "左侧事实",
    context_before: "标题",
    context_after: "右侧因果链",
  };
  ui.contract_mark_composer = {
    editing_mark_id: "mark-1",
    target_type: "text-range",
    slide_id: "S01",
    deck_section_id: "",
    target_key: "composition_intent",
    selected_text: "左侧事实",
    context_before: "标题",
    context_after: "右侧因果链",
    comment: "允许修改意见正文",
  };
  return ui;
}

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  const storage: ReviewDraftStorage = {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => { values.set(key, value); }),
    removeItem: vi.fn((key: string) => { values.delete(key); }),
  };
  return { storage, values };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("review draft store", () => {
  it("fails closed without throwing for cyclic and trap-backed hostile values", () => {
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;
    const throwingPrototype = new Proxy({}, {
      getPrototypeOf() {
        throw new Error("host prototype trap");
      },
    });

    expect(() => clonePlainData(cyclic)).not.toThrow();
    expect(clonePlainData(cyclic)).toBeUndefined();
    expect(() => clonePlainData(throwingPrototype)).not.toThrow();
    expect(clonePlainData(throwingPrototype)).toBeUndefined();
  });

  it("accepts plain-data depth 64 and rejects depth 65", () => {
    expect(clonePlainData(nestedPlainData(64))).toBeDefined();
    expect(clonePlainData(nestedPlainData(65))).toBeUndefined();
  });

  it("rejects a plain-data graph that exceeds the 20,000-node budget", () => {
    const oversized = Object.fromEntries(
      Array.from({ length: 20_000 }, (_, index) => [`field_${index}`, index]),
    );

    expect(clonePlainData(oversized)).toBeUndefined();
  });

  it("rejects a plain array longer than 4,096 items", () => {
    expect(clonePlainData(Array.from({ length: 4_097 }, (_, index) => index))).toBeUndefined();
  });

  it("uses data descriptors only and never invokes accessors", () => {
    let getterReads = 0;
    const accessor = {};
    Object.defineProperty(accessor, "value", {
      enumerable: true,
      get() {
        getterReads += 1;
        return "poison";
      },
    });

    expect(clonePlainData(accessor)).toBeUndefined();
    expect(getterReads).toBe(0);
  });

  it("builds the exact six-segment key with URL-encoded identity segments", () => {
    const context = contentContext({
      projectId: "project:/ 中文",
      reviewSessionId: "session/with:colon",
      sourceVersion: "source v1/版本",
      sourceRevision: 17,
    });

    expect(reviewDraftStorageKey(context)).toBe(
      `ai-ppt-review-draft:v1:${encodeURIComponent(context.projectId)}:content:${encodeURIComponent(context.reviewSessionId)}:${encodeURIComponent(context.sourceVersion)}:17`,
    );
  });

  it("derives sourceRevision only from review.revision and keeps the key stable as snapshot grows", () => {
    const initial = {
      snapshotRevision: 40,
      review: {
        review_type: "content-full-deck",
        project_id: "project-1",
        review_session_id: "session-1",
        source_version: "content-v1",
        revision: 7,
        authoritative_revision: 39,
        reading_blueprint_ref: "blueprint-1",
        slides: [{ slide_id: "S01" }],
      },
    } as unknown as ContentReviewSurfaceData;
    const grown = structuredClone(initial);
    grown.snapshotRevision = 99;
    grown.review.authoritative_revision = 98;

    const first = createReviewDraftContext(initial);
    const second = createReviewDraftContext(grown);

    expect(first.sourceRevision).toBe(7);
    expect(reviewDraftStorageKey(second)).toBe(reviewDraftStorageKey(first));
  });

  it("isolates project, review type, session, source version, and immutable source revision", () => {
    const contexts = [
      contentContext(),
      contentContext({ projectId: "project-2" }),
      contentContext({ reviewSessionId: "content-session-2" }),
      contentContext({ sourceVersion: "content-v2" }),
      contentContext({ sourceRevision: 8 }),
      visualContext(),
    ];

    expect(new Set(contexts.map(reviewDraftStorageKey))).toHaveLength(contexts.length);
  });

  it("uses lineage for page remount identity without extending the fixed storage key", () => {
    const first = visualContext();
    const second = visualContext({
      lineage: { ...first.lineage, anchorSlideSetRef: "anchor-set-next" },
    });

    expect(reviewDraftStorageKey(second)).toBe(reviewDraftStorageKey(first));
    expect(reviewDraftPageIdentity(second)).not.toBe(reviewDraftPageIdentity(first));
  });

  it("round-trips typed content and visual envelopes", () => {
    const content = contentContext();
    const visual = visualContext();
    const contentEnvelope = createReviewDraftEnvelope(content, contentUi(), "2026-08-15T00:02:00Z");
    const visualEnvelope = createReviewDraftEnvelope(visual, visualUi(), "2026-08-15T00:03:00.000001+08:00");

    const contentStorage = memoryStorage();
    const visualStorage = memoryStorage();
    expect(saveReviewDraft(contentStorage.storage, content, contentEnvelope.ui, contentEnvelope.updated_at)).toBe(true);
    expect(saveReviewDraft(visualStorage.storage, visual, visualEnvelope.ui, visualEnvelope.updated_at)).toBe(true);

    expect(loadReviewDraft(contentStorage.storage, content)).toEqual(contentEnvelope);
    expect(loadReviewDraft(visualStorage.storage, visual)).toEqual(visualEnvelope);
  });

  it.each([
    ["target_type", (composer: NonNullable<VisualReviewDraftUi["contract_mark_composer"]>) => {
      composer.target_type = "contract-field";
    }],
    ["slide_id", (composer: NonNullable<VisualReviewDraftUi["contract_mark_composer"]>) => {
      composer.slide_id = "S02";
    }],
    ["deck_section_id", (composer: NonNullable<VisualReviewDraftUi["contract_mark_composer"]>) => {
      composer.deck_section_id = "deck-design-system";
    }],
    ["target_key", (composer: NonNullable<VisualReviewDraftUi["contract_mark_composer"]>) => {
      composer.target_key = "page_family";
    }],
    ["selected_text", (composer: NonNullable<VisualReviewDraftUi["contract_mark_composer"]>) => {
      composer.selected_text = "右侧事实";
    }],
    ["context_before", (composer: NonNullable<VisualReviewDraftUi["contract_mark_composer"]>) => {
      composer.context_before = "另一标题";
    }],
    ["context_after", (composer: NonNullable<VisualReviewDraftUi["contract_mark_composer"]>) => {
      composer.context_after = "另一因果链";
    }],
  ])("rejects an editing contract composer when %s differs from mark-1", (_field, mutate) => {
    const context = visualContext();
    const envelope = createReviewDraftEnvelope(
      context,
      visualTextRangeEditingUi(),
      "2026-08-15T00:03:00Z",
    );
    mutate(envelope.ui.contract_mark_composer!);

    expect(validateReviewDraftEnvelope(envelope, context)).toBeNull();
  });

  it("allows a new contract composer to target another valid field without editing lineage", () => {
    const context = visualContext();
    const ui = visualUi();
    ui.contract_mark_composer = {
      editing_mark_id: "",
      target_type: "contract-field",
      slide_id: "S02",
      deck_section_id: "",
      target_key: "composition_intent",
      selected_text: "",
      context_before: "",
      context_after: "",
      comment: "新建标记不绑定旧目标",
    };
    const envelope = createReviewDraftEnvelope(context, ui, "2026-08-15T00:03:00Z");

    expect(validateReviewDraftEnvelope(envelope, context)).not.toBeNull();
  });

  it("round-trips a Visual Brief mark and logical scroll through the closed draft context", () => {
    const context = visualContext();
    const ui = visualUi();
    ui.contract_mark_drafts[0] = {
      ...ui.contract_mark_drafts[0],
      slide_id: "",
      deck_section_id: "visual-brief",
      target_key: "decision_task",
      comment: "收紧决策任务",
    };
    ui.contract_mark_composer = null;
    ui.contract_logical_scroll = { object_id: "visual-brief", offset: 180 };
    const envelope = createReviewDraftEnvelope(context, ui, "2026-08-15T00:03:00Z");

    expect(validateReviewDraftEnvelope(envelope, context)).not.toBeNull();

    const forbidden = structuredClone(envelope);
    forbidden.ui.contract_mark_drafts[0].target_key = "design_proposition";
    expect(validateReviewDraftEnvelope(forbidden, context)).toBeNull();
  });

  it.each([
    ["extra envelope fact", (value: any) => { value.persistence_status = "saved"; }],
    ["identity mismatch", (value: any) => { value.source_version = "foreign-source"; }],
    ["lineage mismatch", (value: any) => { value.lineage.reading_blueprint_ref = "foreign-blueprint"; }],
    ["extra UI message", (value: any) => { value.ui.message = "saved"; }],
    ["duplicate page draft", (value: any) => { value.ui.page_drafts.push(structuredClone(value.ui.page_drafts[0])); }],
    ["unknown page membership", (value: any) => { value.ui.page_drafts[0].slide_id = "S99"; }],
    ["impossible timestamp", (value: any) => { value.updated_at = "2026-02-30T00:00:00Z"; }],
    ["unknown scroll object", (value: any) => { value.ui.logical_scroll.object_id = "S99"; }],
    ["negative scroll", (value: any) => { value.ui.logical_scroll.offset = -1; }],
  ])("rejects a content envelope with %s", (_label, mutate) => {
    const context = contentContext();
    const envelope: any = createReviewDraftEnvelope(context, contentUi(), "2026-08-15T00:02:00Z");
    mutate(envelope);

    expect(validateReviewDraftEnvelope(envelope, context)).toBeNull();
  });

  it.each([
    ["duplicate feedback ID", (value: any) => { value.ui.anchor_feedback_drafts.push(structuredClone(value.ui.anchor_feedback_drafts[0])); }],
    ["duplicate mark ID", (value: any) => { value.ui.contract_mark_drafts.push(structuredClone(value.ui.contract_mark_drafts[0])); }],
    ["unknown anchor membership", (value: any) => { value.ui.anchor_feedback_drafts[0].anchor_slide_id = "S99"; }],
    ["unknown contract target", (value: any) => { value.ui.contract_mark_drafts[0].target_key = "foreign-field"; }],
    ["invalid normalized region", (value: any) => { value.ui.anchor_feedback_drafts[0].normalized_region.width = 2; }],
    ["invalid draft timestamp", (value: any) => { value.ui.anchor_feedback_drafts[0].created_at = "2026-08-15 00:00:00"; }],
    ["unknown current object", (value: any) => { value.ui.current_anchor_slide_id = "S99"; }],
    ["anchor scroll using contract membership", (value: any) => { value.ui.anchor_logical_scroll.object_id = "S01"; }],
    ["contract scroll using anchor membership", (value: any) => { value.ui.contract_logical_scroll.object_id = "A01"; }],
    ["invalid anchor logical scroll", (value: any) => { value.ui.anchor_logical_scroll.offset = Number.POSITIVE_INFINITY; }],
    ["invalid contract logical scroll", (value: any) => { value.ui.contract_logical_scroll.offset = -1; }],
    ["transient annotation mode", (value: any) => { value.ui.anchor_feedback_composer.annotation_mode = true; }],
    ["saved batch leakage", (value: any) => { value.ui.anchor_feedback_batch = { persistence_status: "saved" }; }],
  ])("rejects a visual envelope with %s", (_label, mutate) => {
    const context = visualContext();
    const envelope: any = createReviewDraftEnvelope(context, visualUi(), "2026-08-15T00:02:00Z");
    mutate(envelope);

    expect(validateReviewDraftEnvelope(envelope, context)).toBeNull();
  });

  it.each([
    ["content fractional", "content", "logical_scroll", 40.5],
    ["visual anchor fractional", "visual", "anchor_logical_scroll", 40.5],
    ["visual contract fractional", "visual", "contract_logical_scroll", 40.5],
    ["content unsafe", "content", "logical_scroll", Number.MAX_SAFE_INTEGER + 1],
    ["visual anchor unsafe", "visual", "anchor_logical_scroll", Number.MAX_SAFE_INTEGER + 1],
    ["visual contract unsafe", "visual", "contract_logical_scroll", Number.MAX_SAFE_INTEGER + 1],
  ] as const)("rejects and cannot restore a %s logical scroll offset", (_label, reviewType, field, offset) => {
    const context = reviewType === "content" ? contentContext() : visualContext();
    const ui = reviewType === "content" ? contentUi() : visualUi();
    (ui as any)[field].offset = offset;
    const envelope = createReviewDraftEnvelope(context as any, ui as any, "2026-08-15T00:02:00Z");
    const key = reviewDraftStorageKey(context);
    const { storage } = memoryStorage({ [key]: JSON.stringify(envelope) });

    expect(validateReviewDraftEnvelope(envelope, context as any)).toBeNull();
    expect(context.reviewType === "content"
      ? loadReviewDraft(storage, context)
      : loadReviewDraft(storage, context)).toBeNull();
  });

  it("restores nonnegative safe-integer logical scroll offsets", () => {
    const context = visualContext();
    const ui = visualUi();
    ui.anchor_logical_scroll = { object_id: "A01", offset: 0 };
    ui.contract_logical_scroll = {
      object_id: "deck-design-system",
      offset: Number.MAX_SAFE_INTEGER,
    };
    const envelope = createReviewDraftEnvelope(context, ui, "2026-08-15T00:02:00Z");
    const key = reviewDraftStorageKey(context);
    const { storage } = memoryStorage({ [key]: JSON.stringify(envelope) });

    expect(loadReviewDraft(storage, context)?.ui).toEqual(ui);
  });

  it("rejects and cannot restore a nonempty anchor composer without a candidate region", () => {
    const context = visualContext();
    const ui = visualUi();
    ui.anchor_feedback_composer = {
      anchor_slide_id: "A01",
      candidate_region: null,
      editing_feedback_id: "",
      comment: "不可见但会锁住页面的输入",
    };
    const envelope = createReviewDraftEnvelope(context, ui, "2026-08-15T00:02:00Z");
    const key = reviewDraftStorageKey(context);
    const { storage } = memoryStorage({ [key]: JSON.stringify(envelope) });

    expect(validateReviewDraftEnvelope(envelope, context)).toBeNull();
    expect(loadReviewDraft(storage, context)).toBeNull();
  });

  it("keeps a null anchor composer legal and restores a normalized candidate composer", () => {
    const context = visualContext();
    const withoutComposer = visualUi();
    withoutComposer.anchor_feedback_composer = null;
    expect(validateReviewDraftEnvelope(
      createReviewDraftEnvelope(context, withoutComposer, "2026-08-15T00:02:00Z"),
      context,
    )?.ui.anchor_feedback_composer).toBeNull();

    const withComposer = visualUi();
    const envelope = createReviewDraftEnvelope(context, withComposer, "2026-08-15T00:02:00Z");
    const key = reviewDraftStorageKey(context);
    const { storage } = memoryStorage({ [key]: JSON.stringify(envelope) });
    expect(loadReviewDraft(storage, context)?.ui.anchor_feedback_composer).toEqual(
      withComposer.anchor_feedback_composer,
    );
  });

  it("rejects non-plain and accessor-backed envelopes without reading the accessor", () => {
    const context = contentContext();
    const envelope = createReviewDraftEnvelope(context, contentUi(), "2026-08-15T00:02:00Z");
    expect(validateReviewDraftEnvelope(Object.create(envelope), context)).toBeNull();

    let getterReads = 0;
    const accessor = structuredClone(envelope) as typeof envelope;
    Object.defineProperty(accessor, "updated_at", {
      configurable: true,
      enumerable: true,
      get() {
        getterReads += 1;
        return "2026-08-15T00:02:00Z";
      },
    });
    expect(validateReviewDraftEnvelope(accessor, context)).toBeNull();
    expect(getterReads).toBe(0);
  });

  it("rejects raw data over 256 KiB before JSON parsing", () => {
    const context = contentContext();
    const key = reviewDraftStorageKey(context);
    const { storage } = memoryStorage({ [key]: "x".repeat(REVIEW_DRAFT_MAX_RAW_BYTES + 1) });
    const parse = vi.spyOn(JSON, "parse");

    expect(loadReviewDraft(storage, context)).toBeNull();
    expect(parse).not.toHaveBeenCalled();
  });

  it("catches storage get, set, and remove failures", () => {
    const context = contentContext();
    const throwing: ReviewDraftStorage = {
      getItem: vi.fn(() => { throw new Error("get denied"); }),
      setItem: vi.fn(() => { throw new Error("set denied"); }),
      removeItem: vi.fn(() => { throw new Error("remove denied"); }),
    };

    expect(() => loadReviewDraft(throwing, context)).not.toThrow();
    expect(loadReviewDraft(throwing, context)).toBeNull();
    expect(() => saveReviewDraft(throwing, context, contentUi(), "2026-08-15T00:00:00Z")).not.toThrow();
    expect(saveReviewDraft(throwing, context, contentUi(), "2026-08-15T00:00:00Z")).toBe(false);
    expect(() => discardReviewDraft(throwing, context)).not.toThrow();
    expect(discardReviewDraft(throwing, context)).toBe(false);
  });

  it("clears one content page draft without changing the remaining page or navigation state", () => {
    const context = contentContext();
    const ui: ContentReviewDraftUi = {
      ...contentUi(),
      page_drafts: [
        { slide_id: "S01", decision: "modify", comment: "修改第一页" },
        { slide_id: "S02", decision: "evidence", comment: "补第二页证据" },
      ],
    };

    const next = applyReviewDraftUpdate(context, ui, {
      type: "clear-page-draft",
      slideId: "S01",
    });

    expect(next).toEqual({
      ...ui,
      page_drafts: [{ slide_id: "S02", decision: "evidence", comment: "补第二页证据" }],
    });
    expect(applyReviewDraftUpdate(context, ui, {
      type: "clear-page-draft",
      slideId: "S99",
    })).toBeNull();
  });

  it("clears every content page draft only for the completed content batch", () => {
    const context = contentContext();
    const ui: ContentReviewDraftUi = {
      ...contentUi(),
      page_drafts: [
        { slide_id: "S01", decision: "modify", comment: "修改第一页" },
        { slide_id: "S02", decision: "evidence", comment: "补第二页证据" },
      ],
    };

    expect(applyReviewDraftUpdate(context, ui, { type: "clear-content-batch" })).toEqual({
      ...ui,
      page_drafts: [],
    });
  });

  it("atomically validates and updates the current content slide with its logical scroll", () => {
    const context = contentContext();
    const ui = contentUi();

    expect(applyReviewDraftUpdate(context, ui, {
      type: "set-content-logical-position",
      slideId: "S02",
      offset: 41,
    })).toEqual({
      ...ui,
      current_slide_id: "S02",
      logical_scroll: { object_id: "S02", offset: 41 },
    });
    expect(applyReviewDraftUpdate(context, ui, {
      type: "set-content-logical-position",
      slideId: "S99",
      offset: 0,
    })).toBeNull();
    expect(applyReviewDraftUpdate(context, ui, {
      type: "set-content-logical-position",
      slideId: "S02",
      offset: -1,
    })).toBeNull();
  });

  it("clears only the visual anchor slice and preserves contract, view, current anchor, and both scrolls", () => {
    const context = visualContext();
    const ui = visualUi();

    const next = applyReviewDraftUpdate(context, ui, { type: "clear-anchor-slice" });

    expect(next).toEqual({
      ...ui,
      anchor_feedback_drafts: [],
      anchor_feedback_composer: null,
    });
    expect(next?.contract_mark_drafts).toEqual(ui.contract_mark_drafts);
    expect(next?.contract_mark_composer).toEqual(ui.contract_mark_composer);
    expect(next?.anchor_logical_scroll).toEqual(ui.anchor_logical_scroll);
    expect(next?.contract_logical_scroll).toEqual(ui.contract_logical_scroll);
  });

  it("clears only the visual contract slice and preserves anchor, view, current anchor, and both scrolls", () => {
    const context = visualContext();
    const ui = visualUi();

    const next = applyReviewDraftUpdate(context, ui, { type: "clear-contract-slice" });

    expect(next).toEqual({
      ...ui,
      contract_mark_drafts: [],
      contract_mark_composer: null,
    });
    expect(next?.anchor_feedback_drafts).toEqual(ui.anchor_feedback_drafts);
    expect(next?.anchor_feedback_composer).toEqual(ui.anchor_feedback_composer);
    expect(next?.anchor_logical_scroll).toEqual(ui.anchor_logical_scroll);
    expect(next?.contract_logical_scroll).toEqual(ui.contract_logical_scroll);
  });

  it("replaces one visual draft slice without allowing it to overwrite the other slice", () => {
    const context = visualContext();
    const ui = visualUi();
    const replacement = [{
      feedback_id: "feedback-2",
      anchor_slide_id: "A02",
      normalized_region: { x: 0.2, y: 0.2, width: 0.2, height: 0.2 },
      comment: "替换锚点草稿",
      created_at: "2026-08-15T00:04:00Z",
    }];

    const next = applyReviewDraftUpdate(context, ui, {
      type: "replace-anchor-slice",
      drafts: replacement,
      composer: null,
    });

    expect(next?.anchor_feedback_drafts).toEqual(replacement);
    expect(next?.anchor_feedback_composer).toBeNull();
    expect(next?.contract_mark_drafts).toEqual(ui.contract_mark_drafts);
    expect(next?.contract_mark_composer).toEqual(ui.contract_mark_composer);
    expect(next?.anchor_logical_scroll).toEqual(ui.anchor_logical_scroll);
    expect(next?.contract_logical_scroll).toEqual(ui.contract_logical_scroll);
  });

  it("derives visual membership and lineage without using mutable snapshot revision", () => {
    const data = {
      snapshotRevision: 200,
      review: {
        review_type: "visual-professional",
        project_id: "project-1",
        review_session_id: "visual-session-1",
        source_version: "visual-v1",
        revision: 8,
        visual_contract_ref: "visual-contract-1",
        anchor_slide_set_ref: "anchor-set-1",
        deck_design_system_ref: "deck-system-1",
        anchors: [{ slide_id: "S01" }],
        slide_visual_contracts: [{ slide_id: "S01", composition_intent: "intent" }],
        deck_design_system: { typography_tokens: {} },
      },
    } as unknown as VisualReviewPageViewModel;

    expect(createReviewDraftContext(data)).toEqual(expect.objectContaining({
      reviewType: "visual",
      sourceRevision: 8,
      anchorSlideIds: ["S01"],
      visualContractFields: { S01: [...REVIEWABLE_SLIDE_FIELD_KEYS] },
      visualBriefFields: [...VISUAL_BRIEF_FIELD_ORDER],
      deckDesignSystemFields: [...DESIGN_SYSTEM_FIELD_ORDER],
    }));
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";

import { createBrowserReviewClient } from "./lib/browser-review-client";

const READING_BLUEPRINT_REF = "artifact://reading-deck-blueprint/" + "1".repeat(64);
const CONTENT_ACCEPTANCE_REF = "artifact://content-acceptance/" + "2".repeat(64);
const VISUAL_CONTRACT_REF = "artifact://visual-contract/" + "a".repeat(64);
const DECK_DESIGN_SYSTEM_REF = "artifact://deck-design-system/" + "b".repeat(64);
const ANCHOR_SLIDE_SET_REF = "artifact://anchor-slide-set/" + "c".repeat(64);
const VISUAL_MARK_SET_REF = "artifact://visual-contract-review-mark-set/" + "d".repeat(64);
const VISUAL_ANCHOR_BATCH_REF = "artifact://visual-anchor-feedback-batch/" + "e".repeat(64);
const NATIVE_PPTX_REF = "artifact://native-pptx/" + "6".repeat(64);
const EDITABILITY_EVIDENCE_REF = "artifact://editability-evidence/" + "7".repeat(64);
const PREFLIGHT_RENDER_REF = "artifact://preflight-render/" + "8".repeat(64);

function reviewSession(
  reviewType: "content-full-deck" | "visual-professional",
  sourceVersion: string,
  reviewSessionId: string,
  targetArtifactRef: string,
) {
  return {
    review_session_id: reviewSessionId,
    review_type: reviewType,
    project_id: "p1",
    target_artifact_ref: targetArtifactRef,
    source_version: sourceVersion,
    revision: 7,
    status: "ready",
    open_policy: "foreground-if-waiting",
    host_open_status: "not-requested",
    persistence_status: "saved",
    host_notification_status: "not-requested",
    ai_receipt_status: "pending",
    created_at: "2026-08-15T00:00:00Z",
    last_opened_at: null,
    submitted_at: null,
  };
}

function contentReviewProjection(materialAssetRef = "") {
  const sourceVersion = "content-v1";
  const readingBlueprintRef = READING_BLUEPRINT_REF;
  return {
    project_id: "p1",
    review_type: "content-full-deck",
    review_session_id: "content-session-1",
    review_session: reviewSession("content-full-deck", sourceVersion, "content-session-1", readingBlueprintRef),
    source_version: sourceVersion,
    revision: 7,
    authoritative_revision: 7,
    reading_blueprint_ref: readingBlueprintRef,
    material_mode: "proposal-led",
    section_flow: materialAssetRef ? ["section-1"] : [],
    slides: materialAssetRef ? [{
      slide_id: "S01",
      order: 1,
      section_id: "section-1",
      page_task: "建立问题共识",
      reading_question: "为何现在行动",
      neutral_title: "经营协同仍有断点",
      customerJudgment: "客户确认现状边界后，再判断是否进入联合方案验证。",
      visible_copy_blocks: [],
      material_views: [{
        material_view_id: "material-view-1",
        asset_ref: materialAssetRef,
      }],
    }] : [],
    decisions: [],
    progress: { completed: 0, total: materialAssetRef ? 1 : 0, remaining: materialAssetRef ? 1 : 0, unsaved: 0 },
    batch: null,
    revision_plan: null,
    content_acceptance_ref: CONTENT_ACCEPTANCE_REF,
  };
}

function visualSlideContract(overrides: Record<string, unknown> = {}) {
  return {
    slide_id: "S01",
    order: 1,
    page_task: "问题诊断",
    reading_question: "为何现在行动",
    neutral_title: "经营协同仍有断点",
    visible_copy_blocks: [],
    identity_labels: ["方案建议"],
    evidence_bindings: [],
    analysis_or_proposal_blocks: [],
    solution_mapping_refs: [],
    previous_relation: "",
    next_relation: "进入一期方案",
    speaker_notes: "",
    reading_quality: {
      independently_readable: true,
      information_density: "medium",
      review_note: "",
    },
    material_mode: "proposal-led",
    page_family: "问题诊断页",
    information_hierarchy: "标题—事实—建议",
    composition_intent: "左侧事实，右侧因果链",
    image_selection_and_crop: "无图时保持原生结构",
    typography_application: "标题与正文层级分明",
    color_application: "中性底色配单一强调色",
    diagram_chart_table_treatment: "因果关系使用原生形状",
    native_bitmap_routing: "原生优先",
    editability_requirements: "所有正文与图形可编辑",
    regions: ["标题区", "正文区"],
    object_relationships: ["事实支持建议"],
    reading_order: ["标题", "事实", "建议"],
    fallbacks: ["缺图时保持原生结构"],
    acceptance_criteria: [{
      criterion_id: "criterion-1",
      level: "must-follow",
      expected_outcome: "阅读顺序清晰且原生可编辑",
    }],
    allowed_exceptions: [],
    future_extension: { renderer_hint: "native-shapes" },
    ...overrides,
  };
}

function visualReviewProjection(
  contractReviewMarks: ReturnType<typeof initialVisualMarkSet> | null = null,
  anchorFeedbackBatch: ReturnType<typeof initialVisualAnchorBatch> | null = null,
) {
  const sourceVersion = "visual-v1";
  const visualContractRef = VISUAL_CONTRACT_REF;
  const anchors = ["S01", "S02", "S03"].map((slideId) => ({
    slide_id: slideId,
    current_asset_ref: `review-assets/anchors/${slideId}-current.png`,
    previous_asset_ref: "",
  }));
  return {
    review_type: "visual-professional",
    review_session_id: "visual-session-1",
    project_id: "p1",
    project_name: "测试项目",
    review_session: reviewSession("visual-professional", sourceVersion, "visual-session-1", visualContractRef),
    source_version: sourceVersion,
    revision: 7,
    authoritative_revision: 7,
    visual_contract_ref: visualContractRef,
    deck_design_system_ref: DECK_DESIGN_SYSTEM_REF,
    deck_design_system: {
      typography_tokens: { title_scale: "32pt" },
    },
    anchor_slide_set_ref: ANCHOR_SLIDE_SET_REF,
    anchors,
    anchor_identity: {
      visual_contract_set_ref: "artifact://visual-contract-set/" + "b".repeat(64),
      slide_ids: anchors.map((anchor) => anchor.slide_id),
      selection_reason: "覆盖问题诊断、证据和方案页面家族",
      native_first_frozen: true,
      native_first_pptx_ref: NATIVE_PPTX_REF,
      pptx_sha256: "a".repeat(64),
      editability_evidence_refs: [EDITABILITY_EVIDENCE_REF],
      preflight_render_refs: [PREFLIGHT_RENDER_REF],
      render_assets: anchors.map((anchor) => ({ ...anchor })),
    },
    slide_visual_contracts: [visualSlideContract()],
    anchor_feedback_batch_ref: anchorFeedbackBatch ? VISUAL_ANCHOR_BATCH_REF : null,
    anchor_feedback_batch: anchorFeedbackBatch,
    contract_review_marks_ref: contractReviewMarks ? VISUAL_MARK_SET_REF : null,
    contract_review_marks: contractReviewMarks,
    gate_status: { G1: "passed", G2: "passed", G3: "user-reviewable" },
    host_submission_capability: "unavailable",
    ai_receipt_capability: "unavailable",
  };
}

function initialVisualMarkSet() {
  return {
    mark_set_id: "visual-marks-initial",
    project_id: "p1",
    review_session_id: "visual-session-1",
    visual_contract_ref: VISUAL_CONTRACT_REF,
    source_version: "visual-v1",
    revision: 7,
    marks: [visualMark(6)],
    persistence_status: "saved" as const,
    host_notification_status: "unavailable" as const,
    ai_receipt_status: "unverified" as const,
    saved_at: "2026-08-15T00:01:00Z",
  };
}

function initialVisualAnchorBatch({
  createdAt = "2026-08-15T00:00:00Z",
  submittedAt = "2026-08-15T00:01:00Z",
  hostNotificationStatus = "unavailable",
  aiReceiptStatus = "unverified",
}: {
  createdAt?: string;
  submittedAt?: string;
  hostNotificationStatus?: "unavailable" | "sent";
  aiReceiptStatus?: "unverified" | "received";
} = {}) {
  return {
    ...visualBatch([{ ...visualFeedback(7), created_at: createdAt }]),
    revision: 7,
    host_notification_status: hostNotificationStatus,
    ai_receipt_status: aiReceiptStatus,
    submitted_at: submittedAt,
  };
}

function reviewEnvelope(review: ReturnType<typeof contentReviewProjection> | ReturnType<typeof visualReviewProjection>, expectedRevision = 7) {
  const scopedReview = { ...review, authoritative_revision: expectedRevision };
  return {
    ok: true,
    projectRoot: "/managed/project",
    reviewType: scopedReview.review_type,
    sourceVersion: scopedReview.source_version,
    expectedRevision,
    bridgeSessionId: "bridge-session-1",
    review: scopedReview,
  };
}

function visualFeedback(revision = 8) {
  return {
    feedback_id: "f1",
    anchor_slide_id: "S01",
    anchor_artifact_ref: ANCHOR_SLIDE_SET_REF,
    normalized_region: { x: 0.1, y: 0.1, width: 0.3, height: 0.2 },
    comment: "调整层级",
    order: 1,
    visual_source_version: "visual-v1",
    revision,
    created_at: "2026-08-15T00:00:00Z",
    created_by: "user",
  };
}

function visualBatch(items = [visualFeedback()]) {
  return {
    batch_id: "anchor-batch-1",
    project_id: "p1",
    review_session_id: "visual-session-1",
    visual_contract_ref: VISUAL_CONTRACT_REF,
    deck_design_system_ref: DECK_DESIGN_SYSTEM_REF,
    anchor_slide_set_ref: ANCHOR_SLIDE_SET_REF,
    items,
    source_version: "visual-v1",
    revision: 8,
    persistence_status: "saved",
    host_notification_status: "not-requested",
    ai_receipt_status: "pending",
    immutable_after_submit: true,
    submitted_at: "2026-08-15T00:01:00Z",
    submitted_by: "user",
  };
}

function visualMark(revision = 8) {
  return {
    mark_id: "m1",
    target_type: "contract-field" as const,
    slide_id: "",
    deck_section_id: "deck-design-system",
    target_key: "typography_tokens",
    selected_text: "",
    context_before: "",
    context_after: "",
    comment: "层级需要更清晰",
    visual_contract_ref: VISUAL_CONTRACT_REF,
    source_version: "visual-v1",
    revision,
    created_at: "2026-08-15T00:00:00Z",
    created_by: "user",
  };
}

function visualMarkResponse(marks = [visualMark()], commandRevision = 8) {
  return {
    ok: true,
    snapshotRevision: commandRevision + 1,
    markSetRef: VISUAL_MARK_SET_REF,
    markSet: {
      mark_set_id: "visual-marks-1",
      project_id: "p1",
      review_session_id: "visual-session-1",
      visual_contract_ref: VISUAL_CONTRACT_REF,
      source_version: "visual-v1",
      revision: commandRevision,
      marks,
      persistence_status: "saved" as const,
      host_notification_status: "not-requested" as const,
      ai_receipt_status: "pending" as const,
      saved_at: "2026-08-15T00:01:00Z",
    },
    hostNotificationStatus: "unavailable" as const,
    aiReceiptStatus: "unverified" as const,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("Browser Review loopback client", () => {
  it("bounds a never-settling review projection with one connection abort", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    let abortCount = 0;
    let connectionSignal: AbortSignal | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      connectionSignal = init?.signal as AbortSignal;
      return new Promise<Response>((_resolve, reject) => {
        connectionSignal?.addEventListener("abort", () => {
          abortCount += 1;
          reject(new DOMException("aborted", "AbortError"));
        });
      });
    });
    const client = createBrowserReviewClient({ connectionTimeoutMs: 20 } as never);

    const result = await Promise.race([
      client.connect().then(() => null, (error: unknown) => error),
      new Promise((resolve) => setTimeout(() => resolve("still-loading"), 100)),
    ]);

    expect(result).toMatchObject({ code: "REVIEW_CONNECTION_TIMEOUT" });
    expect(connectionSignal?.aborted).toBe(true);
    expect(abortCount).toBe(1);
  });

  it("uses one end-to-end deadline and AbortSignal across review and host-open", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const signals: AbortSignal[] = [];
    let hostOpenAbortCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const signal = init?.signal as AbortSignal;
      signals.push(signal);
      if (input === "/api/review") {
        return new Promise<Response>((resolve) => setTimeout(() => resolve(
          new Response(JSON.stringify(reviewEnvelope(contentReviewProjection())), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ), 12));
      }
      return new Promise<Response>((_resolve, reject) => {
        signal.addEventListener("abort", () => {
          hostOpenAbortCount += 1;
          reject(new DOMException("aborted", "AbortError"));
        });
      });
    });
    const client = createBrowserReviewClient({ connectionTimeoutMs: 20 } as never);

    const result = await Promise.race([
      client.connect().then(() => null, (error: unknown) => error),
      new Promise((resolve) => setTimeout(() => resolve("still-loading"), 100)),
    ]);

    expect(result).toMatchObject({ code: "REVIEW_CONNECTION_TIMEOUT" });
    expect(signals).toHaveLength(2);
    expect(signals[0]).toBe(signals[1]);
    expect(signals[0].aborted).toBe(true);
    expect(hostOpenAbortCount).toBe(1);
  });

  it("supersedes an older connection generation and ignores its late projection", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const firstProjection = deferred<Response>();
    let fetchCount = 0;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      fetchCount += 1;
      if (fetchCount === 1) return firstProjection.promise;
      if (fetchCount === 2) {
        return Promise.resolve(new Response(JSON.stringify(
          reviewEnvelope(contentReviewProjection(), 9),
        ), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      return Promise.resolve(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: fetchCount === 3 ? 10 : 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    });
    const client = createBrowserReviewClient({ connectionTimeoutMs: 100 } as never);
    const firstData = vi.fn();
    const secondData = vi.fn();
    const first = client.connect(firstData).then(() => null, (error: unknown) => error);
    await Promise.resolve();
    window.history.replaceState(null, "", "/#token=short-lived-token");

    await client.connect(secondData);
    expect(secondData).toHaveBeenCalledOnce();
    expect(secondData.mock.calls[0][0].snapshotRevision).toBe(10);
    const firstResult = await Promise.race([
      first,
      new Promise((resolve) => setTimeout(() => resolve("still-loading"), 50)),
    ]);
    expect(firstResult).toMatchObject({ code: "REVIEW_CONNECTION_SUPERSEDED" });

    firstProjection.resolve(new Response(JSON.stringify(
      reviewEnvelope(contentReviewProjection()),
    ), { status: 200, headers: { "Content-Type": "application/json" } }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(firstData).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(secondData).toHaveBeenCalledOnce();
  });

  it("removes the fragment token and reads the scoped review with Bearer", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(
        JSON.stringify(reviewEnvelope(contentReviewProjection())),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    const received = vi.fn();

    await client.connect(received);

    expect(window.location.hash).toBe("");
    expect(fetchMock).toHaveBeenCalledWith("/api/review", {
      headers: { authorization: "Bearer short-lived-token" },
      signal: expect.any(AbortSignal),
    });
    expect(received).toHaveBeenCalledWith(
      expect.objectContaining({
        surface: "review",
        selectedProjectRoot: "/managed/project",
        snapshotRevision: 8,
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/host-open", {
      method: "POST",
      headers: {
        authorization: "Bearer short-lived-token",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        expectedRevision: 7,
        bridgeSessionId: "bridge-session-1",
      }),
      signal: expect.any(AbortSignal),
    });
  });

  it.each([
    ["false success fact", (payload: any) => { payload.ok = false; }],
    ["non-object projection", (payload: any) => { payload.review = "visual"; }],
    ["missing projection field", (payload: any) => { Reflect.deleteProperty(payload.review, "project_id"); }],
    ["open projection field", (payload: any) => { payload.review.unexpected = true; }],
    ["spoofed initial persistence fact", (payload: any) => { payload.review.contract_review_marks.persistence_status = "pending"; }],
    ["spoofed initial host fact", (payload: any) => { payload.review.contract_review_marks.host_notification_status = "sent"; }],
    ["spoofed initial AI fact", (payload: any) => { payload.review.contract_review_marks.ai_receipt_status = "received"; }],
    ["spoofed initial anchor host fact", (payload: any) => { payload.review.anchor_feedback_batch.host_notification_status = "sent"; }],
    ["spoofed initial anchor AI fact", (payload: any) => { payload.review.anchor_feedback_batch.ai_receipt_status = "received"; }],
    ["opened session without a host-open receipt ref", (payload: any) => {
      Object.assign(payload.review.review_session, {
        status: "opened",
        host_open_status: "opened",
        last_opened_at: "2026-08-15T00:00:01Z",
      });
    }],
    ["sent session without a host-notification receipt ref", (payload: any) => {
      payload.review.review_session.host_notification_status = "sent";
      payload.review.contract_review_marks.host_notification_status = "sent";
      payload.review.anchor_feedback_batch.host_notification_status = "sent";
    }],
    ["received session without an AI receipt ref", (payload: any) => {
      payload.review.review_session.ai_receipt_status = "received";
      payload.review.contract_review_marks.ai_receipt_status = "received";
      payload.review.anchor_feedback_batch.ai_receipt_status = "received";
    }],
    ["host-open receipt with a non-artifact URI", (payload: any) => {
      Object.assign(payload.review.review_session, {
        status: "opened",
        host_open_status: "opened",
        last_opened_at: "2026-08-15T00:00:01Z",
        host_open_receipt_ref: `https://receipts.invalid/${"a".repeat(64)}`,
      });
    }],
    ["host-notification receipt with the wrong artifact kind", (payload: any) => {
      Object.assign(payload.review.review_session, {
        host_notification_status: "sent",
        host_notification_receipt_ref: `artifact://review-ai-receipt/${"b".repeat(64)}`,
      });
      payload.review.contract_review_marks.host_notification_status = "sent";
      payload.review.anchor_feedback_batch.host_notification_status = "sent";
    }],
    ["AI receipt with a malformed artifact digest", (payload: any) => {
      Object.assign(payload.review.review_session, {
        ai_receipt_status: "received",
        ai_receipt_ref: `artifact://review-ai-receipt/${"g".repeat(64)}`,
      });
      payload.review.contract_review_marks.ai_receipt_status = "received";
      payload.review.anchor_feedback_batch.ai_receipt_status = "received";
    }],
    ["host receipt map with the wrong saved artifact kind", (payload: any) => {
      Object.assign(payload.review.review_session, {
        host_notification_status: "sent",
        host_notification_receipt_ref: `artifact://review-host-notification-receipt/${"b".repeat(64)}`,
        host_notification_receipts: {
          [payload.review.visual_contract_ref]: `artifact://review-host-notification-receipt/${"b".repeat(64)}`,
        },
      });
    }],
    ["host receipt map with the wrong receipt artifact kind", (payload: any) => {
      Object.assign(payload.review.review_session, {
        host_notification_status: "sent",
        host_notification_receipt_ref: `artifact://review-host-notification-receipt/${"b".repeat(64)}`,
        host_notification_receipts: {
          [payload.review.anchor_feedback_batch_ref]: `artifact://review-ai-receipt/${"c".repeat(64)}`,
        },
      });
    }],
    ["AI receipt map with a non-scalar malicious value", (payload: any) => {
      Object.assign(payload.review.review_session, {
        ai_receipt_status: "received",
        ai_receipt_ref: `artifact://review-ai-receipt/${"c".repeat(64)}`,
        ai_receipts: {
          [payload.review.contract_review_marks_ref]: {
            receipt_ref: `artifact://review-ai-receipt/${"c".repeat(64)}`,
          },
        },
      });
    }],
    ["impossible ReviewSession date", (payload: any) => {
      payload.review.review_session.created_at = "2026-02-30T00:00:00Z";
    }],
    ["anchor item created one microsecond after submission", (payload: any) => {
      payload.review.anchor_feedback_batch.items[0].created_at = "2026-08-15T00:01:00.000001Z";
      payload.review.anchor_feedback_batch.submitted_at = "2026-08-15T00:01:00.000000Z";
    }],
    ["empty slide visual contracts", (payload: any) => {
      payload.review.slide_visual_contracts = [];
    }],
    ["duplicate slide visual contract identity", (payload: any) => {
      payload.review.slide_visual_contracts.push(visualSlideContract({ order: 2 }));
    }],
    ["incomplete slide visual contract", (payload: any) => {
      payload.review.slide_visual_contracts = [{ slide_id: "S01" }];
    }],
  ])("rejects a review GET with %s before host-open, data installation, callback, or heartbeat", async (_label, mutate) => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const payload: any = structuredClone(reviewEnvelope(
      visualReviewProjection(initialVisualMarkSet(), initialVisualAnchorBatch()),
    ));
    mutate(payload);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const heartbeat = vi.spyOn(window, "setInterval");
    const onData = vi.fn();
    const client = createBrowserReviewClient();

    const failure = await client.connect(onData).then(
      () => null,
      (error: unknown) => error,
    );

    expect(failure).toMatchObject({ code: "REVIEW_CONNECTION_INVALID" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/host-open")).toHaveLength(0);
    expect(onData).not.toHaveBeenCalled();
    expect(heartbeat).not.toHaveBeenCalled();
    await expect(client.callTool("read_ai_ppt_project_asset", {
      projectRoot: "/managed/project",
      assetRef: "review-assets/anchors/S01-current.png",
    })).rejects.toThrow("unavailable");
  });

  it("accepts advanced receipt states only with exact receipt artifact kinds", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const projection: any = visualReviewProjection(initialVisualMarkSet(), initialVisualAnchorBatch());
    Object.assign(projection.review_session, {
      status: "opened",
      host_open_status: "opened",
      last_opened_at: "2026-08-15T00:00:01Z",
      host_notification_status: "sent",
      ai_receipt_status: "received",
      host_open_receipt_ref: `artifact://review-host-open-receipt/${"a".repeat(64)}`,
      host_notification_receipt_ref: `artifact://review-host-notification-receipt/${"b".repeat(64)}`,
      ai_receipt_ref: `artifact://review-ai-receipt/${"c".repeat(64)}`,
      host_notification_receipts: {
        [VISUAL_ANCHOR_BATCH_REF]: `artifact://review-host-notification-receipt/${"b".repeat(64)}`,
        [VISUAL_MARK_SET_REF]: `artifact://review-host-notification-receipt/${"b".repeat(64)}`,
      },
      ai_receipts: {
        [VISUAL_ANCHOR_BATCH_REF]: `artifact://review-ai-receipt/${"c".repeat(64)}`,
        [VISUAL_MARK_SET_REF]: `artifact://review-ai-receipt/${"c".repeat(64)}`,
      },
    });
    projection.contract_review_marks.host_notification_status = "sent";
    projection.contract_review_marks.ai_receipt_status = "received";
    projection.anchor_feedback_batch.host_notification_status = "sent";
    projection.anchor_feedback_batch.ai_receipt_status = "received";
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(projection)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const onData = vi.fn();

    await createBrowserReviewClient().connect(onData);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(onData).toHaveBeenCalledOnce();
  });

  it("keeps visual receipt facts bound to each saved artifact", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const projection: any = visualReviewProjection(initialVisualMarkSet(), initialVisualAnchorBatch({
      hostNotificationStatus: "sent",
      aiReceiptStatus: "received",
    }));
    Object.assign(projection.review_session, {
      status: "opened",
      host_open_status: "opened",
      last_opened_at: "2026-08-15T00:00:01Z",
      host_notification_status: "sent",
      ai_receipt_status: "received",
      host_open_receipt_ref: `artifact://review-host-open-receipt/${"a".repeat(64)}`,
      host_notification_receipt_ref: `artifact://review-host-notification-receipt/${"b".repeat(64)}`,
      ai_receipt_ref: `artifact://review-ai-receipt/${"c".repeat(64)}`,
      host_notification_receipts: {
        [VISUAL_ANCHOR_BATCH_REF]: `artifact://review-host-notification-receipt/${"b".repeat(64)}`,
      },
      ai_receipts: {
        [VISUAL_ANCHOR_BATCH_REF]: `artifact://review-ai-receipt/${"c".repeat(64)}`,
      },
    });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(projection)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const onData = vi.fn();

    await createBrowserReviewClient().connect(onData);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const installed = onData.mock.calls[0][0];
    expect(installed.review.anchor_feedback_batch).toMatchObject({
      host_notification_status: "sent",
      ai_receipt_status: "received",
    });
    expect(installed.review.contract_review_marks).toMatchObject({
      host_notification_status: "unavailable",
      ai_receipt_status: "unverified",
    });
  });

  it.each([
    ["false success fact", { ok: false, hostOpenStatus: "opened", snapshotRevision: 8 }],
    ["wrong status", { ok: true, hostOpenStatus: "failed", snapshotRevision: 8 }],
    ["missing field", { ok: true, hostOpenStatus: "opened" }],
    ["open envelope", { ok: true, hostOpenStatus: "opened", snapshotRevision: 8, unexpected: true }],
    ["skipped successor revision", { ok: true, hostOpenStatus: "opened", snapshotRevision: 9 }],
  ])("rejects a host-open response with %s before data installation, callback, or heartbeat", async (_label, hostOpenPayload) => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(
        reviewEnvelope(visualReviewProjection(initialVisualMarkSet())),
      ), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(hostOpenPayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }));
    const heartbeat = vi.spyOn(window, "setInterval");
    const onData = vi.fn();
    const client = createBrowserReviewClient();

    const failure = await client.connect(onData).then(
      () => null,
      (error: unknown) => error,
    );

    expect(failure).toMatchObject({ code: "REVIEW_CONNECTION_INVALID" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(onData).not.toHaveBeenCalled();
    expect(heartbeat).not.toHaveBeenCalled();
  });

  it("accepts an initial anchor item at the same instant expressed with an offset", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const batch = initialVisualAnchorBatch({
      createdAt: "2026-08-16T14:31:00.000999+14:30",
      submittedAt: "2026-08-16T00:01:00.000999Z",
    });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(
        visualReviewProjection(initialVisualMarkSet(), batch),
      )), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const received = vi.fn();

    await createBrowserReviewClient().connect(received);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(received).toHaveBeenCalledOnce();
    expect(received).toHaveBeenCalledWith(expect.objectContaining({
      review: expect.objectContaining({
        slide_visual_contracts: [expect.objectContaining({
          future_extension: { renderer_hint: "native-shapes" },
        })],
      }),
    }));
  });

  it("saves visual-contract marks through the scoped Browser API", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const automaticHostReceipt = {
      ...visualMarkResponse(),
      snapshotRevision: 10,
      hostNotificationStatus: "sent" as const,
      aiReceiptStatus: "unverified" as const,
    };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify(reviewEnvelope(visualReviewProjection())),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(automaticHostReceipt), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const client = createBrowserReviewClient();
    await client.connect();

    const result = await client.callTool(
      "save_visual_contract_review_marks",
      {
        projectRoot: "/managed/project",
        expectedRevision: 8,
        sourceVersion: "visual-v1",
        reviewSessionId: "visual-session-1",
        marks: [visualMark()],
      },
    );

    expect(result.snapshot.revision).toBe(10);
    expect(result.mark_set_ref).toBe(VISUAL_MARK_SET_REF);
    expect(result.mark_set.host_notification_status).toBe("sent");
    expect(result.mark_set.ai_receipt_status).toBe("unverified");
    expect(fetchMock.mock.calls[2][0]).toBe("/api/visual/marks");
  });

  it("fails closed when a direct visual-contract save claims an AI receipt", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const spoofedAiReceipt = {
      ...visualMarkResponse(),
      snapshotRevision: 10,
      hostNotificationStatus: "sent" as const,
      aiReceiptStatus: "received" as const,
    };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(visualReviewProjection())), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(spoofedAiReceipt), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }));
    const client = createBrowserReviewClient();
    await client.connect();

    await expect(client.callTool("save_visual_contract_review_marks", {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      sourceVersion: "visual-v1",
      reviewSessionId: "visual-session-1",
      marks: [visualMark()],
    })).rejects.toMatchObject({ code: "VISUAL_CONTRACT_MARK_RESULT_UNCLOSED" });
  });

  it("keeps host notification retry and AI receipt verification as separate artifact-bound Browser recovery actions", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(
        visualReviewProjection(initialVisualMarkSet(), initialVisualAnchorBatch()),
      )), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        savedArtifactRef: VISUAL_ANCHOR_BATCH_REF,
        hostNotificationStatus: "sent",
        snapshotRevision: 9,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        savedArtifactRef: VISUAL_MARK_SET_REF,
        aiReceiptStatus: "received",
        snapshotRevision: 10,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();
    const controller = new AbortController();

    const host = await client.retryVisualHostNotification({
      projectRoot: "/managed/project",
      expectedRevision: 8,
      reviewSessionId: "visual-session-1",
      sourceVersion: "visual-v1",
      savedArtifactRef: VISUAL_ANCHOR_BATCH_REF,
    }, { signal: controller.signal });
    expect(host).toEqual({
      savedArtifactRef: VISUAL_ANCHOR_BATCH_REF,
      hostNotificationStatus: "sent",
      snapshotRevision: 9,
    });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/host-notification", {
      method: "POST",
      headers: { authorization: "Bearer short-lived-token", "content-type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        expectedRevision: 8,
        reviewSessionId: "visual-session-1",
        sourceVersion: "visual-v1",
        savedArtifactRef: VISUAL_ANCHOR_BATCH_REF,
      }),
    });

    const ai = await client.verifyVisualAiReceipt({
      projectRoot: "/managed/project",
      expectedRevision: 9,
      reviewSessionId: "visual-session-1",
      sourceVersion: "visual-v1",
      savedArtifactRef: VISUAL_MARK_SET_REF,
      receiptIdentity: VISUAL_MARK_SET_REF,
    });
    expect(ai).toEqual({
      savedArtifactRef: VISUAL_MARK_SET_REF,
      aiReceiptStatus: "received",
      snapshotRevision: 10,
    });
    expect(fetchMock.mock.calls[3][0]).toBe("/api/ai-receipt");
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toEqual({
      expectedRevision: 9,
      reviewSessionId: "visual-session-1",
      sourceVersion: "visual-v1",
      savedArtifactRef: VISUAL_MARK_SET_REF,
      receiptIdentity: VISUAL_MARK_SET_REF,
    });
  });

  it("fails closed on a host notification recovery response that mixes in an AI fact", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(
        visualReviewProjection(null, initialVisualAnchorBatch()),
      )), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        savedArtifactRef: VISUAL_ANCHOR_BATCH_REF,
        hostNotificationStatus: "sent",
        aiReceiptStatus: "received",
        snapshotRevision: 9,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();

    await expect(client.retryVisualHostNotification({
      projectRoot: "/managed/project",
      expectedRevision: 8,
      reviewSessionId: "visual-session-1",
      sourceVersion: "visual-v1",
      savedArtifactRef: VISUAL_ANCHOR_BATCH_REF,
    })).rejects.toMatchObject({ code: "VISUAL_RECOVERY_RESULT_UNCLOSED" });
  });

  it("forwards a visual-write AbortSignal to the loopback fetch and releases the pending request", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(visualReviewProjection())), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockImplementationOnce((_url, init) => new Promise((_resolve, reject) => {
        const signal = init?.signal;
        signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
      }));
    const client = createBrowserReviewClient();
    await client.connect();
    const controller = new AbortController();

    const pending = client.callTool("save_visual_contract_review_marks", {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      sourceVersion: "visual-v1",
      reviewSessionId: "visual-session-1",
      marks: [visualMark()],
    }, { signal: controller.signal });
    await Promise.resolve();

    expect(fetchMock.mock.calls[2][1]).toEqual(expect.objectContaining({ signal: controller.signal }));
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  it("rejects visual-contract mark scope and revision mismatches before calling the Bridge", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(visualReviewProjection())), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();
    const base = {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      sourceVersion: "visual-v1",
      reviewSessionId: "visual-session-1",
      marks: [visualMark()],
    };

    await expect(client.callTool("save_visual_contract_review_marks", { ...base, projectRoot: "/foreign/project" }))
      .rejects.toThrow("outside the connected review scope");
    await expect(client.callTool("save_visual_contract_review_marks", { ...base, reviewSessionId: "foreign-session" }))
      .rejects.toThrow("outside the connected review scope");
    await expect(client.callTool("save_visual_contract_review_marks", { ...base, sourceVersion: "visual-v2" }))
      .rejects.toThrow("outside the connected review scope");
    await expect(client.callTool("save_visual_contract_review_marks", { ...base, expectedRevision: 7 }))
      .rejects.toThrow(/does not match current revision 8/);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("fails a visual connection closed on an unsafe host-open revision before any marks POST", async () => {
    const unsafeRevision = Number.MAX_SAFE_INTEGER + 1;
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(visualReviewProjection())), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: unsafeRevision,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(
        visualMarkResponse([visualMark(unsafeRevision)], unsafeRevision),
      ), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();

    const connectFailure = await client.connect().then(
      () => null,
      (error: unknown) => error,
    );
    const markFailure = await client.callTool("save_visual_contract_review_marks", {
      projectRoot: "/managed/project",
      expectedRevision: unsafeRevision,
      sourceVersion: "visual-v1",
      reviewSessionId: "visual-session-1",
      marks: [visualMark(unsafeRevision)],
    }).then(
      () => null,
      (error: unknown) => error,
    );

    expect(connectFailure).toMatchObject({ code: "REVIEW_CONNECTION_INVALID" });
    expect(markFailure).toBeInstanceOf(Error);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/visual/marks")).toHaveLength(0);
  });

  it("fails before host-open when the scoped review revision has no safe successor", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(reviewEnvelope(visualReviewProjection(), Number.MAX_SAFE_INTEGER)), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const client = createBrowserReviewClient();

    const failure = await client.connect().then(
      () => null,
      (error: unknown) => error,
    );

    expect(failure).toMatchObject({ code: "REVIEW_REVISION_INVALID" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/host-open")).toHaveLength(0);
  });

  it("fails closed when host-open reaches the terminal safe revision", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(visualReviewProjection(), Number.MAX_SAFE_INTEGER - 1)), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: Number.MAX_SAFE_INTEGER,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();

    const failure = await client.connect().then(
      () => null,
      (error: unknown) => error,
    );

    expect(failure).toMatchObject({ code: "REVIEW_REVISION_INVALID" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/visual/marks")).toHaveLength(0);
  });

  it.each([
    ["malformed", (response: ReturnType<typeof visualMarkResponse>) => {
      Reflect.deleteProperty(response.markSet, "mark_set_id");
    }],
    ["mismatched", (response: ReturnType<typeof visualMarkResponse>) => {
      response.markSet.marks[0].comment = "篡改提交内容";
    }],
    ["unsafe revision", (response: ReturnType<typeof visualMarkResponse>) => {
      response.snapshotRevision = Number.MAX_SAFE_INTEGER + 1;
    }],
  ])("does not advance its revision when a visual-contract mark response is %s", async (_label, mutate) => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const invalid = visualMarkResponse();
    mutate(invalid);
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(visualReviewProjection())), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(invalid), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(visualMarkResponse()), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();
    const input = {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      sourceVersion: "visual-v1",
      reviewSessionId: "visual-session-1",
      marks: [visualMark()],
    };

    const failure = await client.callTool("save_visual_contract_review_marks", input).then(
      () => null,
      (error: unknown) => error,
    );
    expect(failure).toMatchObject({ code: "VISUAL_CONTRACT_MARK_RESULT_UNCLOSED" });
    expect(fetchMock).toHaveBeenCalledTimes(3);

    const result = await client.callTool("save_visual_contract_review_marks", input);
    expect(result.snapshot.revision).toBe(9);
    await expect(client.callTool("save_visual_contract_review_marks", input)).rejects.toThrow(/revision/i);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("submits visual anchor feedback through its own scoped route", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(visualReviewProjection())), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        snapshotRevision: 10,
        batchRef: VISUAL_ANCHOR_BATCH_REF,
        batch: visualBatch(),
        hostNotificationStatus: "sent",
        aiReceiptStatus: "unverified",
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();

    const result = await client.callTool("submit_visual_anchor_feedback_batch", {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      sourceVersion: "visual-v1",
      reviewSessionId: "visual-session-1",
      feedback: [visualFeedback()],
    });

    expect(result.snapshot.revision).toBe(10);
    expect(result.batch.host_notification_status).toBe("sent");
    expect(result.batch.ai_receipt_status).toBe("unverified");
    expect(fetchMock.mock.calls[2][0]).toBe("/api/visual/anchor-feedback");
  });

  it("does not advance its revision when a real visual feedback response is malformed", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(visualReviewProjection())), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        snapshotRevision: 9,
        batchRef: VISUAL_ANCHOR_BATCH_REF,
        batch: { persistence_status: "saved", immutable_after_submit: true },
        hostNotificationStatus: "unavailable",
        aiReceiptStatus: "unverified",
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        snapshotRevision: 9,
        batchRef: VISUAL_ANCHOR_BATCH_REF,
        batch: visualBatch(),
        hostNotificationStatus: "unavailable",
        aiReceiptStatus: "unverified",
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();
    const input = {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      sourceVersion: "visual-v1",
      reviewSessionId: "visual-session-1",
      feedback: [visualFeedback()],
    };

    await expect(client.callTool("submit_visual_anchor_feedback_batch", input))
      .rejects.toThrow("提交结果未闭合");
    const result = await client.callTool("submit_visual_anchor_feedback_batch", input);
    expect(result.snapshot.revision).toBe(9);
    await expect(client.callTool("submit_visual_anchor_feedback_batch", input))
      .rejects.toThrow(/revision/i);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("does not advance its revision when a closed visual feedback response returns an unsafe next revision", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(visualReviewProjection())), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        snapshotRevision: Number.MAX_SAFE_INTEGER + 1,
        batchRef: VISUAL_ANCHOR_BATCH_REF,
        batch: visualBatch(),
        hostNotificationStatus: "unavailable",
        aiReceiptStatus: "unverified",
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        snapshotRevision: 9,
        batchRef: VISUAL_ANCHOR_BATCH_REF,
        batch: visualBatch(),
        hostNotificationStatus: "unavailable",
        aiReceiptStatus: "unverified",
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();
    const input = {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      sourceVersion: "visual-v1",
      reviewSessionId: "visual-session-1",
      feedback: [visualFeedback()],
    };

    const failure = await client.callTool("submit_visual_anchor_feedback_batch", input).then(
      () => null,
      (error: unknown) => error,
    );
    expect(failure).toMatchObject({ code: "VISUAL_ANCHOR_FEEDBACK_RESULT_UNCLOSED" });
    expect(fetchMock).toHaveBeenCalledTimes(3);

    const result = await client.callTool("submit_visual_anchor_feedback_batch", input);
    expect(result.snapshot.revision).toBe(9);
    await expect(client.callTool("submit_visual_anchor_feedback_batch", input)).rejects.toThrow(/revision/i);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("routes a content material asset through read_ai_ppt_project_asset", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(
        contentReviewProjection("review-assets/content/S01-M01.png"),
      )), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        asset: {
          assetRef: "review-assets/content/S01-M01.png",
          mimeType: "image/png",
          bytes: 3,
          dataBase64: "YWJj",
        },
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();

    const result = await client.callTool("read_ai_ppt_project_asset", {
      projectRoot: "/managed/project",
      assetRef: "review-assets/content/S01-M01.png",
    });

    expect(result.asset.mimeType).toBe("image/png");
    expect(fetchMock.mock.calls[2][0]).toBe(
      "/api/asset?assetRef=review-assets%2Fcontent%2FS01-M01.png",
    );
  });

  it("routes visual current and previous assets through the same project-asset tool", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const assetRefs = ["renders/S01-current.png", "renders/S01-previous.png"];
    const projection = visualReviewProjection();
    projection.anchors[0].current_asset_ref = assetRefs[0];
    projection.anchors[0].previous_asset_ref = assetRefs[1];
    projection.anchor_identity.render_assets[0].current_asset_ref = assetRefs[0];
    projection.anchor_identity.render_assets[0].previous_asset_ref = assetRefs[1];
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(projection)), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    for (const assetRef of assetRefs) {
      fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        asset: { assetRef, mimeType: "image/png", bytes: 3, dataBase64: "YWJj" },
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    }
    const client = createBrowserReviewClient();
    await client.connect();

    for (const assetRef of assetRefs) {
      const result = await client.callTool("read_ai_ppt_project_asset", {
        projectRoot: "/managed/project",
        assetRef,
      });
      expect(result.asset.assetRef).toBe(assetRef);
    }

    expect(fetchMock.mock.calls.slice(2).map(([url]) => url)).toEqual([
      "/api/asset?assetRef=renders%2FS01-current.png",
      "/api/asset?assetRef=renders%2FS01-previous.png",
    ]);
  });

  it("rejects project assets outside the connected project before calling the Bridge", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(contentReviewProjection())), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();

    await expect(client.callTool("read_ai_ppt_project_asset", {
      projectRoot: "/another/project",
      assetRef: "review-assets/content/S01-M01.png",
    })).rejects.toThrow("outside the review scope");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("saves content decisions and submits the batch through separate scoped routes", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewEnvelope(contentReviewProjection())), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        snapshotRevision: 9,
        decisionRef: `artifact://content-page-decision/${"d".repeat(64)}`,
        decision: { slide_id: "S01", decision: "approved", comment: "", status: "completed" },
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        snapshotRevision: 10,
        batchRef: `artifact://content-review-batch/${"e".repeat(64)}`,
        batch: { status: "submitted", immutable_after_submit: true },
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createBrowserReviewClient();
    await client.connect();
    const decision = await client.callTool("save_content_page_decision", {
      projectRoot: "/managed/project", expectedRevision: 8, sourceVersion: "content-v1",
      reviewSessionId: "content-session-1", slideId: "S01", decision: "approved", comment: "",
    });
    const batch = await client.callTool("submit_content_review_batch", {
      projectRoot: "/managed/project", expectedRevision: 9, sourceVersion: "content-v1",
      reviewSessionId: "content-session-1",
    });
    expect(decision.snapshot.revision).toBe(9);
    expect(batch.snapshot.revision).toBe(10);
    expect(fetchMock.mock.calls[2][0]).toBe("/api/content/decision");
    expect(fetchMock.mock.calls[3][0]).toBe("/api/content/batch");
  });

  it("preserves the scoped ReviewSession expiry code when a content save is rejected", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify(reviewEnvelope(contentReviewProjection())),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            hostOpenStatus: "opened",
            snapshotRevision: 8,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: false,
            error: { code: "REVIEW_SESSION_EXPIRED", message: "Review session expired." },
          }),
          { status: 410, headers: { "Content-Type": "application/json" } },
        ),
      );
    const client = createBrowserReviewClient();
    await client.connect();

    await expect(client.callTool("save_content_page_decision", {
      projectRoot: "/managed/project",
      expectedRevision: 8,
      sourceVersion: "content-v1",
      reviewSessionId: "content-session-1",
      slideId: "S01",
      decision: "approved",
      comment: "",
    })).rejects.toMatchObject({ code: "REVIEW_SESSION_EXPIRED" });
  });

  it("switches through the authenticated Bridge endpoint and navigates to the new scoped session", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const navigate = vi.fn();
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify(reviewEnvelope(contentReviewProjection())),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        hostOpenStatus: "opened",
        snapshotRevision: 8,
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            reviewType: "visual",
            sourceVersion: "visual-authoritative-v2",
            url: "http://127.0.0.1:43124/#token=independent-token",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const client = createBrowserReviewClient({ navigate });
    await client.connect();

    await client.switchReview("visual");

    expect(fetchMock).toHaveBeenLastCalledWith("/api/switch", {
      method: "POST",
      headers: {
        authorization: "Bearer short-lived-token",
        "content-type": "application/json",
      },
      body: JSON.stringify({ reviewType: "visual" }),
    });
    expect(navigate).toHaveBeenCalledWith(
      "http://127.0.0.1:43124/#token=independent-token",
    );
  });
});

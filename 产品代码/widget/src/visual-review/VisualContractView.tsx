import { useEffect, useId, useMemo, useRef, useState } from "react";

import type {
  ContractMarkComposerState,
  ContractMarkDraftState,
} from "../review-draft/reviewDraftStore";
import { parseArtifactReference } from "../lib/artifact-reference";
import type { HostBridge } from "../types/host";
import type { ToolContractMap } from "../types/tool-contracts";
import type { VisualContractReviewMark, VisualContractReviewMarkSet, VisualReviewSurfaceData } from "../types/visual-review";
import { ReviewOverlayDrawer } from "./ReviewOverlayDrawer";
import {
  sameVisualContractMarkSetImmutableAuthority,
  validateInitialVisualContractMarkSet,
  validateVisualContractMarkToolResult,
} from "./visual-contract-mark-validation";
import {
  isReviewWriteTimeout,
  withReviewWriteDeadline,
} from "./review-write-deadline";
import { VisualReceiptRecoveryControls } from "./VisualReceiptRecoveryControls";

interface Props {
  data: VisualReviewSurfaceData;
  bridge: HostBridge;
  revision: number;
  onRevision: (revision: number) => void;
  commandIdentity: string;
  drafts: ContractMarkDraftState[];
  composer: ContractMarkComposerState | null;
  onSliceChange: (
    drafts: ContractMarkDraftState[],
    composer: ContractMarkComposerState | null,
  ) => void;
  onClearSlice: () => void;
}

interface ContractWriteRequest {
  commandIdentity: string;
  commandRevision: number;
  drafts: ContractMarkDraftState[];
  marks: VisualContractReviewMark[];
  args: ToolContractMap["save_visual_contract_review_marks"]["input"];
}

const DESIGN_LABELS: Record<string, string> = {
  theme_proposition: "设计命题",
  typography_tokens: "字体与层级",
  color_tokens: "色彩系统",
  composition_grammar: "构图语法",
  page_families: "页面家族",
  imagery_strategy: "图像策略",
  diagram_strategy: "图示策略",
  table_strategy: "表格策略",
  editability_rules: "可编辑边界",
  fallback_fonts: "替代字体",
  forbidden_patterns: "明确禁止",
};

const SLIDE_LABELS: Record<string, string> = {
  page_task: "页面任务",
  page_family: "页面家族",
  frozen_copy: "冻结内容",
  speaker_notes: "完整演讲备注",
  source_refs: "来源引用",
  communication_goal: "沟通目标",
  composition_intent: "构图意图",
  information_hierarchy: "信息层级",
  reading_order: "阅读顺序",
  regions: "区域定义",
  object_relationships: "对象关系",
  native_bitmap_routing: "原生/位图路由",
  fallbacks: "降级方案",
  acceptance_criteria: "验收标准",
};

const OMIT_SLIDE_FIELDS = new Set(["slide_id", "order", "neutral_title", "title"]);
const ARTIFACT_KIND_LABELS: Record<string, string> = {
  "visual-contract": "视觉合同",
  "visual-contract-set": "视觉合同集",
};

export function visualSourceVersionLabel(sourceVersion: string): string {
  const artifact = parseArtifactReference(sourceVersion);
  if (!artifact) return sourceVersion;
  const { kind, digest } = artifact;
  const kindLabel = Object.hasOwn(ARTIFACT_KIND_LABELS, kind)
    ? ARTIFACT_KIND_LABELS[kind]
    : `视觉制品 ${kind}`;
  return `${kindLabel} ${digest.slice(0, 8)}`;
}

export function visualConfirmationLabel(g3Status: string): "已确认" | "尚未确认" {
  return g3Status === "passed" ? "已确认" : "尚未确认";
}

function labelFor(key: string, labels: Record<string, string>) {
  return labels[key] || key.replaceAll("_", " ");
}

function ContractValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    return <ul>{value.map((item, index) => <li key={index}><ContractValue value={item} /></li>)}</ul>;
  }
  if (value && typeof value === "object") {
    return (
      <dl className="contract-object-value">
        {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
          <div key={key}><dt>{labelFor(key, {})}</dt><dd><ContractValue value={item} /></dd></div>
        ))}
      </dl>
    );
  }
  return <p>{value === null || value === undefined || value === "" ? "无" : String(value)}</p>;
}

function notificationLabel(status: VisualContractReviewMarkSet["host_notification_status"]) {
  return ({ "not-requested": "未请求", pending: "通知中", sent: "已送达", failed: "失败", unavailable: "不可用" })[status];
}

function receiptLabel(status: VisualContractReviewMarkSet["ai_receipt_status"]) {
  return ({ pending: "待回执", received: "已接收", rejected: "已拒绝", unverified: "未验证" })[status];
}

const invalidRevisionMessage = "当前 revision 无效，请重新打开审核页后再保存。";

function validateProjectedMarkSet(data: VisualReviewSurfaceData): VisualContractReviewMarkSet | null {
  const projected = data.review.contract_review_marks;
  if (projected === null) return null;
  return validateInitialVisualContractMarkSet(projected, data, {
    hostNotificationStatus: projected.host_notification_status,
    aiReceiptStatus: projected.ai_receipt_status,
  })?.markSet ?? null;
}

function markTargetLabel(mark: Pick<
  ContractMarkDraftState,
  "slide_id" | "deck_section_id" | "target_key"
>) {
  const designSystem = mark.deck_section_id === "deck-design-system";
  const identity = designSystem ? "Deck Design System" : mark.slide_id;
  const label = labelFor(mark.target_key, designSystem ? DESIGN_LABELS : SLIDE_LABELS);
  return `${identity} · ${label}`;
}

export function VisualContractView({
  data,
  bridge,
  revision,
  onRevision,
  commandIdentity,
  drafts,
  composer,
  onSliceChange,
  onClearSlice,
}: Props) {
  const [drawer, setDrawer] = useState<"outline" | "marks" | null>(() => composer || drafts.length ? "marks" : null);
  const projectedMarkSet = useMemo(() => validateProjectedMarkSet(data), [data]);
  const [markSet, setMarkSet] = useState(projectedMarkSet);
  const [savedArtifactRef, setSavedArtifactRef] = useState<string | null>(
    projectedMarkSet ? data.review.contract_review_marks_ref : null,
  );
  const [saving, setSaving] = useState(false);
  const [retryPending, setRetryPending] = useState(false);
  const [message, setMessage] = useState("");
  const saveMutationGuard = useRef<symbol | null>(null);
  const mounted = useRef(true);
  const generation = useRef(0);
  const retryRequestRef = useRef<ContractWriteRequest | null>(null);
  const identityRef = useRef(commandIdentity);
  const revisionRef = useRef(revision);
  const highestObservedSnapshotRevisionRef = useRef(data.snapshotRevision);
  const authoritativeMarkRevisionRef = useRef(projectedMarkSet?.revision ?? -1);
  const authoritativeMarkSetRef = useRef(projectedMarkSet);
  const authoritativeMarkArtifactRef = useRef(projectedMarkSet ? data.review.contract_review_marks_ref : null);
  const rootRef = useRef<HTMLElement | null>(null);
  const designSystemRef = useRef<HTMLElement | null>(null);
  const anchorIdentityRef = useRef<HTMLElement | null>(null);
  const slideRefs = useRef(new Map<string, HTMLElement>());
  const instanceId = useId();
  const designSystemId = `${instanceId}-contract-design-system`;
  const anchorIdentityId = `${instanceId}-contract-anchor-identity`;
  const slides = data.review.slide_visual_contracts;
  const artifactSourceVersion = parseArtifactReference(data.review.source_version);
  identityRef.current = commandIdentity;
  revisionRef.current = revision;
  const hasUncommittedMark = composer !== null;
  const revisionIsValid = Number.isSafeInteger(revision)
    && revision >= 0
    && revision < Number.MAX_SAFE_INTEGER;
  const draftsLocked = saving || retryPending;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!saveMutationGuard.current && !retryRequestRef.current) return;
    generation.current += 1;
    saveMutationGuard.current = null;
    retryRequestRef.current = null;
    setSaving(false);
    setRetryPending(false);
    setMessage("当前视觉版本已变化；旧保存已失效，本地未保存标记和输入未改动，可重新保存。");
  }, [commandIdentity, revision]);

  useEffect(() => {
    if (data.snapshotRevision < highestObservedSnapshotRevisionRef.current) return;
    if (data.snapshotRevision > highestObservedSnapshotRevisionRef.current) {
      highestObservedSnapshotRevisionRef.current = data.snapshotRevision;
    }
    const projected = projectedMarkSet;
    if (!projected || projected.revision < authoritativeMarkRevisionRef.current) return;
    if (
      projected.revision === authoritativeMarkRevisionRef.current
      && authoritativeMarkSetRef.current
      && !sameVisualContractMarkSetImmutableAuthority(authoritativeMarkSetRef.current, projected)
    ) return;
    if (
      projected.revision === authoritativeMarkRevisionRef.current
      && authoritativeMarkArtifactRef.current
      && data.review.contract_review_marks_ref !== authoritativeMarkArtifactRef.current
    ) return;
    if (
      projected.revision === authoritativeMarkRevisionRef.current
      && authoritativeMarkSetRef.current
      && projected.host_notification_status === authoritativeMarkSetRef.current.host_notification_status
      && projected.ai_receipt_status === authoritativeMarkSetRef.current.ai_receipt_status
    ) return;
    authoritativeMarkRevisionRef.current = projected.revision;
    authoritativeMarkSetRef.current = projected;
    authoritativeMarkArtifactRef.current = data.review.contract_review_marks_ref;
    setMarkSet(projected);
    setSavedArtifactRef(data.review.contract_review_marks_ref);
  }, [data, projectedMarkSet]);

  const startFieldMark = (target: Pick<
    ContractMarkComposerState,
    "slide_id" | "deck_section_id" | "target_key"
  >) => {
    if (saveMutationGuard.current || retryRequestRef.current) return;
    onSliceChange(drafts, {
      editing_mark_id: "",
      target_type: "contract-field",
      slide_id: target.slide_id,
      deck_section_id: target.deck_section_id,
      target_key: target.target_key,
      selected_text: "",
      context_before: "",
      context_after: "",
      comment: "",
    });
    setDrawer("marks");
  };

  const startSelectionMark = () => {
    if (saveMutationGuard.current || retryRequestRef.current) return;
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !selection.toString().trim() || !selection.rangeCount) {
      setMessage("请先在视觉合同正文中选中需要标记的文字。");
      return;
    }
    const range = selection.getRangeAt(0);
    const valueForNode = (node: Node) => {
      const element = node.nodeType === Node.ELEMENT_NODE ? node as Element : node.parentElement;
      return element?.closest<HTMLElement>("[data-contract-value]") || null;
    };
    const contractValue = valueForNode(range.startContainer);
    if (!contractValue || valueForNode(range.endContainer) !== contractValue) {
      setMessage("选中文字必须完整位于一个合同字段正文内。");
      return;
    }
    const field = contractValue.closest<HTMLElement>("[data-contract-key]");
    if (!field) {
      setMessage("选中文字必须完整位于一个合同字段正文内。");
      return;
    }
    const rawSelectedText = range.toString();
    const selectedText = rawSelectedText.trim();
    const leadingTrimLength = rawSelectedText.length - rawSelectedText.trimStart().length;
    const prefixRange = document.createRange();
    prefixRange.selectNodeContents(contractValue);
    prefixRange.setEnd(range.startContainer, range.startOffset);
    const source = contractValue.textContent || "";
    const offset = prefixRange.toString().length + leadingTrimLength;
    onSliceChange(drafts, {
      editing_mark_id: "",
      target_type: "text-range",
      slide_id: field.dataset.slideId || "",
      deck_section_id: field.dataset.deckSectionId || "",
      target_key: field.dataset.contractKey || "",
      selected_text: selectedText,
      context_before: offset < 0 ? "" : source.slice(Math.max(0, offset - 80), offset).trim(),
      context_after: offset < 0 ? "" : source.slice(offset + selectedText.length, offset + selectedText.length + 80).trim(),
      comment: "",
    });
    setDrawer("marks");
  };

  const addMark = () => {
    if (saveMutationGuard.current || retryRequestRef.current || !composer || !composer.comment.trim()) return;
    const draft: ContractMarkDraftState = {
      mark_id: composer.editing_mark_id || globalThis.crypto?.randomUUID?.() || `mark-${Date.now()}`,
      target_type: composer.target_type,
      slide_id: composer.slide_id,
      deck_section_id: composer.deck_section_id,
      target_key: composer.target_key,
      selected_text: composer.selected_text,
      context_before: composer.context_before,
      context_after: composer.context_after,
      comment: composer.comment.trim(),
      created_at: new Date().toISOString(),
    };
    const nextDrafts = !composer.editing_mark_id
      ? [...drafts, draft]
      : drafts.some((item) => item.mark_id === composer.editing_mark_id)
        ? drafts.map((item) => item.mark_id === composer.editing_mark_id ? draft : item)
        : [...drafts, draft];
    onSliceChange(nextDrafts, null);
    setMessage("标记已加入待保存记录。");
  };

  const editMark = (draft: ContractMarkDraftState) => {
    if (saveMutationGuard.current || retryRequestRef.current) return;
    onSliceChange(drafts, {
      editing_mark_id: draft.mark_id,
      target_type: draft.target_type,
      slide_id: draft.slide_id,
      deck_section_id: draft.deck_section_id,
      target_key: draft.target_key,
      selected_text: draft.selected_text,
      context_before: draft.context_before,
      context_after: draft.context_after,
      comment: draft.comment,
    });
    setDrawer("marks");
  };

  const removeMark = (id: string) => {
    if (saveMutationGuard.current || retryRequestRef.current) return;
    onSliceChange(
      drafts.filter((item) => item.mark_id !== id),
      composer?.editing_mark_id === id ? null : composer,
    );
  };

  const abandonComposer = () => {
    if (saveMutationGuard.current || retryRequestRef.current) return;
    onSliceChange(drafts, null);
  };

  const closeMarks = () => {
    setDrawer(null);
    if (saveMutationGuard.current || retryRequestRef.current) return;
    onSliceChange(drafts, null);
  };

  const save = async () => {
    if (!drafts.length || hasUncommittedMark || saveMutationGuard.current) return;
    if (!revisionIsValid) {
      setMessage(invalidRevisionMessage);
      return;
    }
    const cachedRequest = retryRequestRef.current;
    if (
      cachedRequest
      && (
        cachedRequest.commandIdentity !== commandIdentity
        || cachedRequest.commandRevision !== revision
      )
    ) {
      retryRequestRef.current = null;
      setRetryPending(false);
      setMessage("当前视觉版本已变化；旧保存已失效，本地未保存标记和输入未改动，可重新保存。");
      return;
    }
    const request: ContractWriteRequest = cachedRequest || (() => {
      const snapshot = drafts.map((draft) => ({ ...draft }));
      const submittedMarks: VisualContractReviewMark[] = snapshot.map((draft) => ({
        mark_id: draft.mark_id,
        target_type: draft.target_type,
        slide_id: draft.slide_id,
        deck_section_id: draft.deck_section_id,
        target_key: draft.target_key,
        selected_text: draft.selected_text.trim(),
        context_before: draft.context_before.trim(),
        context_after: draft.context_after.trim(),
        comment: draft.comment,
        visual_contract_ref: data.review.visual_contract_ref,
        source_version: data.review.source_version,
        revision,
        created_at: draft.created_at,
        created_by: "user",
      }));
      return {
        commandIdentity,
        commandRevision: revision,
        drafts: snapshot,
        marks: submittedMarks,
        args: {
          projectRoot: data.selectedProjectRoot,
          expectedRevision: revision,
          reviewSessionId: data.review.review_session_id,
          sourceVersion: data.review.source_version,
          marks: submittedMarks,
        },
      };
    })();
    const saveToken = Symbol("visual-contract-mark-save");
    saveMutationGuard.current = saveToken;
    const saveGeneration = ++generation.current;
    const commandRevision = request.commandRevision;
    const submittedIdentity = request.commandIdentity;
    const commandIsCurrent = () => (
      mounted.current
      && generation.current === saveGeneration
      && identityRef.current === submittedIdentity
      && revisionRef.current === commandRevision
    );
    setSaving(true);
    setMessage("正在保存合同标记…");
    try {
      const result = await withReviewWriteDeadline((signal) => bridge.callTool(
        "save_visual_contract_review_marks",
        request.args,
        { signal },
      ));
      if (!commandIsCurrent()) return;
      const validated = validateVisualContractMarkToolResult(
        result,
        data,
        request.marks,
        commandRevision,
      );
      if (!validated) {
        retryRequestRef.current = null;
        setRetryPending(false);
        setMessage("保存结果未闭合，请刷新/重新打开核对；当前未保存标记和输入未改动。");
        return;
      }
      retryRequestRef.current = null;
      setRetryPending(false);
      highestObservedSnapshotRevisionRef.current = Math.max(
        highestObservedSnapshotRevisionRef.current,
        validated.revision,
      );
      authoritativeMarkRevisionRef.current = Math.max(authoritativeMarkRevisionRef.current, validated.markSet.revision);
      authoritativeMarkSetRef.current = validated.markSet;
      authoritativeMarkArtifactRef.current = validated.markSetRef;
      setMarkSet(validated.markSet);
      setSavedArtifactRef(validated.markSetRef);
      onRevision(validated.revision);
      onClearSlice();
      setMessage("合同标记已保存");
    } catch (error) {
      if (!commandIsCurrent()) return;
      const code = (error as Error & { code?: string }).code;
      if (isReviewWriteTimeout(error)) {
        retryRequestRef.current = request;
        setRetryPending(true);
        setMessage("保存请求超时；结果尚未确认，全部合同标记草稿仍保留。请使用相同内容重试。");
      } else if (code === "VISUAL_CONTRACT_MARK_RESULT_UNCLOSED") {
        retryRequestRef.current = null;
        setRetryPending(false);
        setMessage("保存结果未闭合，请刷新/重新打开核对；当前未保存标记和输入未改动。");
      } else if (code === "REVISION_CONFLICT" || code === "REVIEW_SOURCE_STALE") {
        retryRequestRef.current = null;
        setRetryPending(false);
        setMessage("当前视觉版本已变化；本地未保存标记和输入未改动，请刷新后重试。");
      } else {
        setMessage("合同标记尚未保存；全部草稿仍保留，可直接重试。");
      }
    } finally {
      if (saveMutationGuard.current === saveToken) {
        saveMutationGuard.current = null;
        if (commandIsCurrent()) setSaving(false);
      }
    }
  };

  const installReceiptFact = (fact: "host" | "ai", nextRevision: number) => {
    const current = authoritativeMarkSetRef.current;
    if (!current || !savedArtifactRef) return;
    const next: VisualContractReviewMarkSet = {
      ...current,
      ...(fact === "host"
        ? { host_notification_status: "sent" as const }
        : { ai_receipt_status: "received" as const }),
    };
    authoritativeMarkSetRef.current = next;
    highestObservedSnapshotRevisionRef.current = Math.max(highestObservedSnapshotRevisionRef.current, nextRevision);
    setMarkSet(next);
    onRevision(nextRevision);
  };

  const field = (
    key: string,
    value: unknown,
    label: string,
    location: { slideId: string; deckSectionId: string },
  ) => (
    <section
      className="visual-contract-field"
      key={key}
      data-contract-key={key}
      data-contract-label={label}
      data-slide-id={location.slideId}
      data-deck-section-id={location.deckSectionId}
      data-testid={`contract-field-${location.slideId || location.deckSectionId}-${key}`}
    >
      <header>
        <h4>{label}</h4>
        <button type="button" disabled={draftsLocked} aria-label={`标记 ${location.deckSectionId === "deck-design-system" ? "Deck Design System" : location.slideId} ${label}`} onClick={() => startFieldMark({
          slide_id: location.slideId,
          deck_section_id: location.deckSectionId,
          target_key: key,
        })}>＋ 标记</button>
      </header>
      <div data-contract-value>
        <ContractValue value={value} />
      </div>
    </section>
  );

  return (
    <section ref={rootRef} className="visual-contract-view" aria-label="完整视觉合同正文">
      <header className="visual-contract-toolbar visual-contract-title-page">
        <div className="visual-contract-heading">
          <span>Visual Contract · User Review</span>
          <h1>完整视觉合同</h1>
          <p>{data.review.project_name} · Deck Design System、3 页锚点身份和 {slides.length} 页逐页视觉需求来自同一视觉版本。</p>
        </div>
        <div className="visual-contract-actions">
          <button type="button" aria-label="打开合同目录" onClick={() => setDrawer("outline")}>目录</button>
          <button type="button" disabled={draftsLocked} aria-label="标记选中文字" onMouseDown={(event) => event.preventDefault()} onClick={startSelectionMark}>标记选中文字</button>
          <button type="button" aria-label="打开标记记录" onClick={() => setDrawer("marks")}>{drafts.length} 条标记</button>
          <button className="visual-primary-action" type="button" disabled={!drafts.length || hasUncommittedMark || saving || !revisionIsValid} onClick={save}>
            {saving ? "正在保存…" : drafts.length ? `保存 ${drafts.length} 条合同标记` : "保存合同标记"}
          </button>
        </div>
        <section className="visual-contract-summary" aria-label="视觉合同摘要">
          <dl>
            <div><dt>项目</dt><dd>{data.review.project_name}</dd></div>
            <div><dt>视觉版本</dt><dd>{visualSourceVersionLabel(data.review.source_version)}</dd></div>
            <div><dt>revision</dt><dd>{revision}</dd></div>
            <div><dt>G1</dt><dd>{data.review.gate_status.G1}</dd></div>
            <div><dt>G2</dt><dd>{data.review.gate_status.G2}</dd></div>
            <div><dt>G3</dt><dd>{visualConfirmationLabel(data.review.gate_status.G3)}</dd></div>
            <div><dt>合同页数</dt><dd>{slides.length} 页</dd></div>
            <div><dt>未保存标记</dt><dd aria-live="polite" aria-atomic="true">{drafts.length} 条</dd></div>
          </dl>
        </section>
      </header>
      {!revisionIsValid ? <p className="visual-operation-message" role="alert">{invalidRevisionMessage}</p> : null}
      {hasUncommittedMark ? <p className="visual-operation-message">请先加入合同标记或放弃当前输入，再统一保存。</p> : null}
      {message ? <p className="visual-operation-message" role="status">{message}</p> : null}
      {markSet ? (
        <>
          <div className="visual-receipt-row" aria-label="合同标记保存事实">
            <span>持久化：已保存</span>
            <span>宿主通知：{notificationLabel(markSet.host_notification_status)}</span>
            <span>AI 接收：{receiptLabel(markSet.ai_receipt_status)}</span>
            <strong>保存标记不等于 G3 通过</strong>
          </div>
          <VisualReceiptRecoveryControls
            bridge={bridge}
            commandIdentity={commandIdentity}
            projectRoot={data.selectedProjectRoot}
            reviewSessionId={data.review.review_session_id}
            sourceVersion={data.review.source_version}
            revision={revision}
            savedArtifactRef={savedArtifactRef}
            hostStatus={markSet.host_notification_status}
            aiStatus={markSet.ai_receipt_status}
            hostCapability={data.review.host_submission_capability}
            aiCapability={data.review.ai_receipt_capability}
            onHostSent={(nextRevision) => installReceiptFact("host", nextRevision)}
            onAiReceived={(nextRevision) => installReceiptFact("ai", nextRevision)}
          />
        </>
      ) : null}

      <article className="visual-contract-document">
        <details className="visual-contract-technical">
          <summary>技术信息</summary>
          <dl>
            {artifactSourceVersion && data.review.source_version === data.review.visual_contract_ref ? (
              <div><dt>视觉 source version / 视觉合同 artifact</dt><dd><code>{data.review.source_version}</code></dd></div>
            ) : (
              <>
                {artifactSourceVersion ? <div><dt>视觉 source version</dt><dd><code>{data.review.source_version}</code></dd></div> : null}
                <div><dt>视觉合同 artifact</dt><dd><code>{data.review.visual_contract_ref}</code></dd></div>
              </>
            )}
            <div><dt>Deck Design System artifact</dt><dd><code>{data.review.deck_design_system_ref}</code></dd></div>
            <div><dt>锚点集 artifact</dt><dd><code>{data.review.anchor_slide_set_ref}</code></dd></div>
          </dl>
        </details>
        <section
          ref={designSystemRef}
          id={designSystemId}
          className="visual-contract-chapter"
          data-contract-logical-object="deck-design-system"
        >
          <h2>Deck Design System</h2>
          <p>整套视觉一致性的唯一设计系统。</p>
          <div className="visual-design-system-grid">
            {Object.entries(data.review.deck_design_system).map(([key, value]) => field(
              key, value, labelFor(key, DESIGN_LABELS), { slideId: "", deckSectionId: "deck-design-system" },
            ))}
          </div>
        </section>
        <section
          ref={anchorIdentityRef}
          id={anchorIdentityId}
          className="visual-contract-chapter anchor-identity-chapter"
          data-contract-logical-object="anchor-slide-evidence"
        >
          <h2>Anchor Slide Evidence</h2>
          <p>锚点身份、选择理由和实现证据。</p>
          <ContractValue value={data.review.anchor_identity} />
        </section>
        <section className="visual-slide-contracts" aria-label="全部逐页视觉合同">
          {slides.map((slide, index) => {
            const slideId = String(slide.slide_id || `slide-${index + 1}`);
            const title = String(slide.neutral_title || slide.title || slide.page_task || `${slideId} 视觉合同`);
            const articleId = `${instanceId}-visual-contract-${index}`;
            const titleId = `${articleId}-title`;
            return (
              <article
                ref={(node) => {
                  if (node) slideRefs.current.set(slideId, node);
                  else slideRefs.current.delete(slideId);
                }}
                id={articleId}
                className="visual-slide-contract"
                aria-labelledby={titleId}
                data-contract-logical-object={slideId}
                key={slideId}
              >
                <header><span>{slideId} · 第 {String(slide.order || index + 1)} 页</span><h3 id={titleId}>{title}</h3></header>
                <div className="visual-slide-contract-grid">
                  {Object.entries(slide).filter(([key]) => !OMIT_SLIDE_FIELDS.has(key)).map(([key, value]) => field(
                    key, value, labelFor(key, SLIDE_LABELS), { slideId, deckSectionId: "" },
                  ))}
                </div>
              </article>
            );
          })}
        </section>
      </article>

      <ReviewOverlayDrawer open={drawer === "outline"} title="视觉合同目录" onClose={() => setDrawer(null)}>
        <nav className="visual-contract-outline" aria-label="视觉合同章节定位">
          <button type="button" onClick={() => { designSystemRef.current?.scrollIntoView(); setDrawer(null); }}>Deck Design System</button>
          <button type="button" onClick={() => { anchorIdentityRef.current?.scrollIntoView(); setDrawer(null); }}>Anchor Slide Evidence</button>
          {slides.map((slide) => <button type="button" key={String(slide.slide_id)} onClick={() => { slideRefs.current.get(String(slide.slide_id))?.scrollIntoView(); setDrawer(null); }}>{String(slide.slide_id)} · {String(slide.neutral_title || slide.title || slide.page_task || "视觉合同")}</button>)}
        </nav>
      </ReviewOverlayDrawer>
      <ReviewOverlayDrawer open={drawer === "marks"} title="合同标记记录" onClose={closeMarks}>
        {composer ? (
          <div className="contract-mark-composer">
            <strong>{composer.editing_mark_id ? `正在编辑：${markTargetLabel(composer)}` : markTargetLabel(composer)}</strong>
            {composer.selected_text ? <blockquote>{composer.selected_text}</blockquote> : null}
            <label><span>合同标记意见</span><textarea
              autoFocus
              disabled={draftsLocked}
              aria-label="合同标记意见"
              value={composer.comment}
              onChange={(event) => onSliceChange(drafts, { ...composer, comment: event.target.value })}
            /></label>
            <button type="button" disabled={!composer.comment.trim() || draftsLocked} onClick={addMark}>加入合同标记</button>
            <button className="contract-mark-abandon" type="button" disabled={draftsLocked} onClick={abandonComposer}>放弃本次标记</button>
          </div>
        ) : null}
        {drafts.length ? <ol className="contract-mark-list">{drafts.map((draft) => <li key={draft.mark_id}><strong>{markTargetLabel(draft)}</strong><p>{draft.comment}</p><div className="contract-mark-item-actions"><button type="button" disabled={draftsLocked} aria-label={`编辑 ${draft.comment}`} onClick={() => editMark(draft)}>编辑</button><button type="button" disabled={draftsLocked} aria-label={`移除 ${draft.comment}`} onClick={() => removeMark(draft.mark_id)}>移除</button></div></li>)}</ol> : <p className="visual-empty">暂无待保存标记。可标记字段或先选中文字。</p>}
        {markSet?.marks.length ? <p className="saved-mark-summary">已保存 {markSet.marks.length} 条合同标记。</p> : null}
      </ReviewOverlayDrawer>
    </section>
  );
}

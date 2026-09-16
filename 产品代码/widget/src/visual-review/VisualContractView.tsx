import { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type {
  ContractMarkComposerState,
  ContractMarkDraftState,
} from "../review-draft/reviewDraftStore";
import { parseArtifactReference } from "../lib/artifact-reference";
import type { HostBridge } from "../types/host";
import type { ToolContractMap } from "../types/tool-contracts";
import type { VisualContractReviewMark, VisualContractReviewMarkSet } from "../types/visual-review";
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
import {
  DESIGN_SYSTEM_FIELD_ORDER,
  FROZEN_SLIDE_FIELD_ORDER,
  VISUAL_BRIEF_FIELD_ORDER,
  VISUAL_SLIDE_FIELD_ORDER,
} from "./visual-contract-field-contract";
import type {
  VisualReviewPageSlideContract,
  VisualReviewPageViewModel,
} from "./visual-review-page-view-model";

interface Props {
  data: VisualReviewPageViewModel;
  bridge: HostBridge;
  revision: number;
  onRevision: (revision: number) => void;
  commandIdentity: string;
  toolbarHost?: HTMLElement | null;
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

const BRIEF_LABELS: Record<string, string> = {
  decision_task: "决策任务",
  design_stance: "设计立场",
  audience_fit: "受众与阅读场景",
  emotional_boundary: "情绪边界",
  brand_boundary: "品牌边界",
  density_strategy: "密度策略",
  narrative_rhythm: "叙事节奏",
  imagery_strategy: "图像总策略",
  diagram_strategy: "图示总策略",
  powerpoint_constraints: "PowerPoint 约束",
  forbidden_patterns: "整套禁止模式",
  five_second_test_contract: "五秒判断口径",
  design_philosophy_refs: "设计哲学参考",
};

const DESIGN_LABELS: Record<string, string> = {
  theme_proposition: "设计命题",
  typography_tokens: "字体与层级",
  color_tokens: "色彩系统",
  composition_grammar: "构图语法",
  page_families: "页面家族",
  density_rhythm: "密度节奏",
  cross_slide_rhythm_rules: "跨页节奏规则",
  emphasis_budget: "强调预算",
  imagery_strategy: "图像策略",
  image_language: "图像语言",
  diagram_strategy: "图示策略",
  diagram_language: "图示语言",
  table_strategy: "表格策略",
  editability_rules: "可编辑边界",
  accessibility_rules: "可访问性",
  fallback_fonts: "替代字体",
  forbidden_patterns: "明确禁止",
  five_second_test_rules: "五秒判断规则",
  anchor_specification: "锚点规范",
};

const SLIDE_LABELS: Record<string, string> = {
  core_claim: "核心主张",
  page_family: "页面家族",
  visible_copy: "页面可见文案",
  visible_copy_blocks: "页面可见文案",
  speaker_notes: "讲解备注",
  source_refs: "来源引用",
  communication_goal: "沟通目标",
  composition_intent: "构图意图",
  information_hierarchy: "信息层级",
  reading_order: "阅读顺序",
  regions: "页面区域",
  object_relationships: "对象关系",
  diagram_chart_table_treatment: "图示／图表／表格",
  image_selection_and_crop: "图像选择与裁切",
  color_application: "色彩应用",
  typography_application: "字体应用",
  native_bitmap_routing: "原生／位图路由",
  editability_requirements: "可编辑要求",
  fallbacks: "降级策略",
  acceptance_criteria: "验收标准",
  reader_judgment: "读者五秒判断",
  primary_relationship: "主信息关系",
  secondary_relationship: "辅助信息关系",
  visual_mechanism: "视觉机制",
  focal_point: "视觉重心",
  asset_roles: "资产角色",
  forbidden_patterns: "页面禁止模式",
  previous_rhythm_relation: "与前页节奏",
  next_rhythm_relation: "与后页节奏",
  text_density_budget: "文字密度预算",
  powerpoint_implementation_requirements: "PowerPoint 实现要求",
  acceptance_evidence_plan: "验收证据计划",
};

const CONTRACT_VALUE_LABELS: Record<string, string> = {
  accent: "强调色",
  ink: "正文色",
  title: "标题",
  body: "正文",
  fallback_fonts: "替代字体",
  region_id: "区域标识",
  purpose: "用途",
  criterion_id: "验收项",
  level: "级别",
  expected_outcome: "预期结果",
  slide_ids: "锚点页",
  selection_reason: "选择理由",
  native_first_frozen: "原生可编辑已冻结",
};

const MISSING_CONTRACT_VALUE = "待后端按前端字段合同提供";

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

function labelFor(key: string, labels: Record<string, string>) {
  return labels[key] || key.replaceAll("_", " ");
}

function presentContractValue(value: unknown): unknown {
  return value === undefined || value === null || value === ""
    ? MISSING_CONTRACT_VALUE
    : value;
}

function slideFieldValue(
  slide: VisualReviewPageSlideContract,
  key: keyof VisualReviewPageSlideContract,
): unknown {
  if (key === "secondary_relationship" && slide[key] === null) return null;
  return presentContractValue(slide[key]);
}

function ContractValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    return <ul>{value.map((item, index) => <li key={index}><ContractValue value={item} /></li>)}</ul>;
  }
  if (value && typeof value === "object") {
    return (
      <dl className="contract-object-value">
        {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
          <div key={key}><dt>{labelFor(key, CONTRACT_VALUE_LABELS)}</dt><dd><ContractValue value={item} /></dd></div>
        ))}
      </dl>
    );
  }
  if (value === null || value === undefined || value === "") return <p>无</p>;
  const text = String(value);
  return <p>{text === MISSING_CONTRACT_VALUE ? text : <span data-contract-anchor-leaf>{text}</span>}</p>;
}

function paletteTextIsDark(color: string): boolean {
  const match = /^#([\da-f]{6})$/i.exec(color.trim());
  if (!match) return false;
  const value = match[1];
  const red = Number.parseInt(value.slice(0, 2), 16);
  const green = Number.parseInt(value.slice(2, 4), 16);
  const blue = Number.parseInt(value.slice(4, 6), 16);
  return ((red * 299) + (green * 587) + (blue * 114)) / 1000 > 170;
}

function isCssPaletteColor(value: unknown): value is string {
  return typeof value === "string"
    && /^(?:#[\da-f]{3,8}|rgba?\(|hsla?\()/i.test(value.trim());
}

function ColorPaletteValue({ value }: { value: unknown }) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return <ContractValue value={value} />;
  const tokens = Object.entries(value as Record<string, unknown>).filter(
    (entry): entry is [string, string] => typeof entry[1] === "string",
  );
  if (!tokens.some(([, token]) => isCssPaletteColor(token))) return <ContractValue value={value} />;
  return (
    <div className="visual-palette-line" data-testid="visual-color-palette">
      {tokens.map(([key, token]) => {
        const color = isCssPaletteColor(token) ? token : null;
        return (
          <span
            className={`visual-palette-swatch${!color || paletteTextIsDark(color) ? " light" : ""}`}
            style={{ background: color || "#F3F4F6" }}
            key={key}
          >
            <strong>{labelFor(key, CONTRACT_VALUE_LABELS)}</strong>
            <small data-contract-anchor-leaf>{token}</small>
          </span>
        );
      })}
    </div>
  );
}

interface ReadableContractPart {
  prefix: string;
  value: string;
}

function readableContractParts(value: unknown, prefix = ""): ReadableContractPart[] {
  if (value === null || value === undefined || value === "") return [];
  if (Array.isArray(value)) return value.flatMap((item) => readableContractParts(item, prefix));
  if (typeof value !== "object") return [{ prefix, value: String(value) }];
  return Object.entries(value as Record<string, unknown>).flatMap(([key, item]) => (
    readableContractParts(item, `${prefix}${labelFor(key, CONTRACT_VALUE_LABELS)}：`)
  ));
}

function DeckDesignSystemValue({ fieldKey, value }: { fieldKey: string; value: unknown }) {
  if (fieldKey === "color_tokens") return <ColorPaletteValue value={value} />;
  if (fieldKey === "typography_tokens" || fieldKey === "density_rhythm") {
    const parts = readableContractParts(value);
    return parts.length ? <p>{parts.map((part, index) => (
      <span key={index}>
        {index ? "；" : ""}{part.prefix}<span data-contract-anchor-leaf>{part.value}</span>
      </span>
    ))}</p> : <ContractValue value={value} />;
  }
  return <ContractValue value={value} />;
}

function anchorLeafForNode(node: Node): HTMLElement | null {
  const element = node.nodeType === Node.ELEMENT_NODE ? node as Element : node.parentElement;
  return element?.closest<HTMLElement>("[data-contract-anchor-leaf]") || null;
}

const ECMASCRIPT_WHITESPACE_RUN = /[\u0009-\u000D\u0020\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000\uFEFF]+/gu;
const ECMASCRIPT_NON_WHITESPACE_RUN = /[^\u0009-\u000D\u0020\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000\uFEFF]+/gu;
const ECMASCRIPT_WHITESPACE_CHARACTER = /[\u0009-\u000D\u0020\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000\uFEFF]/u;

function normalizedContractAnchorText(value: string): string {
  return value.replace(ECMASCRIPT_WHITESPACE_RUN, " ").replace(/^ | $/gu, "");
}

function leafOffsetForBoundary(
  leaf: HTMLElement,
  node: Node,
  offset: number,
): number {
  const prefix = document.createRange();
  prefix.selectNodeContents(leaf);
  prefix.setEnd(node, offset);
  return prefix.toString().length;
}

function normalizedBoundaryOffset(
  value: string,
  offset: number,
  side: "start" | "end",
): number {
  const tokens = [...value.matchAll(ECMASCRIPT_NON_WHITESPACE_RUN)];
  let normalizedStart = 0;
  let previousEnd = 0;
  for (const [index, token] of tokens.entries()) {
    const start = token.index;
    const end = start + token[0].length;
    if (index) normalizedStart = previousEnd + 1;
    const normalizedEnd = normalizedStart + token[0].length;
    if (offset < start) return side === "start" ? normalizedStart : previousEnd;
    if (offset <= end) return normalizedStart + Math.max(0, offset - start);
    previousEnd = normalizedEnd;
  }
  return previousEnd;
}

function textAnchorForRange(
  contractValue: HTMLElement,
  range: Range,
): { selectedText: string; contextBefore: string; contextAfter: string } | null {
  const startLeaf = anchorLeafForNode(range.startContainer);
  const endLeaf = anchorLeafForNode(range.endContainer);
  if (!startLeaf || !endLeaf || !contractValue.contains(startLeaf) || !contractValue.contains(endLeaf)) {
    return null;
  }
  const leaves = [...contractValue.querySelectorAll<HTMLElement>("[data-contract-anchor-leaf]")];
  const startIndex = leaves.indexOf(startLeaf);
  const endIndex = leaves.indexOf(endLeaf);
  if (startIndex < 0 || endIndex < startIndex) return null;

  const normalizedLeaves = leaves.map((leaf) => normalizedContractAnchorText(leaf.textContent || ""));
  const leafStarts: number[] = [];
  let cursor = 0;
  for (const [index, value] of normalizedLeaves.entries()) {
    leafStarts.push(cursor);
    cursor += value.length;
    if (index < normalizedLeaves.length - 1) cursor += 1;
  }
  const source = normalizedLeaves.join(" ");
  let start = leafStarts[startIndex] + normalizedBoundaryOffset(
    startLeaf.textContent || "",
    leafOffsetForBoundary(startLeaf, range.startContainer, range.startOffset),
    "start",
  );
  let end = leafStarts[endIndex] + normalizedBoundaryOffset(
    endLeaf.textContent || "",
    leafOffsetForBoundary(endLeaf, range.endContainer, range.endOffset),
    "end",
  );
  while (start < end && ECMASCRIPT_WHITESPACE_CHARACTER.test(source[start])) start += 1;
  while (end > start && ECMASCRIPT_WHITESPACE_CHARACTER.test(source[end - 1])) end -= 1;
  const selectedText = source.slice(start, end);
  if (!selectedText) return null;
  return {
    selectedText,
    contextBefore: [...source.slice(0, start)].slice(-80).join("").trim(),
    contextAfter: [...source.slice(end)].slice(0, 80).join("").trim(),
  };
}

function notificationLabel(status: VisualContractReviewMarkSet["host_notification_status"]) {
  return ({ "not-requested": "未请求", pending: "通知中", sent: "已送达", failed: "失败", unavailable: "不可用" })[status];
}

function receiptLabel(status: VisualContractReviewMarkSet["ai_receipt_status"]) {
  return ({ pending: "待回执", received: "已接收", rejected: "已拒绝", unverified: "未验证" })[status];
}

const invalidRevisionMessage = "当前 revision 无效，请重新打开审核页后再保存。";

function validateProjectedMarkSet(data: VisualReviewPageViewModel): VisualContractReviewMarkSet | null {
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
  const visualBrief = mark.deck_section_id === "visual-brief";
  const designSystem = mark.deck_section_id === "deck-design-system";
  const identity = visualBrief
    ? "Visual Brief"
    : designSystem
      ? "Deck Design System"
      : mark.slide_id;
  const labels = visualBrief ? BRIEF_LABELS : designSystem ? DESIGN_LABELS : SLIDE_LABELS;
  const label = labelFor(mark.target_key, labels);
  return `${identity} · ${label}`;
}

export function VisualContractView({
  data,
  bridge,
  revision,
  onRevision,
  commandIdentity,
  toolbarHost,
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
  const [selectionToolbar, setSelectionToolbar] = useState<{ top: number; left: number } | null>(null);
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
  const visualBriefRef = useRef<HTMLElement | null>(null);
  const designSystemRef = useRef<HTMLElement | null>(null);
  const anchorIdentityRef = useRef<HTMLElement | null>(null);
  const slideRefs = useRef(new Map<string, HTMLElement>());
  const outlineNavigationFrameRef = useRef<number | null>(null);
  const instanceId = useId();
  const visualBriefId = `${instanceId}-contract-visual-brief`;
  const designSystemId = `${instanceId}-contract-design-system`;
  const anchorIdentityId = `${instanceId}-contract-anchor-identity`;
  const slides = data.review.slide_visual_contracts;
  const slideById = useMemo(
    () => new Map(slides.map((slide) => [slide.slide_id, slide])),
    [slides],
  );
  const anchorEvidence = useMemo(
    () => data.review.anchor_identity.slide_ids.map((slideId) => {
      const slide = slideById.get(slideId);
      const pageFamily = typeof slide?.page_family === "string" && slide.page_family.trim()
        ? slide.page_family
        : "锚点视觉证据";
      const title = slide?.anchor_title || pageFamily;
      const pageTask = slide?.validation_purpose || data.review.anchor_identity.selection_reason;
      return { slideId, title, pageTask };
    }),
    [data.review.anchor_identity.selection_reason, data.review.anchor_identity.slide_ids, slideById],
  );
  const visualBriefRows = useMemo(
    () => VISUAL_BRIEF_FIELD_ORDER.map((key) => ({
      key,
      label: labelFor(key, BRIEF_LABELS),
      value: presentContractValue(data.review.visual_brief[key]),
    })),
    [data.review.visual_brief],
  );
  const designSystemRows = useMemo(
    () => DESIGN_SYSTEM_FIELD_ORDER.map((key) => {
      let value: unknown = data.review.deck_design_system[key];
      if (key === "typography_tokens" && data.review.deck_design_system.fallback_fonts !== undefined) {
        value = {
          ...(value && typeof value === "object" ? value as Record<string, unknown> : {}),
          fallback_fonts: data.review.deck_design_system.fallback_fonts,
        };
      }
      if (key === "anchor_specification" && value === undefined) {
        value = {
          slide_ids: data.review.anchor_identity.slide_ids,
          selection_reason: data.review.anchor_identity.selection_reason,
          native_first_frozen: data.review.anchor_identity.native_first_frozen,
        };
      }
      return { key, label: labelFor(key, DESIGN_LABELS), value: presentContractValue(value) };
    }),
    [data.review.anchor_identity, data.review.deck_design_system],
  );
  identityRef.current = commandIdentity;
  revisionRef.current = revision;
  const hasUncommittedMark = composer !== null;
  const revisionIsValid = Number.isSafeInteger(revision)
    && revision >= 0
    && revision < Number.MAX_SAFE_INTEGER;
  const draftsLocked = saving || retryPending;

  const updateSelectionToolbar = () => {
    if (draftsLocked) {
      setSelectionToolbar(null);
      return;
    }
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !normalizedContractAnchorText(selection.toString()) || !selection.rangeCount) {
      setSelectionToolbar(null);
      return;
    }
    const range = selection.getRangeAt(0);
    const valueForNode = (node: Node) => {
      const element = node.nodeType === Node.ELEMENT_NODE ? node as Element : node.parentElement;
      return element?.closest<HTMLElement>("[data-contract-value]") || null;
    };
    const contractValue = valueForNode(range.startContainer);
    if (!contractValue || valueForNode(range.endContainer) !== contractValue || !rootRef.current?.contains(contractValue)) {
      setSelectionToolbar(null);
      return;
    }
    if (!anchorLeafForNode(range.startContainer) || !anchorLeafForNode(range.endContainer)) {
      setSelectionToolbar(null);
      return;
    }
    const rect = typeof range.getBoundingClientRect === "function"
      ? range.getBoundingClientRect()
      : contractValue.getBoundingClientRect();
    setSelectionToolbar({
      top: Math.max(70, rect.top - 42),
      left: Math.max(12, Math.min(window.innerWidth - 150, rect.left + (rect.width / 2) - 60)),
    });
  };

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
      if (outlineNavigationFrameRef.current !== null) {
        window.cancelAnimationFrame(outlineNavigationFrameRef.current);
        outlineNavigationFrameRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const clearSelectionToolbar = () => setSelectionToolbar(null);
    document.addEventListener("selectionchange", updateSelectionToolbar);
    window.addEventListener("resize", clearSelectionToolbar);
    return () => {
      document.removeEventListener("selectionchange", updateSelectionToolbar);
      window.removeEventListener("resize", clearSelectionToolbar);
    };
  }, [draftsLocked]);

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
    setSelectionToolbar(null);
    setDrawer("marks");
  };

  const navigateFromOutline = (target: () => HTMLElement | null | undefined) => {
    setDrawer(null);
    if (outlineNavigationFrameRef.current !== null) {
      window.cancelAnimationFrame(outlineNavigationFrameRef.current);
    }
    outlineNavigationFrameRef.current = window.requestAnimationFrame(() => {
      target()?.scrollIntoView({ behavior: "auto", block: "start" });
      outlineNavigationFrameRef.current = window.requestAnimationFrame(() => {
        outlineNavigationFrameRef.current = null;
        target()?.scrollIntoView({ behavior: "auto", block: "start" });
      });
    });
  };

  const startSelectionMark = () => {
    if (saveMutationGuard.current || retryRequestRef.current) return;
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !normalizedContractAnchorText(selection.toString()) || !selection.rangeCount) {
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
    const anchor = textAnchorForRange(contractValue, range);
    if (!anchor) {
      setMessage("选中文字必须完整位于合同正文值内。请避开展示标签后重试。");
      return;
    }
    onSliceChange(drafts, {
      editing_mark_id: "",
      target_type: "text-range",
      slide_id: field.dataset.slideId || "",
      deck_section_id: field.dataset.deckSectionId || "",
      target_key: field.dataset.contractKey || "",
      selected_text: anchor.selectedText,
      context_before: anchor.contextBefore,
      context_after: anchor.contextAfter,
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
        selected_text: normalizedContractAnchorText(draft.selected_text),
        context_before: normalizedContractAnchorText(draft.context_before),
        context_after: normalizedContractAnchorText(draft.context_after),
        comment: draft.comment,
        visual_contract_ref: data.review.visual_contract_ref,
        source_version: data.review.source_version,
        revision,
        created_at: draft.created_at,
        created_by: "user",
        ...(draft.target_type === "text-range"
          ? { anchor_representation_version: "browser-v2" as const }
          : {}),
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
  ) => {
    const targetIdentity = location.deckSectionId === "visual-brief"
      ? "Visual Brief"
      : location.deckSectionId === "deck-design-system"
        ? "Deck Design System"
        : location.slideId;
    return (
    <section
      className="visual-contract-field"
      key={key}
      data-contract-key={key}
      data-contract-label={label}
      data-slide-id={location.slideId}
      data-deck-section-id={location.deckSectionId}
      data-contract-missing={value === MISSING_CONTRACT_VALUE ? "true" : undefined}
      data-testid={`contract-field-${location.slideId || location.deckSectionId}-${key}`}
    >
      <header>
        <h4>{label}</h4>
        <button type="button" disabled={draftsLocked} aria-label={`标记 ${targetIdentity} ${label}`} onClick={() => startFieldMark({
          slide_id: location.slideId,
          deck_section_id: location.deckSectionId,
          target_key: key,
        })} />
      </header>
      <div data-contract-value>
        {location.deckSectionId === "deck-design-system"
          ? <DeckDesignSystemValue fieldKey={key} value={value} />
          : <ContractValue value={value} />}
      </div>
    </section>
    );
  };

  const commandBar = (
    <div className="visual-contract-commandbar" aria-label="视觉合同操作">
      <div className="visual-contract-command-actions">
        <button type="button" aria-label="打开合同目录" onClick={() => setDrawer("outline")}>目录</button>
        <span className="visual-contract-command-status" aria-live="polite" aria-atomic="true">
          {drafts.length ? `${drafts.length} 条待保存标记` : "所有标记已保存"}
        </span>
        <button type="button" aria-label="打开标记记录" onClick={() => setDrawer("marks")}><span className="visual-contract-mark-count">{drafts.length}</span>标记</button>
        <button className="visual-primary-action" type="button" disabled={!drafts.length || hasUncommittedMark || saving || !revisionIsValid} onClick={save}>
          {saving ? "正在保存…" : drafts.length ? `保存 ${drafts.length} 条合同标记` : "保存合同标记"}
        </button>
      </div>
    </div>
  );

  return (
    <section ref={rootRef} className="visual-contract-view" aria-label="完整视觉合同正文">
      {toolbarHost ? createPortal(commandBar, toolbarHost) : commandBar}
      <div className="visual-contract-feedback-facts">
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
      </div>

      {selectionToolbar ? <div className="visual-selection-toolbar" style={selectionToolbar}>
        <button type="button" disabled={draftsLocked} aria-label="标记选中文字" onMouseDown={(event) => event.preventDefault()} onClick={startSelectionMark}>标记选中文字</button>
      </div> : null}

      <article className="visual-contract-document" onMouseUp={updateSelectionToolbar}>
        <header className="visual-contract-title-page">
          <div className="visual-contract-kicker">Visual Contract · User Review</div>
          <h1>完整视觉合同</h1>
          <p>从整套设计系统到全部逐页视觉合同连续展开。请判断全套视觉需求是否一致，以及每一页是否被 AI 正确理解；目录只负责定位，标记抽屉只在需要时覆盖打开。</p>
          <div className="visual-contract-identity-line">
            <span><strong>范围</strong> {slides.length} 页逐页合同</span>
            <span><strong>生产路线</strong> {String(presentContractValue(data.review.deck_design_system.production_route))}</span>
            <span className="visual-hidden-technical"><strong>项目</strong> {data.review.project_name}</span>
            <span className="visual-hidden-technical"><strong>revision</strong> {revision}</span>
          </div>
        </header>
        <section
          ref={visualBriefRef}
          id={visualBriefId}
          className="visual-contract-section visual-contract-chapter"
          data-contract-logical-object="visual-brief"
        >
          <header className="visual-contract-section-head">
            <h2>Visual Brief</h2>
            <span>{String(presentContractValue(data.review.visual_brief.design_proposition))}</span>
          </header>
          <div className="visual-design-system-grid">
            {visualBriefRows.map(({ key, label, value }) => field(
              key, value, label, { slideId: "", deckSectionId: "visual-brief" },
            ))}
          </div>
        </section>
        <section
          ref={designSystemRef}
          id={designSystemId}
          className="visual-contract-section visual-contract-chapter"
          data-contract-logical-object="deck-design-system"
        >
          <header className="visual-contract-section-head"><h2>Deck Design System</h2><span>整套一致性合同</span></header>
          <div className="visual-design-system-grid">
            {designSystemRows.map(({ key, label, value }) => field(
              key, value, label, { slideId: "", deckSectionId: "deck-design-system" },
            ))}
          </div>
        </section>
        <section
          ref={anchorIdentityRef}
          id={anchorIdentityId}
          className="visual-contract-section visual-contract-chapter anchor-identity-chapter"
          data-contract-logical-object="anchor-slide-evidence"
        >
          <header className="visual-contract-section-head"><h2>Anchor Slide Evidence</h2><span>{anchorEvidence.length} 页原生锚点身份</span></header>
          <div className="visual-anchor-evidence-strip">
            {anchorEvidence.map(({ slideId, pageTask, title }) => (
              <article className="visual-anchor-evidence-item" key={slideId}>
                <b>{slideId}</b>
                <strong>{title}</strong>
                <span>{pageTask}</span>
              </article>
            ))}
          </div>
          <p className="visual-contract-footnote">{data.review.anchor_identity.selection_reason}。锚点用于验证设计系统能否原生实现，原生可编辑与预检渲染证据已登记；完整合同仍覆盖全部 {slides.length} 页，不以锚点代替整套页面需求。</p>
        </section>
        <section className="visual-contract-section visual-slide-contracts" aria-label="全部逐页视觉合同">
          <header className="visual-contract-section-head"><h2>全部 Slide Visual Contract</h2><span>{slides.length} 页 · 连续阅读</span></header>
          <div className="visual-contract-list">
            {slides.map((slide, index) => {
              const slideId = String(slide.slide_id || `slide-${index + 1}`);
              const title = slide.neutral_title || `${slideId} 视觉合同`;
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
                  <header className="visual-slide-contract-head">
                    <div
                      className="visual-contract-page-id"
                      title={slideId}
                      aria-label={slideId}
                    >{String(index + 1).padStart(2, "0")}</div>
                    <div className="visual-contract-page-title">
                      <h3 id={titleId}>{title}</h3>
                      <p>
                        <span className="visual-contract-slide-key" title={slideId}>{slideId}</span>
                        <span>{String(slide.page_family || "页面家族待提供")} · 第 {String(slide.order || index + 1)} 页</span>
                      </p>
                    </div>
                  </header>
                  <div className="visual-contract-columns">
                    <section className="visual-contract-column">
                      <h4>冻结内容</h4>
                      {FROZEN_SLIDE_FIELD_ORDER.map((key) => field(
                        key, slideFieldValue(slide, key), labelFor(key, SLIDE_LABELS), { slideId, deckSectionId: "" },
                      ))}
                    </section>
                    <section className="visual-contract-column">
                      <h4>视觉实现合同</h4>
                      {VISUAL_SLIDE_FIELD_ORDER.map((key) => field(
                        key, slideFieldValue(slide, key), labelFor(key, SLIDE_LABELS), { slideId, deckSectionId: "" },
                      ))}
                    </section>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </article>

      <ReviewOverlayDrawer open={drawer === "outline"} title="视觉合同目录" side="left" onClose={() => setDrawer(null)}>
        <nav className="visual-contract-outline" aria-label="视觉合同章节定位">
          <p className="visual-contract-outline-group">整套合同</p>
          <button type="button" data-index="00" onClick={() => navigateFromOutline(() => visualBriefRef.current)}>Visual Brief</button>
          <button type="button" data-index="01" onClick={() => navigateFromOutline(() => designSystemRef.current)}>Deck Design System</button>
          <button type="button" data-index="A" onClick={() => navigateFromOutline(() => anchorIdentityRef.current)}>Anchor Slide Evidence</button>
          <p className="visual-contract-outline-group">{slides.length} 页页面合同</p>
          {slides.map((slide) => <button type="button" data-index={String(slide.slide_id)} key={String(slide.slide_id)} onClick={() => navigateFromOutline(() => slideRefs.current.get(String(slide.slide_id)))}>{slide.neutral_title || "视觉合同"}</button>)}
        </nav>
      </ReviewOverlayDrawer>
      <ReviewOverlayDrawer open={drawer === "marks"} title="合同标记" side="right" onClose={closeMarks}>
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

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { ProjectAssetImage } from "../components/ProjectAssetImage";
import type {
  AnchorFeedbackComposerState,
  AnchorFeedbackDraftState,
} from "../review-draft/reviewDraftStore";
import type { HostBridge } from "../types/host";
import type { NormalizedRegion } from "../types/visual-review";
import { isValidNormalizedRegion } from "./normalized-region";

interface Props {
  bridge: HostBridge;
  projectRoot: string;
  slideId: string;
  assetRef: string;
  drafts: AnchorFeedbackDraftState[];
  composer: AnchorFeedbackComposerState | null;
  disabled: boolean;
  toolbarActions?: ReactNode;
  onSliceChange: (
    drafts: AnchorFeedbackDraftState[],
    composer: AnchorFeedbackComposerState | null,
  ) => void;
}

interface DragState {
  pointerId: number;
  startX: number;
  startY: number;
  region: NormalizedRegion;
}

type ImageStatus = "loading" | "ready" | "unavailable";

function clamp(value: number) {
  return Math.min(1, Math.max(0, value));
}

function regionFromPoints(element: HTMLElement, startX: number, startY: number, endX: number, endY: number): NormalizedRegion | null {
  const rect = element.getBoundingClientRect();
  if (![rect.left, rect.top, rect.width, rect.height].every(Number.isFinite) || rect.width <= 0 || rect.height <= 0) {
    return null;
  }
  const width = rect.width;
  const height = rect.height;
  const x1 = clamp((startX - rect.left) / width);
  const y1 = clamp((startY - rect.top) / height);
  const x2 = clamp((endX - rect.left) / width);
  const y2 = clamp((endY - rect.top) / height);
  return {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    width: Math.abs(x2 - x1),
    height: Math.abs(y2 - y1),
  };
}

function regionStyle(region: NormalizedRegion) {
  return {
    left: `${region.x * 100}%`, top: `${region.y * 100}%`,
    width: `${region.width * 100}%`, height: `${region.height * 100}%`,
  };
}

export function RegionFeedbackEditor({
  bridge,
  projectRoot,
  slideId,
  assetRef,
  drafts,
  composer,
  disabled,
  toolbarActions,
  onSliceChange,
}: Props) {
  const [annotationMode, setAnnotationMode] = useState(false);
  const [dragPreview, setDragPreview] = useState<NormalizedRegion | null>(null);
  const [message, setMessage] = useState("拖动框选需要反馈的范围；单点不会生成标注。");
  const [imageStatus, setImageStatus] = useState<ImageStatus>("loading");
  const drag = useRef<DragState | null>(null);
  const activeComposer = composer?.anchor_slide_id === slideId ? composer : null;
  const candidate = activeComposer?.candidate_region ?? null;
  const editingId = activeComposer?.editing_feedback_id ?? "";
  const comment = activeComposer?.comment ?? "";
  const slideDrafts = drafts.filter((item) => item.anchor_slide_id === slideId);
  const hasPersistedComposer = composer !== null;

  useEffect(() => {
    setAnnotationMode(false);
    drag.current = null;
    setDragPreview(null);
    setMessage("拖动框选需要反馈的范围；单点不会生成标注。");
  }, [slideId]);

  useEffect(() => {
    setImageStatus("loading");
  }, [assetRef, slideId]);

  const handleImageReady = useCallback(() => {
    setImageStatus("ready");
  }, []);

  const handleImageUnavailable = useCallback(() => {
    setImageStatus("unavailable");
    setAnnotationMode(false);
    drag.current = null;
    setDragPreview(null);
  }, []);

  const begin = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!annotationMode || disabled || imageStatus !== "ready" || hasPersistedComposer || event.button !== 0 || event.isPrimary === false) return;
    const region = regionFromPoints(event.currentTarget, event.clientX, event.clientY, event.clientX, event.clientY);
    if (!region) {
      setMessage("当前预览尺寸不可用，无法开始框选。");
      return;
    }
    drag.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, region };
    setDragPreview(region);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  };

  const move = (event: React.PointerEvent<HTMLDivElement>) => {
    const current = drag.current;
    if (imageStatus !== "ready" || !current || current.pointerId !== event.pointerId) return;
    const region = regionFromPoints(event.currentTarget, current.startX, current.startY, event.clientX, event.clientY);
    if (!region) {
      drag.current = null;
      setDragPreview(null);
      return;
    }
    current.region = region;
    setDragPreview(region);
    event.preventDefault();
  };

  const finish = (event: React.PointerEvent<HTMLDivElement>) => {
    const current = drag.current;
    if (imageStatus !== "ready" || !current || current.pointerId !== event.pointerId) return;
    if (hasPersistedComposer) {
      drag.current = null;
      setDragPreview(null);
      if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
        event.currentTarget.releasePointerCapture?.(event.pointerId);
      }
      setAnnotationMode(false);
      return;
    }
    const region = regionFromPoints(event.currentTarget, current.startX, current.startY, event.clientX, event.clientY);
    drag.current = null;
    setDragPreview(null);
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
    }
    setAnnotationMode(false);
    if (!isValidNormalizedRegion(region)) {
      setMessage("框选范围过小，未生成标注；请拖出一个可感知区域。");
      return;
    }
    onSliceChange(drafts, {
      anchor_slide_id: slideId,
      candidate_region: region,
      editing_feedback_id: "",
      comment: "",
    });
    setMessage(`${slideId} 框选区域已定位，请在幻灯片下方输入意见。`);
  };

  const save = () => {
    if (disabled || imageStatus !== "ready" || !isValidNormalizedRegion(candidate) || !comment.trim()) return;
    const next = editingId
      ? drafts.map((item) => item.feedback_id === editingId
          ? { ...item, normalized_region: candidate, comment: comment.trim() }
          : item)
      : [...drafts, {
          feedback_id: globalThis.crypto?.randomUUID?.() || `feedback-${Date.now()}`,
          anchor_slide_id: slideId,
          normalized_region: candidate,
          comment: comment.trim(),
          created_at: new Date().toISOString(),
        }];
    onSliceChange(next, null);
    setMessage("本条意见已加入本轮反馈；可继续跨页框选。 ");
  };

  const discard = () => {
    if (disabled) return;
    onSliceChange(drafts, null);
    setMessage("当前未加入的反馈已放弃。");
  };

  const edit = (draft: AnchorFeedbackDraftState) => {
    if (disabled || imageStatus !== "ready" || hasPersistedComposer || !isValidNormalizedRegion(draft.normalized_region)) return;
    setAnnotationMode(false);
    drag.current = null;
    setDragPreview(null);
    onSliceChange(drafts, {
      anchor_slide_id: slideId,
      candidate_region: { ...draft.normalized_region },
      editing_feedback_id: draft.feedback_id,
      comment: draft.comment,
    });
    setMessage(`${slideId} 已定位到现有框选区域。`);
  };

  const cancelDrag = () => {
    drag.current = null;
    setDragPreview(null);
  };

  return (
    <section className="region-feedback-editor" aria-label={`${slideId} 区域反馈`}>
      <div className="anchor-toolbar">
        <div><strong>{slideId}</strong><span>拖动形成矩形范围</span></div>
        <div className="anchor-toolbar-actions">
          {toolbarActions}
          <button
            type="button"
            className={annotationMode ? "active" : ""}
            disabled={disabled || imageStatus !== "ready" || hasPersistedComposer}
            onClick={() => {
              if (disabled || imageStatus !== "ready" || hasPersistedComposer) return;
              setAnnotationMode((value) => !value);
            }}
          >{annotationMode ? "取消标注" : "开始标注"}</button>
        </div>
      </div>
      <div
        className={`anchor-canvas${annotationMode ? " annotating" : ""}`}
        data-testid="anchor-canvas"
        onPointerDown={begin}
        onPointerMove={move}
        onPointerUp={finish}
        onPointerCancel={cancelDrag}
        onLostPointerCapture={cancelDrag}
      >
        <ProjectAssetImage
          bridge={bridge}
          projectRoot={projectRoot}
          assetRef={assetRef}
          alt={`${slideId} 锚点页成果`}
          onReady={handleImageReady}
          onUnavailable={handleImageUnavailable}
        />
        {slideDrafts.map((draft, index) => (
          <button
            type="button"
            className={`anchor-region saved${editingId === draft.feedback_id ? " active" : ""}`}
            style={regionStyle(draft.normalized_region)}
            key={draft.feedback_id}
            aria-label={`${slideId} 已标注区域 ${index + 1}`}
            disabled={disabled || imageStatus !== "ready" || hasPersistedComposer}
            onPointerDown={(event) => event.stopPropagation()}
            onClick={() => edit(draft)}
          ><span>{drafts.indexOf(draft) + 1}</span></button>
        ))}
        {candidate || dragPreview ? <div className="anchor-region candidate" style={regionStyle(candidate || dragPreview!)}><span>{editingId ? drafts.findIndex((item) => item.feedback_id === editingId) + 1 : drafts.length + 1}</span></div> : null}
      </div>
      {candidate ? (
        <div className="anchor-feedback-composer">
          <label>
            <span>{slideId} · 当前框选区域反馈</span>
            <textarea
              autoFocus
              aria-label="当前框选区域反馈"
              value={comment}
              disabled={disabled || imageStatus !== "ready"}
              onChange={(event) => activeComposer && onSliceChange(drafts, {
                ...activeComposer,
                comment: event.target.value,
              })}
            />
          </label>
          <div>
            <button type="button" disabled={disabled || imageStatus !== "ready" || !comment.trim()} onClick={save}>{editingId ? "更新本条反馈" : "加入本轮反馈"}</button>
            <button type="button" disabled={disabled} onClick={discard}>放弃当前输入</button>
          </div>
        </div>
      ) : null}
      <p className="region-editor-message" role="status">
        {imageStatus === "loading"
          ? "预览加载完成后可标注。"
          : imageStatus === "unavailable"
            ? "预览加载失败，请重试后再标注。"
            : message}
      </p>
    </section>
  );
}

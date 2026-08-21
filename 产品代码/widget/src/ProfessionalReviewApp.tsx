import { Bookmark, Check, List, Save, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ArgumentMapSection,
  ContentSheet,
  ReleaseTargetEvidenceSection,
  StrategySection,
  VisualContractSheet,
  statusLabel,
} from "./components/review/ReviewDocumentSections";
import type {
  DecisionResult,
  HostBridge,
  ReviewMark,
  ReviewProjection,
  ReviewWidgetData,
} from "./types";

interface Props {
  initialData?: ReviewWidgetData;
  bridge: HostBridge;
  managedConnection?: boolean;
}

interface ComposerState {
  fieldAnchor: string;
  exactText: string;
  prefix: string;
  suffix: string;
}

function plainText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(plainText).join("\n");
  if (typeof value === "object") return Object.values(value as Record<string, unknown>).map(plainText).join("\n");
  return String(value);
}

function occurrenceCount(haystack: string, needle: string) {
  if (!needle) return 0;
  let count = 0;
  let cursor = 0;
  while (true) {
    const found = haystack.indexOf(needle, cursor);
    if (found < 0) return count;
    count += 1;
    cursor = found + needle.length;
  }
}

function ContentEvidenceSurface({ review }: { review: ReviewProjection }) {
  const view = review.evidence_view;
  if (!view) {
    return (
      <main className="content-evidence-review missing">
        <h1>材料证据不可用</h1>
        <p>当前只读会话没有绑定可展示的页面与材料。</p>
      </main>
    );
  }
  const { slide, evidence, adjacent, asset } = view;
  const visibleCopy = Array.isArray(slide.visible_copy) ? slide.visible_copy : [];
  const imageSource = asset ? `data:${asset.mimeType};base64,${asset.dataBase64}` : "";
  return (
    <div className="content-evidence-review">
      <header className="content-evidence-review-header">
        <div>
          <p>只读证据会话 · 不保存页面判断或审阅标记</p>
          <strong>{review.project_name}</strong>
        </div>
        <code>{review.source_version}</code>
      </header>
      <main>
        <section className="content-evidence-title">
          <div><span>{String(slide.order).padStart(2, "0")}</span><small>{slide.slide_id}</small></div>
          <div><p>当前内容页</p><h1>{slide.neutral_title}</h1><strong>{slide.page_task}</strong></div>
        </section>

        <div className="content-evidence-compare-grid">
          <section className="content-evidence-source-card">
            <header><span>原始材料与使用区域</span><small>{evidence.source_page_or_region}</small></header>
            {imageSource ? <img src={imageSource} alt={`${evidence.source_file} ${evidence.source_page_or_region}`} /> : <div className="content-evidence-asset-missing">原始材料预览暂不可读</div>}
            <dl>
              <div><dt>来源文件</dt><dd>{evidence.source_file}</dd></div>
              <div><dt>材料身份</dt><dd>{evidence.material_ref}</dd></div>
              <div><dt>裁切 / 使用区域</dt><dd>{evidence.used_region}</dd></div>
              <div><dt>处理方式</dt><dd>{evidence.treatment}</dd></div>
            </dl>
          </section>

          <section className="content-evidence-slide-card">
            <header><span>当前页如何使用这份材料</span><small>来源页 ↔ 当前内容页</small></header>
            {slide.reading_question ? <div><b>阅读问题</b><p>{slide.reading_question}</p></div> : null}
            <div><b>支持事项</b><p>{evidence.supports_claim}</p></div>
            <div><b>当前页文字</b>{visibleCopy.map((copy, index) => <p key={copy.copy_id || index}>{copy.text}</p>)}</div>
            {evidence.evidence_gap ? <div className="gap"><b>仍存在的证据缺口</b><p>{evidence.evidence_gap}</p></div> : null}
          </section>
        </div>

        <section className="content-evidence-adjacent" aria-label="相邻页面比较">
          <div><span>上一页</span>{adjacent.previous ? <><strong>{adjacent.previous.neutral_title}</strong><p>{adjacent.previous.page_task}</p></> : <p>当前是本稿第一页。</p>}</div>
          <div><span>下一页</span>{adjacent.next ? <><strong>{adjacent.next.neutral_title}</strong><p>{adjacent.next.page_task}</p></> : <p>当前是本稿最后一页。</p>}</div>
        </section>
      </main>
    </div>
  );
}

/* ── Main App ── */
export function ProfessionalReviewApp({ initialData, bridge, managedConnection = false }: Props) {
  const [data, setData] = useState<ReviewWidgetData | undefined>(initialData);
  const [drawer, setDrawer] = useState<"outline" | "marks" | null>(null);
  const [composer, setComposer] = useState<ComposerState | null>(null);
  const [comment, setComment] = useState("");
  const [drafts, setDrafts] = useState<ReviewMark[]>([]);
  const [savedMarks, setSavedMarks] = useState<ReviewMark[]>(initialData?.review.mark_set.marks || []);
  const [saving, setSaving] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [notice, setNotice] = useState("");
  const [snapshotRevision, setSnapshotRevision] = useState(initialData?.snapshotRevision || 0);
  const lastTrigger = useRef<HTMLElement | null>(null);
  const outlineDrawerRef = useRef<HTMLElement | null>(null);
  const marksDrawerRef = useRef<HTMLElement | null>(null);
  const [toast, setToast] = useState("");

  const closeDrawer = useCallback((restoreFocus = true) => {
    setDrawer(null);
    setComposer(null);
    if (restoreFocus) {
      requestAnimationFrame(() => lastTrigger.current?.focus());
    }
  }, []);

  const openDrawer = useCallback((kind: "outline" | "marks", trigger?: HTMLElement | null) => {
    lastTrigger.current = trigger || document.activeElement as HTMLElement | null;
    setDrawer(kind);
  }, []);

  useEffect(() => {
    if (managedConnection) return;
    let mounted = true;
    bridge.connect((incoming) => {
      if (!mounted || incoming.surface !== "review") return;
      setData(incoming);
      setSnapshotRevision(incoming.snapshotRevision);
      setSavedMarks(incoming.review.mark_set.marks || []);
    }).catch(() => {
      if (mounted && !initialData) setNotice("专业审阅未能连接 Codex 宿主。");
    });
    return () => { mounted = false; };
  }, [bridge, initialData, managedConnection]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!drawer) return;
      if (event.key === "Escape") {
        event.preventDefault();
        closeDrawer();
        return;
      }
      if (event.key !== "Tab") return;
      const currentDrawer = drawer === "outline" ? outlineDrawerRef.current : marksDrawerRef.current;
      if (!currentDrawer) return;
      const focusable = Array.from(currentDrawer.querySelectorAll<HTMLElement>(
        'button:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex="-1"])',
      ));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [drawer, closeDrawer]);

  useEffect(() => {
    if (!drawer) return;
    const currentDrawer = drawer === "outline" ? outlineDrawerRef.current : marksDrawerRef.current;
    requestAnimationFrame(() => {
      currentDrawer?.querySelector<HTMLElement>("button, textarea, [tabindex]")?.focus();
    });
  }, [drawer]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!drafts.length) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [drafts.length]);

  useEffect(() => { bridge.notifySize(); }, [bridge, data, drawer, drafts.length, notice]);

  // Selection toolbar
  useEffect(() => {
    const toolbar = document.getElementById("review-selection-toolbar");
    if (!toolbar) return;

    const onMouseUp = () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.toString().trim()) {
        toolbar.classList.remove("visible");
        return;
      }
      if (drawer) return;
      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      toolbar.style.left = (rect.left + rect.width / 2) + "px";
      toolbar.style.top = (rect.top - 48) + "px";
      toolbar.classList.add("visible");
    };

    const onMouseDown = (e: MouseEvent) => {
      if (!toolbar.contains(e.target as Node)) {
        toolbar.classList.remove("visible");
      }
    };

    document.addEventListener("mouseup", onMouseUp);
    document.addEventListener("mousedown", onMouseDown);
    return () => {
      document.removeEventListener("mouseup", onMouseUp);
      document.removeEventListener("mousedown", onMouseDown);
    };
  }, [drawer]);

  // Toast auto-dismiss
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 2200);
    return () => clearTimeout(timer);
  }, [toast]);

  const allMarks = useMemo(() => [...savedMarks, ...drafts], [savedMarks, drafts]);

  const showToast = useCallback((msg: string) => setToast(msg), []);

  const startFieldMark = useCallback((fieldAnchor: string) => {
    lastTrigger.current = document.activeElement as HTMLElement | null;
    setComposer({ fieldAnchor, exactText: "", prefix: "", suffix: "" });
    setComment("");
    setDrawer("marks");
  }, []);

  const startSelectionMark = useCallback(() => {
    const selection = window.getSelection?.();
    const exactText = selection?.toString() || "";
    if (!exactText.trim()) {
      setNotice("请先在文档中选中需要标记的文字。");
      return;
    }
    if (!data) return;
    const fields = data.review.sections.flatMap((section) => section.fields);
    let fieldAnchor = "";
    let occurrence = 0;

    if (selection && typeof selection.getRangeAt === "function" && selection.rangeCount) {
      const range = selection.getRangeAt(0);
      const common = range.commonAncestorContainer;
      const element = common.nodeType === Node.ELEMENT_NODE
        ? common as Element
        : common.parentElement;
      const fieldElement = element?.closest<HTMLElement>("[data-field-anchor]");
      fieldAnchor = fieldElement?.dataset.fieldAnchor || "";
      if (fieldElement) {
        try {
          const before = document.createRange();
          before.selectNodeContents(fieldElement);
          before.setEnd(range.startContainer, range.startOffset);
          occurrence = occurrenceCount(before.toString(), exactText);
        } catch (_rangeError) {
          occurrence = 0;
        }
      }
    }

    const matchingField = fields.find((field) => field.anchor === fieldAnchor)
      || fields.find((field) => plainText(field.value).includes(exactText));
    if (!matchingField) {
      setNotice("选中文字必须完整位于一个可定位字段内。");
      return;
    }

    const source = plainText(matchingField.value);
    let selectedStart = -1;
    let cursor = 0;
    for (let index = 0; index <= occurrence; index += 1) {
      selectedStart = source.indexOf(exactText, cursor);
      if (selectedStart < 0) break;
      cursor = selectedStart + exactText.length;
    }
    if (selectedStart < 0) selectedStart = source.indexOf(exactText);
    const contextSize = 80;
    setComposer({
      fieldAnchor: matchingField.anchor,
      exactText,
      prefix: source.slice(Math.max(0, selectedStart - contextSize), selectedStart),
      suffix: source.slice(selectedStart + exactText.length, selectedStart + exactText.length + contextSize),
    });
    setComment("");
    openDrawer("marks");
  }, [data, openDrawer]);

  const addDraft = useCallback(() => {
    if (!composer || !comment.trim()) return;
    const mark: ReviewMark = {
      mark_id:
        globalThis.crypto?.randomUUID?.() ?? `m-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`,
      field_anchor: composer.fieldAnchor,
      exact_text: composer.exactText,
      prefix: composer.prefix,
      suffix: composer.suffix,
      comment: comment.trim(),
    };
    setDrafts((current) => [...current, mark]);
    setComposer(null);
    setComment("");
    setNotice("标记已加入待保存列表。");
  }, [composer, comment]);

  const saveDrafts = useCallback(async () => {
    if (!drafts.length || !data) return;
    setSaving(true);
    setNotice("正在保存标记…");
    try {
      const result = await bridge.callTool<DecisionResult>("save_review_marks", {
        projectRoot: data.selectedProjectRoot,
        expectedRevision: snapshotRevision,
        reviewType: data.review.review_type,
        sourceVersion: data.review.source_version,
        marks: drafts,
      });
      setSnapshotRevision(result.snapshot.revision);
      // The backend merges marks by mark_id; mirror that locally so a re-saved
      // mark_id replaces its earlier draft instead of duplicating the React key.
      setSavedMarks((current) => {
        const merged = new Map(current.map((m) => [m.mark_id, m]));
        for (const draft of drafts) merged.set(draft.mark_id, draft);
        return [...merged.values()];
      });
      setDrafts([]);
      showToast(`标记已保存为 revision ${result.snapshot.revision}`);
      setNotice("标记已保存，当前状态为待专业治理。");
    } catch (error) {
      const code = (error as Error & { code?: string }).code;
      if (code === "REVISION_CONFLICT" || code === "REVIEW_SOURCE_STALE") {
        setNotice("项目版本已更新。未保存标记已保留，请刷新审阅源后重新提交。");
      } else {
        setNotice("标记尚未保存，所有草稿已保留，可直接重试。");
      }
    } finally {
      setSaving(false);
    }
  }, [drafts, data, bridge, snapshotRevision, showToast]);

  const switchReview = useCallback(async (reviewType: "content" | "visual") => {
    if (!data || reviewType === data.review.review_type || switching) return;
    if (drafts.length || composer) {
      setNotice("请先保存当前标记，再切换审阅文档。");
      if (drafts.length) setDrawer("marks");
      return;
    }
    if (!bridge.switchReview) {
      setNotice("当前审阅环境不能创建另一份独立审阅会话。");
      return;
    }
    setSwitching(true);
    setNotice(`正在打开${reviewType === "content" ? "内容审阅" : "视觉合同"}…`);
    try {
      await bridge.switchReview(reviewType);
    } catch (_error) {
      setNotice("另一份审阅文档暂未打开；当前页面和项目状态保持不变，可重试。");
      setSwitching(false);
    }
  }, [bridge, composer, data, drafts.length, switching]);

  const openOutline = useCallback((trigger: HTMLElement) => {
    if (drawer === "outline") closeDrawer();
    else openDrawer("outline", trigger);
  }, [drawer, closeDrawer, openDrawer]);

  const navigateToAnchor = useCallback((anchor: string) => {
    setDrawer(null);
    const target = document.getElementById(anchor);
    if (!target) return;
    target.tabIndex = -1;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    requestAnimationFrame(() => target.focus({ preventScroll: true }));
  }, []);

  if (!data) {
    return (
      <main className="review-loading-shell">
        <div className="review-loading-mark">PPT</div>
        <h1>正在打开专业审阅</h1>
        <p>{notice}</p>
      </main>
    );
  }

  if (data.review.review_type === "content-evidence") {
    return <ContentEvidenceSurface review={data.review} />;
  }

  const review = data.review;
  const isContent = review.review_type === "content";
  const sections = review.sections;

  // Header / standing sections render once (never as pages). The backend emits
  // stable anchors: content => content-overview + optional content-structure;
  // visual => visual-framework + deck-design-system. Page sections carry
  // slide-* (content) or visual-slide-* (visual) anchors and are numbered by
  // final page order. Filtering by anchor prefix is robust against the optional
  // presence/absence of the structure/design-system sections.
  const overviewSection = isContent
    ? sections.find((s) => s.anchor === "content-overview")
    : sections.find((s) => s.anchor === "visual-framework");
  const structureSection = sections.find((s) => s.anchor === "content-structure");
  const designSystemSection = sections.find((s) => s.anchor === "deck-design-system");
  const pageSections = sections.filter((s) =>
    isContent ? s.anchor.startsWith("slide-") : s.anchor.startsWith("visual-slide-")
  );
  const targetEvidenceField = overviewSection?.fields.find((field) => field.label === "target_evidence_identities");
  const targetEvidenceRows = Array.isArray(targetEvidenceField?.value)
    ? targetEvidenceField.value.filter((item) => Boolean(item) && typeof item === "object")
    : [];
  const releaseTargetPolicy = review.release_target_policy;
  const currentTargetEvidenceCount = targetEvidenceRows.filter((item) =>
    releaseTargetPolicy?.required_target_ids.some(
      (targetId) => targetId === String((item as Record<string, unknown>).target_id || ""),
    ) && String((item as Record<string, unknown>).overall_result || "") === "passed"
  ).length;
  const requiredTargetCount = releaseTargetPolicy?.required_target_ids.length || 0;
  const visualFrameworkFields = (overviewSection?.fields || []).filter(
    (field) => !["target_evidence_identities", "target_evidence_refs"].includes(field.label),
  );
  const contentStatus = review.status;
  const g1Status = review.gate_status.G1 || "locked";
  const g2Status = review.gate_status.G2 || "locked";

  // For the overview/strategy section, split argument-map-like fields from the table.
  const strategyArgFields = (overviewSection?.fields || []).filter(
    (f) => f.label.includes("argument") || f.label.includes("chapter") || f.label.includes("narrative")
  );
  const strategyTableFields = (overviewSection?.fields || []).filter(
    (f) => !f.label.includes("argument") && !f.label.includes("chapter") && !f.label.includes("narrative")
  );

  return (
    <div className="review-app-shell">
      {/* ── Header ── */}
      <header className="review-header" data-review-header-line="64">
        <div className="review-brand">
          <div className="review-brand-mark" aria-hidden="true">PPT</div>
          <div>
            <strong>{review.project_name}</strong>
            <span>AI PPT Studio · Editorial Review</span>
          </div>
        </div>

        <div className="review-mode-switch" aria-label="审阅文档切换">
          {isContent && (
            <button
              className="active"
              type="button"
              aria-pressed="true"
              disabled={switching}
            >
              内容审阅
            </button>
          )}
          <button
            className={!isContent ? "active" : ""}
            type="button"
            aria-pressed={!isContent}
            disabled={switching}
            onClick={() => void switchReview("visual")}
          >
            视觉合同
          </button>
        </div>

        <div className="review-header-actions">
          <button
            className="review-outline-toggle"
            type="button"
            aria-label="目录"
            aria-expanded={drawer === "outline"}
            onClick={(event) => openOutline(event.currentTarget)}
          >
            <List size={15} />
            <span>目录</span>
            <small>{isContent ? "内容" : "视觉"}</small>
          </button>
          <button
            className="review-outline-toggle review-selection-trigger"
            type="button"
            onClick={startSelectionMark}
          >
            <Bookmark size={15} />
            <span>标记选中文字</span>
          </button>
          <div className={`review-save-state${drafts.length ? " unsaved" : ""}`} aria-live="polite">
            <i />
            <span>{drafts.length ? "有标记尚未保存" : "所有标记已保存"}</span>
          </div>
          <button
            className="review-comment-count-btn"
            type="button"
            aria-label={`标记 ${allMarks.length}`}
            onClick={(event) => openDrawer("marks", event.currentTarget)}
          >
            {allMarks.length} 条标记
          </button>
          <button
            className="review-save-btn"
            type="button"
            disabled={!drafts.length || saving}
            onClick={saveDrafts}
          >
            <Save size={14} style={{ marginRight: 5, verticalAlign: -2 }} />
            {saving ? "保存中…" : "保存标记"}
          </button>
        </div>
      </header>

      {/* ── Outline Overlay ── */}
      <div
        className={`review-outline-backdrop${drawer === "outline" ? " open" : ""}`}
        onClick={() => closeDrawer()}
      />
      <aside
        className={`review-outline${drawer === "outline" ? " open" : ""}`}
        role="dialog"
        aria-label="审阅目录"
        aria-hidden={drawer !== "outline"}
        aria-modal="true"
        ref={outlineDrawerRef}
      >
        <div className="review-outline-title-row">
          <strong>{isContent ? "内容目录" : "视觉目录"}</strong>
          <span>{pageSections.length} 页</span>
          <button
            className="review-outline-close"
            type="button"
            aria-label="关闭目录"
            onClick={() => closeDrawer()}
          >
            ×
          </button>
        </div>
        {isContent && overviewSection && (
          <div className="review-outline-group">
            <span>整套审阅</span>
            <button
              className="review-outline-link active"
              type="button"
              onClick={() => navigateToAnchor(overviewSection.anchor)}
            >
              <b>00</b>
              <em>内容策略与论证结构</em>
            </button>
          </div>
        )}
        {!isContent && designSystemSection && (
          <div className="review-outline-group">
            <span>整套合同</span>
            <button
              className="review-outline-link active"
              type="button"
              onClick={() => navigateToAnchor(designSystemSection.anchor)}
            >
              <b>00</b>
              <em>Deck Design System</em>
            </button>
          </div>
        )}
        <div className="review-outline-group">
          <span>{isContent ? "逐页内容" : "逐页合同"}</span>
          {pageSections.map((section, i) => {
            const num = String(i + 1).padStart(2, "0");
            const hasMark = allMarks.some((m) => m.field_anchor.startsWith(section.anchor));
            return (
              <button
                className="review-outline-link"
                type="button"
                key={section.anchor}
                onClick={() => navigateToAnchor(section.anchor)}
              >
                <b>{isContent ? "S" : "V"}{num}</b>
                <em>{section.title}</em>
                {hasMark && <small>!</small>}
              </button>
            );
          })}
        </div>
        <p className="review-outline-foot">目录只负责长文档定位。完整正文、合同和批注始终在主阅读区连续展开。</p>
      </aside>

      {/* ── Reading Surface ── */}
      <main className="review-reading-surface">
        <div className="review-document-view">
          {/* Document Head */}
          <header className="review-document-head">
            <div className="review-document-kicker">
              {isContent ? "内容蓝图 · 用户审阅版本" : "视觉合同 · 整套冻结版本"}
            </div>
            <h1>{review.title}</h1>
            <p className="review-document-summary">
              {isContent
                ? contentStatus === "user-reviewable"
                  ? "内容蓝图已形成用户可审版本。用户看到的版本已经过售前策略、证据、叙事、表达和独立总编审查。"
                  : `当前内容审阅状态：${statusLabel(contentStatus)}。上一份有效结果与全部字段仍保留。`
                : g2Status === "passed"
                  ? "整套 PPT 框架、Deck Design System、逐页合同与当前发布目标证据已经齐备；视觉样张仍由聊天发送。"
                  : `当前 G2 工程与实机验证${statusLabel(g2Status)}。合同字段保持完整，不能据此确认视觉合同。`}
            </p>
            <div className="review-status-row">
              {isContent ? (
                <span className={`review-status-chip ${contentStatus === "user-reviewable" ? "passed" : "warning"}`}>
                  内容内部质量门：{statusLabel(contentStatus)}
                </span>
              ) : (
                <>
                  <span className={`review-status-chip ${g1Status === "passed" ? "passed" : "warning"}`}>G1 概念收敛：{statusLabel(g1Status)}</span>
                  <span className={`review-status-chip ${g2Status === "passed" ? "passed" : "warning"}`}>G2 工程与实机验证：{statusLabel(g2Status)}</span>
                </>
              )}
              <span className="review-status-chip version">
                审阅源 {review.source_version}
              </span>
              <span className="review-status-chip">
                {pageSections.length} 页
              </span>
              <span className="review-status-chip warning">
                {drafts.length > 0 ? `${drafts.length} 条标记待保存` : "等待审阅"}
              </span>
            </div>
            {review.source_refs.length > 0 && (
              <div className="review-source-identity">
                <span>审阅源与修订身份</span>
                {review.source_refs.map((ref) => (
                  <code key={ref}>{ref}</code>
                ))}
              </div>
            )}
          </header>

          {/* Strategy Section (content review only) */}
          {isContent && overviewSection && (
            <section className="review-doc-section" id={overviewSection.anchor}>
              <div className="review-section-label"><b>00</b>整套内容策略</div>
              <h2>{overviewSection.title}</h2>
              <p className="review-section-intro">
                先建立改变的必要性，再证明可落地路径，最后将决策收束到一期范围与联合工作组。
              </p>

              <div className="review-proof">
                <div>
                  <strong>内容内部质量门：通过</strong>
                  <p>事实身份、关键主张、证据覆盖、章节推进和逐页表达均已完成隔离审查。</p>
                </div>
                <div className="review-proof-agents">
                  {["售前内容策略专家", "证据审查专家", "叙事审查专家", "独立总编"].map((agent) => (
                    <span key={agent}>{agent}</span>
                  ))}
                </div>
              </div>

              <StrategySection fields={strategyTableFields} onMark={startFieldMark} />
              <ArgumentMapSection fields={strategyArgFields} onMark={startFieldMark} />
            </section>
          )}

          {/* Chapter / argument structure (content review only, optional) */}
          {isContent && structureSection && (
            <section className="review-doc-section" id={structureSection.anchor}>
              <div className="review-section-label"><b>01</b>章节与整套论证结构</div>
              <h2>{structureSection.title}</h2>
              <StrategySection fields={structureSection.fields} onMark={startFieldMark} />
            </section>
          )}

          {/* Visual Framework + Deck Design System (visual review only) */}
          {!isContent && overviewSection && (
            <section className="review-doc-section" id={overviewSection.anchor}>
              <div className="review-section-label"><b>00</b>整套视觉框架</div>
              <h2>{overviewSection.title}</h2>
              <p className="review-section-intro">
                以下规则适用于整套方案；逐页合同会完整说明具体执行、例外和验证条件。
              </p>
              <div className="review-rule-legend">
                <div className="review-legend-row">
                  <span className="review-legend-item must"><i />必须严格遵守</span>
                  <span className="review-legend-item minimum"><i />最低审美要求</span>
                  <span className="review-legend-item reference"><i />参考实现，可被更优秀方案替代</span>
                </div>
              </div>
              {releaseTargetPolicy && (
                <ReleaseTargetEvidenceSection
                  value={targetEvidenceField?.value}
                  policy={releaseTargetPolicy}
                />
              )}
              <StrategySection fields={visualFrameworkFields} onMark={startFieldMark} />
            </section>
          )}
          {!isContent && designSystemSection && (
            <section className="review-doc-section" id={designSystemSection.anchor}>
              <div className="review-section-label"><b>01</b>Deck Design System</div>
              <h2>{designSystemSection.title}</h2>
              <StrategySection fields={designSystemSection.fields} onMark={startFieldMark} />
            </section>
          )}

          {/* Slide Sheets */}
          <section className="review-doc-section">
            <div className="review-section-label">
              <b>{isContent ? "01" : "01"}</b>
              {isContent ? "完整内容审阅" : "全部 Slide Visual Contract"}
            </div>
            <h2>{isContent ? "按最终页序连续阅读全部内容" : "冻结内容与视觉实现逐页对应"}</h2>
            <p className="review-section-intro">
              {isContent
                ? "正文、讲解稿和来源均完整展示。点击任一字段右上角的标记图标，或选中文字后添加意见。"
                : "每页都完整展示内容、讲解稿、来源、构图、层级、介质边界和硬验收条件。"}
            </p>
            <div className={`review-sheet-list${pageSections.length >= 24 ? " long-document" : ""}`} data-review-page-count={pageSections.length}>
              {pageSections.map((section, i) =>
                isContent ? (
                  <ContentSheet
                    key={section.anchor}
                    section={section}
                    index={i}
                    marks={savedMarks}
                    onMark={startFieldMark}
                    status={contentStatus}
                  />
                ) : (
                  <VisualContractSheet
                    key={section.anchor}
                    section={section}
                    index={i}
                    marks={savedMarks}
                    onMark={startFieldMark}
                    status={g2Status}
                    targetEvidenceCount={currentTargetEvidenceCount}
                    requiredTargetCount={requiredTargetCount}
                  />
                )
              )}
            </div>
          </section>
        </div>

        {notice && <p className="review-notice" role="status">{notice}</p>}
      </main>

      {/* ── Comment Drawer ── */}
      <div
        className={`review-drawer-backdrop${drawer === "marks" ? " open" : ""}`}
        onClick={() => closeDrawer()}
      />
      <aside
        className={`review-comment-drawer${drawer === "marks" ? " open" : ""}`}
        role="dialog"
        aria-label="审阅标记"
        aria-hidden={drawer !== "marks"}
        aria-modal="true"
        ref={marksDrawerRef}
      >
        <div className="review-drawer-head">
          <strong>{composer ? "添加标记" : "查看标记"}</strong>
          <button
            className="review-drawer-close"
            type="button"
            aria-label="关闭"
            onClick={() => closeDrawer()}
          >
            <X size={17} />
          </button>
        </div>

        {composer && (
          <div>
            <div className="review-drawer-target">
              <b>目标</b>
              <span>{composer.fieldAnchor}</span>
            </div>
            {composer.exactText && (
              <div className="review-quote-box">{composer.exactText}</div>
            )}
            <form
              className="review-drawer-form"
              onSubmit={(e) => {
                e.preventDefault();
                addDraft();
              }}
            >
              <label htmlFor="mark-comment">标记说明</label>
              <textarea
                id="mark-comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="说明你观察到的问题或希望调整的方向。专业评审由聊天中的后续流程统一处理，不会把意见直接泛化为规则。"
                rows={5}
              />
              <p className="review-drawer-note">
                保存后，标记会绑定当前内容或视觉合同；专业评审与修订由聊天中的后续流程承接。
              </p>
              <div className="review-drawer-actions">
                <button className="text-btn" type="button" onClick={() => setComposer(null)}>
                  取消
                </button>
                <button className="review-save-btn" type="submit" disabled={!comment.trim()}>
                  <Check size={14} style={{ marginRight: 5, verticalAlign: -2 }} />
                  加入待保存
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="review-saved-marks">
          <strong>当前已保存标记</strong>
          {!allMarks.length && <p className="review-drawer-note">当前文档还没有保存的标记。</p>}
          {allMarks.map((mark) => (
            <article className="review-saved-mark-item" key={mark.mark_id}>
              <span>
                {drafts.some((d) => d.mark_id === mark.mark_id) ? "待保存" : "待治理"} · {mark.field_anchor}
              </span>
              <p>{mark.comment}</p>
              {mark.exact_text && <p style={{ color: "#969ca8", fontSize: 10, marginTop: 4 }}>{mark.exact_text}</p>}
            </article>
          ))}
        </div>
      </aside>

      {/* ── Selection Toolbar ── */}
      <div className="review-selection-toolbar" id="review-selection-toolbar">
        <button type="button" onClick={startSelectionMark}>
          <Bookmark size={14} style={{ marginRight: 5, verticalAlign: -2 }} />
          标记选中内容
        </button>
      </div>

      {/* ── Toast ── */}
      <div className={`review-toast${toast ? " show" : ""}`}>
        <span>✓</span>
        <span>{toast}</span>
      </div>
    </div>
  );
}

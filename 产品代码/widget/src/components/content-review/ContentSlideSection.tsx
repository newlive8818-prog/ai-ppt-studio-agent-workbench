import { memo, useState } from "react";
import { ArrowDown, ArrowUp, ExternalLink, FileWarning, Link2, LoaderCircle } from "lucide-react";

import { ProjectAssetImage } from "../ProjectAssetImage";
import type { OpenedContentEvidenceBrowser } from "../../lib/content-review-client";
import type { HostBridge } from "../../types";
import type { ContentPageDecision, ContentReviewSlide } from "../../types/content-review";
import { PageDecisionEditor, type PageDecisionEditorMeta } from "./PageDecisionEditor";

interface Props {
  slide: ContentReviewSlide;
  bridge: HostBridge;
  projectRoot: string;
  onSaveDecision: (slideId: string, decision: ContentPageDecision, comment: string) => Promise<void>;
  onEditorMetaChange: (slideId: string, meta: PageDecisionEditorMeta) => void;
  onOpenEvidenceBrowser: (
    slideId: string,
    evidenceId: string,
    materialRef: string,
  ) => Promise<OpenedContentEvidenceBrowser>;
}

const ROLE_LABELS = new Map([
  ["lead", "导读"], ["headline", "页面主文"], ["body", "正文"],
  ["boundary", "边界说明"], ["source-note", "来源说明"],
]);

function valueLabel(value: unknown) {
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.join("、");
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value ?? "");
}

function ContentSlideSectionComponent({ slide, bridge, projectRoot, onSaveDecision, onEditorMetaChange, onOpenEvidenceBrowser }: Props) {
  const [openingEvidenceId, setOpeningEvidenceId] = useState("");
  const [evidenceNotice, setEvidenceNotice] = useState("");
  const [evidenceHandoffUrl, setEvidenceHandoffUrl] = useState("");

  async function openEvidence(evidenceId: string, materialRef: string) {
    if (openingEvidenceId) return;
    setOpeningEvidenceId(evidenceId);
    setEvidenceNotice("");
    setEvidenceHandoffUrl("");
    try {
      const result = await onOpenEvidenceBrowser(slide.slide_id, evidenceId, materialRef);
      if (result.opened) {
        setEvidenceNotice("原材料已在只读 Browser 中打开。");
      } else {
        setEvidenceNotice("只读证据会话已准备，请在 Browser 打开。");
        setEvidenceHandoffUrl(result.url || "");
      }
    } catch (_error) {
      setEvidenceNotice("原材料暂未打开；当前页面判断和未保存意见保持不变，可重试。");
    } finally {
      setOpeningEvidenceId("");
    }
  }
  return (
    <article className="content-slide-section page" id={`content-slide-${slide.slide_id}`} data-slide-id={slide.slide_id} data-content-slide={slide.slide_id} tabIndex={-1}>
      <header className="content-slide-header page-head">
        <div className="content-slide-number"><span>{String(slide.order).padStart(2, "0")}</span><small>{slide.slide_id}</small></div>
        <div className="content-slide-heading"><p>中立标题</p><h2>{slide.neutral_title}</h2></div>
      </header>

      <div className="content-slide-main content-slide-reading-grid page-body">
        <div className="content-slide-copy-column page-text">
          <section className="content-slide-intent purpose" aria-label="页面任务与阅读问题">
            <div><span>这一页的目标</span><p>{slide.page_task}</p></div>
            <div><span>阅读问题</span><p>{slide.reading_question}</p></div>
          </section>

          <section className="content-review-block visible-copy-block visible-copy">
            <header><span>页面实际文字</span><small>完整显示，不作摘要</small></header>
            <div className="visible-copy-list">{slide.visible_copy_blocks.map((block) => (
              <div key={block.block_id} className={`visible-copy-row role-${block.role}`}>
                <small>{ROLE_LABELS.get(block.role) || block.role}</small><p>{block.text}</p>
              </div>
            ))}</div>
          </section>

          <section className="content-review-block identity-block">
            <header><span>内容身份</span><small>事实、推断、建议与待验证分开</small></header>
            <div className="content-identity-labels">{slide.identity_labels.map((identity) => <span key={identity}>{identity}</span>)}</div>
            <div className="content-analysis-list">{slide.analysis_or_proposal_blocks.map((block) => (
              <div key={block.block_id}><strong>{block.identity}</strong><p>{block.text}</p></div>
            ))}</div>
          </section>

          <section className="content-review-block mapping-block">
            <header><span>问题—要求—方案映射</span><small>查看本页在整套方案中的作用</small></header>
            {slide.solution_mapping_refs.length ? <ul>{slide.solution_mapping_refs.map((item) => <li key={item}><Link2 size={14} />{item}</li>)}</ul>
              : <p className="content-empty-value">本页当前没有问题—方案映射。</p>}
          </section>
        </div>

        <aside className="content-slide-evidence-column" aria-label="本页材料证据">
          <section className="content-review-block evidence-block visual-evidence">
            <header><span>图片与材料</span><small>有多少展示多少；没有图片不构成缺失</small></header>
            {slide.evidence_bindings.map((binding) => (
              <article className={`content-evidence-item ${binding.source_refs.length ? "has-source" : "is-gap"}`} key={binding.binding_id}>
                {binding.asset_ref ? (
                  <figure>
                    <ProjectAssetImage
                      bridge={bridge}
                      projectRoot={projectRoot}
                      assetRef={binding.asset_ref}
                      alt={binding.caption || `${slide.slide_id} 材料 ${binding.binding_id}`}
                      className="content-evidence-image"
                    />
                    <figcaption>{binding.caption || binding.identity}</figcaption>
                  </figure>
                ) : null}
                <div className="content-evidence-gap-title"><FileWarning size={17} /><strong>{binding.source_refs.length ? binding.identity : "明确证据缺口"}</strong></div>
                <dl>
                  <div><dt>证据身份</dt><dd>{binding.identity}</dd></div>
                  <div><dt>来源位置</dt><dd>{binding.source_refs.length ? binding.source_refs.join("\n") : "当前未绑定可定位来源"}</dd></div>
                  <div><dt>用途 / 支持内容</dt><dd>{binding.supports_block_refs.join("、")}</dd></div>
                  <div><dt>证据标识</dt><dd>{binding.binding_id}</dd></div>
                </dl>
                {binding.material_ref ? (
                  <button
                    className="content-evidence-open-button"
                    type="button"
                    disabled={Boolean(openingEvidenceId)}
                    onClick={() => void openEvidence(binding.binding_id, binding.material_ref!)}
                  >
                    {openingEvidenceId === binding.binding_id ? <LoaderCircle size={14} /> : <ExternalLink size={14} />}
                    放大查看原材料
                  </button>
                ) : null}
                {!binding.source_refs.length ? <p className="content-evidence-gap"><strong>证据缺口</strong>本页对应内容只能保持为待联合验证，不得显示为来源事实。</p> : null}
              </article>
            ))}
            {evidenceNotice ? <p className="content-evidence-browser-notice" role="status">{evidenceNotice}</p> : null}
            {evidenceHandoffUrl ? (
              <a
                className="content-evidence-browser-handoff"
                href={evidenceHandoffUrl}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={14} />在 Browser 打开只读证据
              </a>
            ) : null}
            {slide.evidence_bindings.some((binding) => !binding.material_ref) ? <p className="content-evidence-browser-notice">没有类型化 material_ref 的绑定不提供“打开原材料”动作。</p> : null}
          </section>
        </aside>
      </div>

      <details className="full-script">
        <summary>完整逐字稿</summary>
        <div className="speaker-notes-block"><p>{slide.speaker_notes}</p></div>
      </details>

      <section className="content-slide-notes-grid quality" aria-label="阅读质量与相邻页面关系">
        <div className="reading-quality-block"><span>阅读质量与信息密度</span><dl>{Object.entries(slide.reading_quality).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{valueLabel(value)}</dd></div>)}</dl></div>
        <div className="content-slide-relations" aria-label="本页与前后页关系">
          <div><ArrowUp size={16} /><span>承接上一页</span><p>{slide.previous_relation}</p></div>
          <div><ArrowDown size={16} /><span>进入下一页</span><p>{slide.next_relation}</p></div>
        </div>
      </section>

      <PageDecisionEditor slideId={slide.slide_id} savedState={slide.decision_state} onSave={onSaveDecision} onMetaChange={onEditorMetaChange} />
    </article>
  );
}

export const ContentSlideSection = memo(ContentSlideSectionComponent);

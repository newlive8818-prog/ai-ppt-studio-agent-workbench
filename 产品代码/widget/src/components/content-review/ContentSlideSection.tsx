import { memo, useState } from "react";
import { ArrowDown, ArrowUp, ExternalLink, FileText, Image as ImageIcon, Link2, LoaderCircle } from "lucide-react";

import type { ContentPageDecision, ContentReviewSlide, HostBridge } from "../../types";
import { ProjectAssetImage } from "../ProjectAssetImage";
import { PageDecisionEditor, type PageDecisionEditorMeta } from "./PageDecisionEditor";

interface Props {
  slide: ContentReviewSlide;
  projectRoot: string;
  bridge: HostBridge;
  onSaveDecision: (slideId: string, decision: ContentPageDecision, comment: string) => Promise<void>;
  onEditorMetaChange: (slideId: string, meta: PageDecisionEditorMeta) => void;
  onOpenEvidenceBrowser: (slideId: string, evidenceId: string, materialRef: string) => Promise<void>;
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

function ContentSlideSectionComponent({ slide, projectRoot, bridge, onSaveDecision, onEditorMetaChange, onOpenEvidenceBrowser }: Props) {
  const [openingEvidenceId, setOpeningEvidenceId] = useState("");
  const [evidenceNotice, setEvidenceNotice] = useState("");

  async function openEvidence(evidenceId: string, materialRef: string) {
    if (openingEvidenceId) return;
    setOpeningEvidenceId(evidenceId);
    setEvidenceNotice("");
    try {
      await onOpenEvidenceBrowser(slide.slide_id, evidenceId, materialRef);
      setEvidenceNotice("原材料已在只读 Browser 中打开。");
    } catch (_error) {
      setEvidenceNotice("原材料暂未打开；当前页面判断和未保存意见保持不变，可重试。");
    } finally {
      setOpeningEvidenceId("");
    }
  }
  return (
    <article className="content-slide-section" id={`content-slide-${slide.slide_id}`} data-slide-id={slide.slide_id} tabIndex={-1}>
      <header className="content-slide-header">
        <div className="content-slide-number"><span>{String(slide.order).padStart(2, "0")}</span><small>{slide.slide_id}</small></div>
        <div className="content-slide-heading"><p>{slide.section_id}</p><h2>{slide.neutral_title}</h2></div>
      </header>

      <section className="content-slide-intent" aria-label="页面任务与阅读问题">
        <div><span>这一页的任务</span><p>{slide.page_task}</p></div>
        <div><span>阅读问题</span><p>{slide.reading_question}</p></div>
      </section>

      <div className="content-slide-main">
        <div className="content-slide-copy-column">
          <section className="content-review-block visible-copy-block">
            <header><span>页面实际文字</span><small>完整显示，不作摘要</small></header>
            <div className="visible-copy-list">{slide.visible_copy.map((block) => (
              <div key={block.copy_id} className={`visible-copy-row role-${block.role}`}>
                <small>{ROLE_LABELS.get(block.role) || block.role}</small><p>{block.text}</p>
              </div>
            ))}</div>
          </section>

          <section className="content-review-block identity-block">
            <header><span>内容身份</span><small>事实、推断、建议与待验证分开</small></header>
            <div className="content-identity-labels">{slide.identity_labels.map((identity) => <span key={identity}>{identity}</span>)}</div>
            <div className="content-analysis-list">{slide.analysis_or_proposal_blocks.map((block, index) => (
              <div key={`${block.identity}-${index}`}><strong>{block.identity}</strong><p>{block.text}</p></div>
            ))}</div>
          </section>

          <section className="content-review-block mapping-block">
            <header><span>问题—要求—方案映射</span><small>查看本页在整套方案中的作用</small></header>
            {slide.solution_mapping_refs.length ? <ul>{slide.solution_mapping_refs.map((item) => <li key={item}><Link2 size={14} />{item}</li>)}</ul>
              : <p className="content-empty-value">本页当前没有问题—方案映射。</p>}
          </section>
        </div>

        <aside className="content-slide-evidence-column" aria-label="本页图片与材料证据">
          <section className="content-review-block evidence-block">
            <header><span>图片与材料</span><small>直接查看本页使用的依据</small></header>
            {slide.evidence_items.length ? slide.evidence_items.map((evidence) => (
              <article className={`content-evidence-item ${evidence.asset_ref ? "has-asset" : "is-gap"}`} key={evidence.evidence_id}>
                {evidence.asset_ref ? <figure>
                  <ProjectAssetImage bridge={bridge} projectRoot={projectRoot} assetRef={evidence.asset_ref} alt={`${evidence.source_file} ${evidence.source_page_or_region}`} className="content-evidence-image" />
                  <figcaption><ImageIcon size={14} />{evidence.source_file}</figcaption>
                </figure> : <div className="content-evidence-gap-title"><FileText size={17} /><strong>明确证据缺口</strong></div>}
                <dl>
                  <div><dt>证据身份</dt><dd>{evidence.fact_identity}</dd></div>
                  <div><dt>来源文件</dt><dd>{evidence.source_file}</dd></div>
                  <div><dt>页码 / 区域</dt><dd>{evidence.source_page_or_region}</dd></div>
                  <div><dt>本页使用区域</dt><dd>{evidence.used_region}</dd></div>
                  <div><dt>用途 / 支持事项</dt><dd>{evidence.supports_claim}</dd></div>
                  <div><dt>处理方式</dt><dd>{evidence.treatment}</dd></div>
                </dl>
                {evidence.evidence_gap ? <p className="content-evidence-gap"><strong>证据缺口</strong>{evidence.evidence_gap}</p> : null}
                {evidence.asset_ref ? (
                  <button
                    className="content-evidence-open-button"
                    type="button"
                    disabled={Boolean(openingEvidenceId)}
                    onClick={() => void openEvidence(evidence.evidence_id, evidence.material_ref)}
                  >
                    {openingEvidenceId === evidence.evidence_id ? <LoaderCircle size={14} /> : <ExternalLink size={14} />}
                    放大查看原材料
                  </button>
                ) : null}
              </article>
            )) : <p className="content-empty-value">当前页没有绑定真实材料，也没有提供可审核的证据缺口。</p>}
            {evidenceNotice ? <p className="content-evidence-browser-notice" role="status">{evidenceNotice}</p> : null}
            {slide.source_refs.length ? <div className="content-source-refs"><strong>完整来源引用</strong>{slide.source_refs.map((ref) => <code key={ref}>{ref}</code>)}</div> : null}
          </section>
        </aside>
      </div>

      <section className="content-slide-notes-grid">
        <div className="speaker-notes-block"><span>完整逐字稿</span><p>{slide.speaker_notes}</p></div>
        <div className="reading-quality-block"><span>阅读质量与信息密度</span><dl>{Object.entries(slide.reading_quality).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{valueLabel(value)}</dd></div>)}</dl></div>
      </section>

      <section className="content-slide-relations" aria-label="本页与前后页关系">
        <div><ArrowUp size={16} /><span>承接上一页</span><p>{slide.previous_relation || "当前是本稿第一页。"}</p></div>
        <div><ArrowDown size={16} /><span>进入下一页</span><p>{slide.next_relation || "当前是本稿最后一页。"}</p></div>
      </section>

      <PageDecisionEditor slideId={slide.slide_id} savedState={slide.decision_state} onSave={onSaveDecision} onMetaChange={onEditorMetaChange} />
    </article>
  );
}

export const ContentSlideSection = memo(ContentSlideSectionComponent);

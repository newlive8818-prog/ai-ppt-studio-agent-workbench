import { useMemo, type ReactNode } from "react";

import type { ContentDecisionChoice } from "../types/content-review";
import type { HostBridge } from "../types/host";
import "../styles/content-review-view-model.css";
import type {
  ContentReviewDraftBlockViewModel,
  ContentReviewPageViewModel,
  ContentReviewSlideViewModel,
} from "./content-review-page-view-model";
import { ContentReviewMaterialVisuals } from "./ContentReviewMaterialVisuals";
import { PageDecisionControl } from "./PageDecisionControl";

export interface ContentReviewViewModelSurfaceProps {
  viewModel: ContentReviewPageViewModel;
  bridge: HostBridge;
  projectRoot: string;
  savingSlideId?: string | null;
  submitting?: boolean;
  pageMessage?: string;
  readsDisabled?: boolean;
  onDecisionChange: (slideId: string, decision: ContentDecisionChoice) => void;
  onCommentChange: (slideId: string, comment: string) => void;
  onSavePageDecision: (slideId: string) => Promise<boolean>;
  onSubmitReviewBatch: () => void | Promise<void>;
}

interface DraftContentBlocksProps {
  blocks: readonly ContentReviewDraftBlockViewModel[];
}

function DraftContentBlocks({ blocks }: DraftContentBlocksProps) {
  const nodes: ReactNode[] = [];
  let bullets: ContentReviewDraftBlockViewModel[] = [];
  const flushBullets = () => {
    if (!bullets.length) return;
    const group = bullets;
    bullets = [];
    nodes.push(
      <ul key={`bullets-${group[0].blockId}`}>
        {group.map((block) => <li key={block.blockId}>{block.text}</li>)}
      </ul>,
    );
  };
  for (const block of blocks) {
    if (block.type === "bullet") {
      bullets.push(block);
      continue;
    }
    flushBullets();
    nodes.push(<p key={block.blockId}>{block.text}</p>);
  }
  flushBullets();
  return <>{nodes}</>;
}

function draftMessage(slide: ContentReviewSlideViewModel): string {
  if (slide.localDraftState.dirty) return "尚未保存";
  if (slide.savedDecision) return "已保存";
  return "尚未判断";
}

export function ContentReviewViewModelSurface({
  viewModel,
  bridge,
  projectRoot,
  savingSlideId = null,
  submitting = false,
  pageMessage = "",
  readsDisabled = false,
  onDecisionChange,
  onCommentChange,
  onSavePageDecision,
  onSubmitReviewBatch,
}: ContentReviewViewModelSurfaceProps) {
  const slidesBySection = useMemo(() => {
    const grouped = new Map<string, ContentReviewSlideViewModel[]>();
    for (const slide of viewModel.slides) {
      const slides = grouped.get(slide.sectionId);
      if (slides) slides.push(slide);
      else grouped.set(slide.sectionId, [slide]);
    }
    return grouped;
  }, [viewModel.slides]);
  const progressPercent = viewModel.progress.total
    ? Math.min(100, (viewModel.progress.completed / viewModel.progress.total) * 100)
    : 0;
  const batchSubmitted = viewModel.batchState === "submitted";
  const pageWritesDisabled = !viewModel.availableActions.savePageDecision
    || batchSubmitted
    || submitting;
  const canSubmit = viewModel.availableActions.submitReviewBatch
    && !batchSubmitted
    && !submitting
    && !savingSlideId
    && viewModel.progress.total > 0
    && viewModel.progress.completed === viewModel.progress.total
    && viewModel.progress.remaining === 0
    && viewModel.progress.unsaved === 0;

  return (
    <main className="content-review-vm-page">
      <header className="content-review-vm-header" data-content-review-vm-header>
        <div className="content-review-vm-header-main">
          <div className="content-review-vm-project">
            <span>内容全稿审核</span>
            <h1>{viewModel.projectLabel}</h1>
            <p>{viewModel.sourceVersion} · revision {viewModel.revision} · {viewModel.slides.length} 页</p>
          </div>
          <div className="content-review-vm-progress" aria-label="审核进度">
            <strong>{viewModel.progress.completed} / {viewModel.progress.total}</strong>
            <span>已完成 · {viewModel.progress.unsaved} 未保存</span>
          </div>
        </div>
        <div
          className="content-review-vm-progress-track"
          role="progressbar"
          aria-label="全稿审核完成进度"
          aria-valuemin={0}
          aria-valuemax={viewModel.progress.total}
          aria-valuenow={viewModel.progress.completed}
        >
          <span style={{ width: `${progressPercent}%` }} />
        </div>
        <nav className="content-review-vm-chapter-nav" aria-label="章节快速定位">
          {viewModel.sections.map((section, index) => (
            <a key={section.sectionId} href={`#content-vm-chapter-${index + 1}`}>
              第 {index + 1} 章 · {section.title}
            </a>
          ))}
        </nav>
      </header>

      <div className="content-review-vm-document">
        <section className="content-review-vm-deck-intro" aria-labelledby="content-review-vm-intro-title">
          <span>完整阅读稿</span>
          <h2 id="content-review-vm-intro-title">按最终页序连续阅读完整内容</h2>
          <p>逐页核对页面目标、客户判断、实际文字和页面画面，再完成本页审核判断。</p>
          <div>
            <span>{viewModel.sections.length} 章</span>
            <span>{viewModel.slides.length} 页</span>
            <span>阅读优先</span>
          </div>
        </section>

        {pageMessage ? <p className="content-review-vm-message" role="status">{pageMessage}</p> : null}

        <section className="content-review-vm-deck" aria-label="完整内容全稿">
          {viewModel.sections.map((section, sectionIndex) => {
            const slides = slidesBySection.get(section.sectionId) ?? [];
            return (
              <section
                className="content-review-vm-chapter"
                id={`content-vm-chapter-${sectionIndex + 1}`}
                key={section.sectionId}
                aria-labelledby={`content-vm-chapter-${sectionIndex + 1}-title`}
              >
                <header className="content-review-vm-chapter-heading">
                  <span>{sectionIndex + 1}</span>
                  <div>
                    <h2 id={`content-vm-chapter-${sectionIndex + 1}-title`}>{section.title}</h2>
                    <p>{slides.length} 页 · 第 {slides[0]?.order ?? 0}–{slides.at(-1)?.order ?? 0} 页</p>
                  </div>
                </header>

                <div className="content-review-vm-chapter-slides">
                  {slides.map((slide) => {
                    const saving = savingSlideId === slide.slideId;
                    const controlsDisabled = pageWritesDisabled || Boolean(savingSlideId && !saving);
                    const hasMaterialVisuals = slide.materialVisuals.length > 0;
                    const readingLayoutClass = hasMaterialVisuals
                      ? "content-review-vm-reading-grid--with-visuals"
                      : "content-review-vm-reading-grid--text-only";
                    return (
                      <article
                        className="content-review-vm-slide"
                        id={`content-vm-${slide.slideId}`}
                        key={slide.slideId}
                        data-content-review-vm-slide
                        aria-label={`${slide.slideId} 内容审核`}
                      >
                        <header className="content-review-vm-slide-heading">
                          <span className="content-review-vm-page-number">{slide.order}</span>
                          <div>
                            <h3>{slide.neutralTitle}</h3>
                            <p>第 {slide.order} 页 · {slide.slideId}</p>
                          </div>
                          <span
                            className={`content-review-vm-mark${slide.localDraftState.decision ? ` is-${slide.localDraftState.decision}` : ""}`}
                            aria-label={slide.localDraftState.decision ? "本页已有判断" : "本页尚未判断"}
                          />
                        </header>

                        <div className={`content-review-vm-reading-grid ${readingLayoutClass}`}>
                          <div className="content-review-vm-text">
                            <section className="content-review-vm-purpose" aria-label={`${slide.slideId} 页面审核目标`}>
                              <div>
                                <span className="content-review-vm-label">这一页的目标</span>
                                <p>{slide.pageGoal}</p>
                              </div>
                              <div>
                                <span className="content-review-vm-label">希望客户形成的判断</span>
                                <p>{slide.customerJudgment}</p>
                              </div>
                            </section>
                            <section
                              className="content-review-vm-draft"
                              aria-label={`${slide.slideId} 页面实际文字`}
                            >
                              <span className="content-review-vm-label">页面实际文字</span>
                              <h4>{slide.draftContent.title}</h4>
                              <DraftContentBlocks blocks={slide.draftContent.blocks} />
                            </section>
                          </div>
                          {hasMaterialVisuals ? (
                            <ContentReviewMaterialVisuals
                              bridge={bridge}
                              projectRoot={projectRoot}
                              slideId={slide.slideId}
                              visuals={slide.materialVisuals}
                              readsDisabled={readsDisabled}
                            />
                          ) : null}
                        </div>

                        <p className="content-review-vm-reading-question">
                          <strong>本页阅读判断：</strong>{slide.readingQuestion}
                        </p>

                        <PageDecisionControl
                          slideId={slide.slideId}
                          decision={slide.localDraftState.decision}
                          comment={slide.localDraftState.comment}
                          saved={slide.savedDecision ?? undefined}
                          dirty={slide.localDraftState.dirty}
                          saving={saving}
                          message={draftMessage(slide)}
                          disabled={controlsDisabled}
                          saveDisabled={!viewModel.availableActions.savePageDecision || Boolean(savingSlideId)}
                          onDecisionChange={(decision) => onDecisionChange(slide.slideId, decision)}
                          onCommentChange={(comment) => onCommentChange(slide.slideId, comment)}
                          onSave={() => onSavePageDecision(slide.slideId)}
                        />
                      </article>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </section>

        <section className="content-review-vm-summary" aria-labelledby="content-review-vm-summary-title">
          <div>
            <span>全稿审核收口</span>
            <h2 id="content-review-vm-summary-title">
              {viewModel.progress.completed}/{viewModel.progress.total} 页已完成
            </h2>
            <p>{batchSubmitted
              ? "本轮审核已提交，等待 Codex 集中处理。"
              : canSubmit
                ? "全部页面已完成，可以提交本轮审核。"
                : `还有 ${viewModel.progress.remaining} 页未完成，${viewModel.progress.unsaved} 项尚未保存。`}</p>
          </div>
          <button
            type="button"
            disabled={!canSubmit}
            onClick={() => { void onSubmitReviewBatch(); }}
          >{batchSubmitted ? "本轮审核已提交" : submitting ? "正在提交…" : "完成本轮审核，交给 Codex 集中处理"}</button>
        </section>
      </div>
    </main>
  );
}

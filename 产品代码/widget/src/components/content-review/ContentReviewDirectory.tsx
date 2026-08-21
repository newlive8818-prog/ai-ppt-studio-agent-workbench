import { useEffect, useMemo, useRef } from "react";
import { X } from "lucide-react";

import type { ContentReviewChapter, ContentReviewSlide } from "../../types";

interface Props {
  open: boolean;
  chapters: ContentReviewChapter[];
  slides: ContentReviewSlide[];
  onClose: () => void;
  onNavigate: (slideId: string) => void;
}

export function ContentReviewDirectory({ open, chapters, slides, onClose, onNavigate }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const slidesBySection = useMemo(() => {
    const result = new Map<string, ContentReviewSlide[]>();
    for (const slide of slides) {
      const rows = result.get(slide.section_id) || [];
      rows.push(slide);
      result.set(slide.section_id, rows);
    }
    return result;
  }, [slides]);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  if (!open) return null;
  return (
    <>
      <button className="content-directory-backdrop" aria-label="关闭全稿目录" onClick={onClose} />
      <aside className="content-directory" role="dialog" aria-modal="true" aria-label="全稿目录">
        <header>
          <div><strong>全稿目录</strong><span>{slides.length} 页·只用于定位</span></div>
          <button ref={closeRef} type="button" aria-label="关闭全稿目录" onClick={onClose}><X size={18} /></button>
        </header>
        <nav aria-label="完整内容页面定位">
          {chapters.map((chapter, chapterIndex) => (
            <section key={chapter.section_id}>
              <h3><span>{String(chapterIndex + 1).padStart(2, "0")}</span>{chapter.title}</h3>
              {(slidesBySection.get(chapter.section_id) || []).map((slide) => (
                <button
                  key={slide.slide_id}
                  type="button"
                  aria-label={`${slide.slide_id} · ${slide.neutral_title}`}
                  onClick={() => onNavigate(slide.slide_id)}
                >
                  <b>{String(slide.order).padStart(2, "0")}</b>
                  <span>{slide.neutral_title}</span>
                  <i className={slide.decision_state.completed ? "complete" : ""} aria-label={slide.decision_state.completed ? "已判断" : "未判断"} />
                </button>
              ))}
            </section>
          ))}
        </nav>
      </aside>
    </>
  );
}

import { useEffect, useRef } from "react";
import { X } from "lucide-react";

import type { ContentReviewSlide } from "../../types/content-review";

interface Props {
  open: boolean;
  slides: ContentReviewSlide[];
  onClose: () => void;
  onNavigate: (slideId: string) => void;
}

export function ContentReviewDirectory({ open, slides, onClose, onNavigate }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);

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
          <section>
            <h3><span>01</span>完整全稿</h3>
            {slides.map((slide) => (
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
        </nav>
      </aside>
    </>
  );
}

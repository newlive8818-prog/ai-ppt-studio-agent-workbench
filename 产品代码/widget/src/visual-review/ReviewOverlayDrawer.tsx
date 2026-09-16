import type { ReactNode } from "react";

interface Props {
  open: boolean;
  title: string;
  side?: "left" | "right";
  onClose: () => void;
  children: ReactNode;
}

export function ReviewOverlayDrawer({ open, title, side = "right", onClose, children }: Props) {
  if (!open) return null;
  return (
    <div className="visual-overlay-layer">
      <button className="visual-overlay-backdrop" aria-label={`关闭${title}`} onClick={onClose} />
      <aside className={`visual-overlay-drawer visual-overlay-drawer-${side}`} role="dialog" aria-modal="true" aria-label={title} data-overlay="true">
        <header>
          <h2>{title}</h2>
          <button type="button" onClick={onClose}>关闭</button>
        </header>
        <div className="visual-overlay-content">{children}</div>
      </aside>
    </div>
  );
}

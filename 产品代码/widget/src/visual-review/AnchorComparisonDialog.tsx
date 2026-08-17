import { createPortal } from "react-dom";
import { useEffect, useId, useRef, type RefObject } from "react";

import { ProjectAssetImage } from "../components/ProjectAssetImage";
import type { HostBridge } from "../types/host";

interface Props {
  bridge: HostBridge;
  projectRoot: string;
  slideId: string;
  previousAssetRef: string;
  currentAssetRef: string;
  onClose: () => void;
  fallbackFocusRef: RefObject<HTMLElement | null>;
}

interface ComparisonModalOwner {
  token: symbol;
  dialogRef: RefObject<HTMLElement | null>;
  initialFocusRef: RefObject<HTMLElement | null>;
  trigger: HTMLElement | null;
  fallbackFocusRef: RefObject<HTMLElement | null>;
}

interface ComparisonModalStack {
  originalBodyOverflow: string;
  owners: ComparisonModalOwner[];
}

const comparisonModalStacks = new WeakMap<Document, ComparisonModalStack>();

function focusModalOwner(owner: ComparisonModalOwner) {
  const target = owner.initialFocusRef.current || owner.dialogRef.current;
  if (target?.isConnected) target.focus();
}

function restoreModalOwnerTrigger(owner: ComparisonModalOwner) {
  if (owner.trigger?.isConnected) owner.trigger.focus();
  else if (owner.fallbackFocusRef.current?.isConnected) owner.fallbackFocusRef.current.focus();
}

function registerComparisonModal(documentRef: Document, owner: ComparisonModalOwner) {
  let stack = comparisonModalStacks.get(documentRef);
  if (!stack) {
    stack = {
      originalBodyOverflow: documentRef.body.style.overflow,
      owners: [],
    };
    comparisonModalStacks.set(documentRef, stack);
  }
  stack.owners.push(owner);
  documentRef.body.style.overflow = "hidden";
  focusModalOwner(owner);

  let registered = true;
  return () => {
    if (!registered) return;
    registered = false;
    const currentStack = comparisonModalStacks.get(documentRef);
    if (!currentStack) return;
    const ownerIndex = currentStack.owners.findIndex((candidate) => candidate.token === owner.token);
    if (ownerIndex < 0) return;
    currentStack.owners.splice(ownerIndex, 1);

    const nextTop = currentStack.owners.at(-1);
    if (nextTop) {
      documentRef.body.style.overflow = "hidden";
      if (!nextTop.dialogRef.current?.contains(documentRef.activeElement)) focusModalOwner(nextTop);
      return;
    }

    documentRef.body.style.overflow = currentStack.originalBodyOverflow;
    comparisonModalStacks.delete(documentRef);
    restoreModalOwnerTrigger(owner);
  };
}

export function AnchorComparisonDialog({
  bridge,
  projectRoot,
  slideId,
  previousAssetRef,
  currentAssetRef,
  onClose,
  fallbackFocusRef,
}: Props) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const titleId = `${useId()}-anchor-comparison-title`;

  useEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const background = fallbackFocusRef.current?.closest<HTMLElement>(".visual-professional-page") || null;
    const backgroundHadInert = background?.hasAttribute("inert") || false;
    const previousInertValue = background?.getAttribute("inert") ?? "";
    background?.setAttribute("inert", "");
    const unregisterModal = registerComparisonModal(document, {
      token: Symbol("anchor-comparison-modal"),
      dialogRef,
      initialFocusRef: closeButtonRef,
      trigger,
      fallbackFocusRef,
    });

    return () => {
      if (backgroundHadInert) background?.setAttribute("inert", previousInertValue);
      else background?.removeAttribute("inert");
      unregisterModal();
    };
  }, [fallbackFocusRef]);

  const trapFocus = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(
      "button:not(:disabled), [href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex='-1'])",
    ) || []);
    if (!focusable.length) {
      event.preventDefault();
      dialogRef.current?.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (focusable.length === 1 || (!event.shiftKey && document.activeElement === last)) {
      event.preventDefault();
      first.focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    }
  };

  return createPortal(
    <div className="anchor-comparison-layer">
      <button className="anchor-comparison-backdrop" type="button" aria-label="关闭对比背景" onClick={onClose} />
      <section
        ref={dialogRef}
        className="anchor-comparison-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={trapFocus}
      >
        <header>
          <div>
            <h2 id={titleId}>{slideId} 前后版本对比</h2>
            <p>两侧使用同一显示尺寸；对比只辅助判断本轮变化，不构成 G3 确认。</p>
          </div>
          <button ref={closeButtonRef} type="button" aria-label="关闭对比" onClick={onClose}>关闭</button>
        </header>
        <div className="anchor-comparison-grid">
          <section>
            <h3>上一版</h3>
            <div className="anchor-comparison-stage">
              <ProjectAssetImage
                bridge={bridge}
                projectRoot={projectRoot}
                assetRef={previousAssetRef}
                alt={`${slideId} 上一版锚点成果`}
              />
            </div>
          </section>
          <section>
            <h3>当前版</h3>
            <div className="anchor-comparison-stage">
              <ProjectAssetImage
                bridge={bridge}
                projectRoot={projectRoot}
                assetRef={currentAssetRef}
                alt={`${slideId} 当前版锚点成果`}
              />
            </div>
          </section>
        </div>
      </section>
    </div>,
    document.body,
  );
}

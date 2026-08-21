import { useEffect, useRef, useState } from "react";

import { ProjectAssetImage } from "../components/ProjectAssetImage";
import type { HostBridge } from "../types/host";
import type { ContentReviewMaterialVisualViewModel } from "./content-review-page-view-model";

interface ContentReviewMaterialVisualsProps {
  bridge: HostBridge;
  projectRoot: string;
  slideId: string;
  visuals: readonly ContentReviewMaterialVisualViewModel[];
  readsDisabled?: boolean;
}

interface LazyMaterialVisualProps {
  bridge: HostBridge;
  projectRoot: string;
  visual: ContentReviewMaterialVisualViewModel;
  readsDisabled: boolean;
}

function LazyMaterialVisual({
  bridge,
  projectRoot,
  visual,
  readsDisabled,
}: LazyMaterialVisualProps) {
  const activationRef = useRef<HTMLDivElement>(null);
  const [nearViewport, setNearViewport] = useState(false);
  const [manuallyActivated, setManuallyActivated] = useState(false);
  const supportsViewportObserver = typeof IntersectionObserver !== "undefined";
  const activated = nearViewport || manuallyActivated;

  useEffect(() => {
    const target = activationRef.current;
    if (!target || activated || !supportsViewportObserver || readsDisabled) return;
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      setNearViewport(true);
      observer.disconnect();
    }, { rootMargin: "320px 0px" });
    observer.observe(target);
    return () => observer.disconnect();
  }, [activated, readsDisabled, supportsViewportObserver]);

  return (
    <div
      className="content-review-vm-image-slot"
      data-content-review-vm-visual={visual.visualId}
      ref={activationRef}
    >
      {activated && !readsDisabled ? (
        <ProjectAssetImage
          bridge={bridge}
          projectRoot={projectRoot}
          assetRef={visual.assetRef}
          alt={visual.altText}
          className="content-review-vm-image"
        />
      ) : (
        <div className="asset-placeholder content-review-vm-image">
          <span>{readsDisabled
            ? "当前页面画面暂不可读"
            : supportsViewportObserver
              ? "进入视口后读取页面画面"
              : "当前环境未自动读取页面画面"}</span>
          {!readsDisabled && !supportsViewportObserver ? (
            <button
              type="button"
              className="content-review-vm-manual-read"
              aria-label={`读取本页画面：${visual.altText}`}
              onClick={() => setManuallyActivated(true)}
            >读取本页画面</button>
          ) : null}
        </div>
      )}
    </div>
  );
}

export function ContentReviewMaterialVisuals({
  bridge,
  projectRoot,
  slideId,
  visuals,
  readsDisabled = false,
}: ContentReviewMaterialVisualsProps) {
  if (visuals.length === 0) return null;

  return (
    <section
      className="content-review-vm-visuals"
      aria-label={`${slideId} 文字与图片材料一起审核`}
    >
      <span className="content-review-vm-label">文字与图片材料一起审核</span>
      <div className="content-review-vm-visual-list">
        {visuals.map((visual) => (
          <LazyMaterialVisual
            key={visual.visualId}
            bridge={bridge}
            projectRoot={projectRoot}
            visual={visual}
            readsDisabled={readsDisabled}
          />
        ))}
      </div>
    </section>
  );
}

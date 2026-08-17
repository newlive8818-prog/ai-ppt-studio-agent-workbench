import { useEffect, useRef, useState } from "react";

import { ProjectAssetImage } from "../components/ProjectAssetImage";
import type { ContentReviewSlide } from "../types/content-review";
import type { HostBridge } from "../types/host";

interface Props {
  bridge: HostBridge;
  projectRoot: string;
  slide: ContentReviewSlide;
  readsDisabled?: boolean;
}

interface LazyImageProps {
  bridge: HostBridge;
  projectRoot: string;
  assetRef: string;
  alt: string;
  readsDisabled: boolean;
}

function LazyProjectAssetImage({ bridge, projectRoot, assetRef, alt, readsDisabled }: LazyImageProps) {
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
    <div className="content-material-image-slot" ref={activationRef}>
      {activated && !readsDisabled ? (
        <ProjectAssetImage
          bridge={bridge}
          projectRoot={projectRoot}
          assetRef={assetRef}
          alt={alt}
          className="content-material-image"
        />
      ) : (
        <div className="asset-placeholder content-material-image">
          <span>{readsDisabled
            ? "权威审核投影无效；项目材料未读取"
            : supportsViewportObserver
              ? "进入视口后读取项目材料"
              : "当前环境不支持视口检测；项目材料未自动读取"}</span>
          {!readsDisabled && !supportsViewportObserver ? (
            <button
              type="button"
              className="content-material-manual-read"
              aria-label={`读取本条材料：${alt}`}
              onClick={() => setManuallyActivated(true)}
            >读取本条材料</button>
          ) : null}
        </div>
      )}
    </div>
  );
}

export function ContentMaterialView({ bridge, projectRoot, slide, readsDisabled = false }: Props) {
  const materialViews = slide.material_mode === "proposal-led" ? [] : slide.material_views;
  return (
    <section className="content-material-view" aria-label={`${slide.slide_id} 材料画面`}>
      <header className="content-material-view-heading">
        <span>文字与材料同屏审核</span>
        <strong>{materialViews.length ? `${materialViews.length} 条材料` : "无材料画面"}</strong>
      </header>

      {materialViews.length ? (
        <div className="content-material-list">
          {materialViews.map((material, index) => (
            <figure className="content-material-card" key={material.material_view_id}>
              <LazyProjectAssetImage
                bridge={bridge}
                projectRoot={projectRoot}
                assetRef={material.asset_ref}
                alt={`${slide.slide_id} 材料画面 ${index + 1}`}
                readsDisabled={readsDisabled}
              />
              <figcaption>
                <div className="content-material-source">
                  <strong>{material.source_file_name}</strong>
                  <span>第 {material.page_number} 页 · {material.region_label}</span>
                </div>
                <dl className="content-material-metadata">
                  <div><dt>用途</dt><dd>{material.purpose}</dd></div>
                  <div><dt>处理方式</dt><dd>{material.treatment}</dd></div>
                  <div><dt>证据身份</dt><dd>{material.evidence_identity}</dd></div>
                </dl>
              </figcaption>
            </figure>
          ))}
        </div>
      ) : (
        <p className="content-material-empty">
          {slide.material_mode === "proposal-led"
            ? "本页为 proposal-led 内容，没有可展示的项目材料画面。"
            : "本页尚未登记可审核的项目材料画面，请按当前证据缺口判断。"}
        </p>
      )}
    </section>
  );
}

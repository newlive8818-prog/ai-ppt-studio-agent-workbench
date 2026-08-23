import { ImageOff, LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { HostBridge } from "../types";


interface Props {
  bridge: HostBridge;
  projectRoot: string;
  assetRef: string;
  alt: string;
  className?: string;
}

export function ProjectAssetImage({ bridge, projectRoot, assetRef, alt, className = "" }: Props) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [nearViewport, setNearViewport] = useState(false);
  const [source, setSource] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame || typeof IntersectionObserver === "undefined") {
      setNearViewport(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      setNearViewport(true);
      observer.disconnect();
    }, { rootMargin: "640px 0px" });
    observer.observe(frame);
    return () => observer.disconnect();
  }, [assetRef]);

  useEffect(() => {
    let active = true;
    setSource("");
    setFailed(false);
    if (!assetRef || !nearViewport) return () => { active = false; };
    bridge.callTool("read_ai_ppt_project_asset", {
      projectRoot,
      assetRef,
    }).then((result) => {
      if (active) setSource(`data:${result.asset.mimeType};base64,${result.asset.dataBase64}`);
    }).catch(() => {
      if (active) setFailed(true);
    });
    return () => { active = false; };
  }, [assetRef, bridge, nearViewport, projectRoot]);

  if (failed) return <div ref={frameRef} className={`asset-placeholder ${className}`}><ImageOff size={20} /><span>预览暂不可读</span></div>;
  if (!source) return <div ref={frameRef} className={`asset-placeholder ${className}`}><LoaderCircle size={20} /><span>{nearViewport ? "读取项目预览" : "预览将在接近时读取"}</span></div>;
  return <div ref={frameRef} className="project-asset-frame"><img className={className} src={source} alt={alt} loading="lazy" decoding="async" /></div>;
}

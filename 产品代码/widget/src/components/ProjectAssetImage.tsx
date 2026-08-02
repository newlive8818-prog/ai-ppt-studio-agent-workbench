import { ImageOff, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import type { HostBridge } from "../types";


interface Props {
  bridge: HostBridge;
  projectRoot: string;
  assetRef: string;
  alt: string;
  className?: string;
}

interface AssetResult {
  asset: {
    assetRef: string;
    mimeType: string;
    bytes: number;
    dataBase64: string;
  };
}

export function ProjectAssetImage({ bridge, projectRoot, assetRef, alt, className = "" }: Props) {
  const [source, setSource] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setSource("");
    setFailed(false);
    if (!assetRef) return () => { active = false; };
    bridge.callTool<AssetResult>("read_ai_ppt_project_asset", {
      projectRoot,
      assetRef,
    }).then((result) => {
      if (active) setSource(`data:${result.asset.mimeType};base64,${result.asset.dataBase64}`);
    }).catch(() => {
      if (active) setFailed(true);
    });
    return () => { active = false; };
  }, [assetRef, bridge, projectRoot]);

  if (failed) return <div className={`asset-placeholder ${className}`}><ImageOff size={20} /><span>预览暂不可读</span></div>;
  if (!source) return <div className={`asset-placeholder ${className}`}><LoaderCircle size={20} /><span>读取项目预览</span></div>;
  return <img className={className} src={source} alt={alt} />;
}

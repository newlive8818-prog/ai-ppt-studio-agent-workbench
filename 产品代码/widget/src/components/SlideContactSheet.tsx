import type { HostBridge } from "../types";
import { ProjectAssetImage } from "./ProjectAssetImage";


interface Props {
  bridge: HostBridge;
  projectRoot: string;
  renders: Array<{ asset_ref: string; exists: boolean }>;
  selectedIndex: number;
  onSelected: (index: number) => void;
}

export function SlideContactSheet({ bridge, projectRoot, renders, selectedIndex, onSelected }: Props) {
  return (
    <div className="contact-sheet" aria-label="页面渲染接触表">
      {renders.map((render, index) => (
        <button
          className={index === selectedIndex ? "active" : ""}
          type="button"
          key={`${render.asset_ref}-${index}`}
          aria-label={`查看第 ${index + 1} 页`}
          onClick={() => onSelected(index)}
        >
          {render.exists ? <ProjectAssetImage bridge={bridge} projectRoot={projectRoot} assetRef={render.asset_ref} alt={`第 ${index + 1} 页渲染`} /> : <span className="missing-render">缺少渲染</span>}
          <small>{String(index + 1).padStart(2, "0")}</small>
        </button>
      ))}
    </div>
  );
}

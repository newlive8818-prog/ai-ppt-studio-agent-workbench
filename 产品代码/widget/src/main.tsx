import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";

import { ReviewSurfaceRouter } from "./ReviewSurfaceRouter";
import { createBrowserReviewClient } from "./lib/browser-review-client";
import type { HostBridge, ReviewSurfaceData } from "./types/host";
import { parseToolOutput } from "./types/tool-contracts";
import type { ToolContractMap } from "./types/tool-contracts";
import "./styles/base.css";

function createPreviewBridge(): HostBridge {
  return {
    async connect() {},
    async callTool<K extends keyof ToolContractMap>(
      name: K,
      args: ToolContractMap[K]["input"],
    ) {
      if (name === "read_ai_ppt_project_asset") {
        const assetRef = String(
          (
            args as ToolContractMap["read_ai_ppt_project_asset"]["input"]
          ).assetRef || "",
        );
        const asset = window.__AI_PPT_PREVIEW_ASSETS__?.[assetRef];
        if (asset) return parseToolOutput(name, { asset });
      }
      throw new Error("Preview mode is read-only.");
    },
  };
}

function SurfaceRouter() {
  const preview = window.__AI_PPT_PREVIEW__;
  const [data, setData] = useState<ReviewSurfaceData | undefined>(preview);
  const [error, setError] = useState("");
  const bridge = useMemo(
    () => (preview ? createPreviewBridge() : createBrowserReviewClient()),
    [preview],
  );

  useEffect(() => {
    if (preview) return;
    if (!window.location.hash.startsWith("#token=")) {
      setError("该页面需要有效的专业审核会话，请从 Codex 对话按需打开。");
      return;
    }
    let mounted = true;
    bridge
      .connect((incoming) => {
        if (mounted) setData(incoming);
      })
      .catch(() => {
        if (mounted) {
          setError("无法连接专业审核会话，项目数据未被修改。");
        }
      });
    return () => {
      mounted = false;
    };
  }, [bridge, preview]);

  if (!data) {
    return (
      <main className="loading-shell">
        <div className="loading-mark">PPT</div>
        <h1>正在读取专业审核成果</h1>
        <p>{error || "正在同步同一 project revision…"}</p>
      </main>
    );
  }
  return <ReviewSurfaceRouter data={data} bridge={bridge} />;
}

createRoot(document.getElementById("root")!).render(<SurfaceRouter />);

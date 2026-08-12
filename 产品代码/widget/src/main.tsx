import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { ProfessionalReviewApp } from "./ProfessionalReviewApp";
import { createBrowserReviewClient } from "./lib/browser-review-client";
import { createSidebarHostClient } from "./lib/sidebar-host-client";
import type { HostBridge, SurfaceData } from "./types";
import "./styles.css";

function createPreviewBridge(): HostBridge {
  return {
    async connect() {},
    async callTool<T>(name: string, args: Record<string, unknown>) {
      if (name === "read_ai_ppt_project_asset") {
        const assetRef = String(args.assetRef || "");
        const asset = window.__AI_PPT_PREVIEW_ASSETS__?.[assetRef];
        if (asset) return { asset } as T;
      }
      throw new Error("Preview mode is read-only.");
    },
    async updateModelContext() {},
    async sendFollowUp() {},
    async confirmMission() {
      throw new Error("Preview mode cannot confirm a mission.");
    },
    getHostEnvironment() {
      return {
        containerWidth: window.innerWidth,
        canSendMessage: false,
        canUpdateModelContext: false,
      };
    },
    notifySize() {},
  };
}

const preview = window.__AI_PPT_PREVIEW__;
const browserReview = !preview && window.location.hash.startsWith("#token=");
const bridge = preview
  ? createPreviewBridge()
  : browserReview
    ? createBrowserReviewClient()
    : createSidebarHostClient();

function SurfaceRouter() {
  const [data, setData] = useState<SurfaceData | undefined>(preview);
  const [error, setError] = useState("");

  useEffect(() => {
    if (preview) return;
    let mounted = true;
    bridge.connect((incoming) => {
      if (mounted) setData(incoming);
    }).catch(() => {
      if (mounted) setError("无法连接 Codex 宿主，项目数据未被修改。");
    });
    return () => { mounted = false; };
  }, []);

  if (!data) {
    return <main className="loading-shell"><div className="loading-mark">PPT</div><h1>正在读取 AI PPT 项目</h1><p>{error || "正在同步同一 project revision…"}</p></main>;
  }
  if (data.surface === "review") {
    return <ProfessionalReviewApp initialData={data} bridge={bridge} managedConnection />;
  }
  return <App initialData={data} bridge={bridge} managedConnection />;
}

createRoot(document.getElementById("root")!).render(<SurfaceRouter />);

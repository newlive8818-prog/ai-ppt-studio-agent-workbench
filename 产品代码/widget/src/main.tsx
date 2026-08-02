import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { createMcpAppClient } from "./lib/mcp-app-client";
import type { HostBridge } from "./types";
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
    async requestDisplayMode() {},
    notifySize() {},
  };
}

const bridge = window.__AI_PPT_PREVIEW__
  ? createPreviewBridge()
  : createMcpAppClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App initialData={window.__AI_PPT_PREVIEW__} bridge={bridge} />
  </StrictMode>,
);

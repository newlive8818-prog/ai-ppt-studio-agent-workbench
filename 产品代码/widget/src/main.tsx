import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { createMcpAppClient } from "./lib/mcp-app-client";
import type { HostBridge } from "./types";
import "./styles.css";

function createPreviewBridge(): HostBridge {
  return {
    async connect() {},
    async callTool() { throw new Error("Preview mode is read-only."); },
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

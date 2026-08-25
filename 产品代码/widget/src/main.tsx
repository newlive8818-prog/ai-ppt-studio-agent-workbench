import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import { ReviewSurfaceRouter } from "./ReviewSurfaceRouter";
import { createBrowserReviewClient } from "./lib/browser-review-client";
import { createSidebarHostClient } from "./lib/sidebar-host-client";
import type { HostBridge, SurfaceData } from "./types";
import { parseToolOutput, type ToolContractMap } from "./types/tool-contracts";
import "./styles.css";

function currentPreview(): SurfaceData | undefined {
  return window.__AI_PPT_CONTENT_REVIEW_PREVIEW__ || window.__AI_PPT_PREVIEW__;
}

function createPreviewBridge(): HostBridge {
  function count(name: string) {
    const calls = window.__AI_PPT_PREVIEW_CALLS__ ||= {};
    calls[name] = (calls[name] || 0) + 1;
  }
  return {
    async connect() {},
    async callTool<K extends keyof ToolContractMap>(
      name: K,
      args: ToolContractMap[K]["input"],
    ) {
      count(name);
      const projection = window.__AI_PPT_CONTENT_REVIEW_PREVIEW__;
      if (name === "get_content_full_deck_review_projection" && projection) {
        return parseToolOutput(name, structuredClone(projection));
      }
      if (name === "save_content_full_deck_page_decision" && projection) {
        const input = args as ToolContractMap["save_content_full_deck_page_decision"]["input"];
        const scenario = window.__AI_PPT_CONTENT_REVIEW_SCENARIO__;
        if (scenario === "save-failure" || scenario === "source-conflict") {
          const error = new Error(
            scenario === "source-conflict" ? "Preview source changed." : "Preview save failed.",
          ) as Error & { code?: string };
          error.code = scenario === "source-conflict" ? "CONTENT_REVIEW_CONFLICT" : "CONTENT_REVIEW_SAVE_FAILED";
          throw error;
        }
        const slide = projection.slides.find((item) => item.slide_id === input.slideId);
        if (!slide) throw new Error("Preview slide not found.");
        slide.decision_state = {
          selected: input.decision,
          comment: input.comment,
          completed: true,
          saved: true,
          frozen: false,
        };
        projection.revision += 1;
        const completed = projection.slides.filter((item) => item.decision_state.completed).length;
        projection.review_progress.completed = completed;
        projection.review_progress.remaining = projection.slides.length - completed;
        projection.review_progress.saved_comment_count = projection.slides.filter((item) => item.decision_state.comment).length;
        projection.review_progress.counts = {
          approved: projection.slides.filter((item) => item.decision_state.selected === "approved").length,
          modify: projection.slides.filter((item) => item.decision_state.selected === "modify").length,
          evidence: projection.slides.filter((item) => item.decision_state.selected === "evidence").length,
          merge_or_delete: projection.slides.filter((item) => item.decision_state.selected === "merge-or-delete").length,
        };
        return parseToolOutput(name, {
          page_completion: { slide_id: slide.slide_id, completed: true },
          review_progress: projection.review_progress,
          revision: projection.revision,
        });
      }
      if (name === "submit_content_full_deck_review_batch") {
        const error = new Error("Preview mode cannot issue a trusted host confirmation.") as Error & { code?: string };
        error.code = "HOST_CONFIRMATION_UNAVAILABLE";
        throw error;
      }
      if (name === "open_content_full_deck_evidence_browser" && projection) {
        const input = args as ToolContractMap["open_content_full_deck_evidence_browser"]["input"];
        return parseToolOutput(name, {
          status: "review-session-ready",
          opened: false,
          reviewType: "content-evidence",
          reviewSessionId: input.reviewSessionId,
          sourceVersion: input.sourceVersion,
          slideId: input.slideId,
          evidenceId: input.evidenceId,
          materialRef: input.materialRef,
          url: "http://127.0.0.1/preview-evidence-not-opened",
        });
      }
      if (name === "read_ai_ppt_project_asset") {
        const assetArgs = args as ToolContractMap["read_ai_ppt_project_asset"]["input"];
        const asset = window.__AI_PPT_PREVIEW_ASSETS__?.[assetArgs.assetRef];
        if (asset) return parseToolOutput(name, { asset });
      }
      throw new Error("Preview mode does not provide this authoritative operation.");
    },
    async updateModelContext() {},
    async sendFollowUp() { count("sendFollowUp"); },
    async confirmMission() { throw new Error("Preview mode cannot confirm a mission."); },
    getHostEnvironment() {
      return { containerWidth: window.innerWidth, canSendMessage: false, canUpdateModelContext: false };
    },
    notifySize() {},
  };
}

const preview = currentPreview();
const browserReview = !preview && window.location.hash.startsWith("#token=");
const bridge = preview
  ? createPreviewBridge()
  : browserReview
    ? createBrowserReviewClient()
    : createSidebarHostClient();

function projectRootFor(data: SurfaceData | undefined): string {
  if (!data) return "";
  if (data.surface === "content-full-deck") {
    return window.__AI_PPT_CONTENT_REVIEW_PROJECT_ROOT__ || "";
  }
  return data.surface === "review"
    ? data.selectedProjectRoot
    : data.selectedProjectRoot || data.snapshot.project.project_root;
}

function SurfaceRouter() {
  const [data, setData] = useState<SurfaceData | undefined>(preview);
  const [projectRoot, setProjectRoot] = useState(() => projectRootFor(preview));
  const [error, setError] = useState("");

  useEffect(() => {
    if (preview) return;
    let mounted = true;
    bridge.connect((incoming) => {
      if (!mounted) return;
      setData(incoming);
      setProjectRoot((current) => projectRootFor(incoming) || current);
    }).catch(() => {
      if (mounted) setError("无法连接 Codex 宿主，项目数据未被修改。");
    });
    return () => { mounted = false; };
  }, []);

  if (!data) {
    return <main className="loading-shell"><div className="loading-mark">PPT</div><h1>正在读取 AI PPT 项目</h1><p>{error || "正在同步同一 project revision…"}</p></main>;
  }
  return <ReviewSurfaceRouter initialData={data} projectRoot={projectRoot} bridge={bridge} managedConnection />;
}

createRoot(document.getElementById("root")!).render(<SurfaceRouter />);

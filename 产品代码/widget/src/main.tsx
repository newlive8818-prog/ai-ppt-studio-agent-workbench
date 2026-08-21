import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { ProfessionalReviewApp } from "./ProfessionalReviewApp";
import { createBrowserReviewClient } from "./lib/browser-review-client";
import { createSidebarHostClient } from "./lib/sidebar-host-client";
import type { HostBridge, SurfaceData } from "./types";
import "./styles.css";

function createPreviewBridge(): HostBridge {
  function count(name: string) {
    const calls = window.__AI_PPT_PREVIEW_CALLS__ ||= {};
    calls[name] = (calls[name] || 0) + 1;
  }
  return {
    async connect() {},
    async callTool<T>(name: string, args: Record<string, unknown>) {
      count(name);
      if (name === "get_content_sidebar_review_projection") {
        const projection = window.__AI_PPT_CONTENT_REVIEW_PREVIEW__;
        if (projection) return structuredClone(projection) as T;
      }
      if (name === "save_content_page_decision") {
        const scenario = window.__AI_PPT_CONTENT_REVIEW_SCENARIO__;
        if (scenario === "save-failure" || scenario === "source-conflict") {
          const error = new Error(
            scenario === "source-conflict" ? "Preview source changed." : "Preview save failed.",
          ) as Error & { code?: string };
          error.code = scenario === "source-conflict"
            ? "CONTENT_REVIEW_CONFLICT"
            : "CONTENT_REVIEW_SAVE_FAILED";
          throw error;
        }
        const projection = window.__AI_PPT_CONTENT_REVIEW_PREVIEW__;
        if (projection?.display_policy !== "content-sidebar-full-deck") {
          throw new Error("Content review is not ready in this preview.");
        }
        const slide = projection.slides.find((item) => item.slide_id === String(args.slideId || ""));
        if (!slide) throw new Error("Preview slide not found.");
        const selected = String(args.decision || "") as typeof slide.decision_state.selected;
        slide.decision_state = {
          selected,
          comment: String(args.comment || ""),
          completed: true,
          saved: true,
          frozen: false,
        };
        projection.revision += 1;
        const completed = projection.slides.filter((item) => item.decision_state.completed).length;
        projection.review_progress.completed = completed;
        projection.review_progress.remaining = projection.slides.length - completed;
        projection.review_progress.next_incomplete_slide_id = projection.slides.find(
          (item) => !item.decision_state.completed,
        )?.slide_id || "";
        projection.review_progress.saved_comment_count = projection.slides.filter(
          (item) => item.decision_state.comment,
        ).length;
        projection.review_progress.counts = {
          approved: projection.slides.filter((item) => item.decision_state.selected === "approved").length,
          modify: projection.slides.filter((item) => item.decision_state.selected === "modify").length,
          evidence: projection.slides.filter((item) => item.decision_state.selected === "evidence").length,
          merge_or_delete: projection.slides.filter((item) => item.decision_state.selected === "merge-or-delete").length,
        };
        const previewData = window.__AI_PPT_PREVIEW__;
        if (!previewData || !("snapshot" in previewData)) throw new Error("Preview snapshot is unavailable.");
        const snapshot = structuredClone(previewData.snapshot);
        snapshot.revision = projection.revision;
        return {
          artifact_ref: `artifact://page-decision/preview-${slide.slide_id}-${projection.revision}`,
          page_completion: { slide_id: slide.slide_id, completed: true },
          review_progress: projection.review_progress,
          snapshot,
        } as T;
      }
      if (name === "submit_content_review_batch") {
        const projection = window.__AI_PPT_CONTENT_REVIEW_PREVIEW__;
        if (projection?.display_policy !== "content-sidebar-full-deck") {
          throw new Error("Content review is not ready in this preview.");
        }
        projection.phase = "review-batch-submitted";
        projection.current_batch.status = "submitted";
        projection.slides.forEach((slide) => { slide.decision_state.frozen = true; });
        projection.revision += 1;
        const previewData = window.__AI_PPT_PREVIEW__;
        if (!previewData || !("snapshot" in previewData)) throw new Error("Preview snapshot is unavailable.");
        const snapshot = structuredClone(previewData.snapshot);
        snapshot.revision = projection.revision;
        return {
          artifact_ref: "artifact://content-review-batch/deterministic-preview-submitted",
          follow_up_message: "请基于冻结审核批次形成整套修改方案。",
          snapshot,
        } as T;
      }
      if (name === "open_content_evidence_browser") {
        return { opened: true, reviewType: "content-evidence", ...args } as T;
      }
      if (name === "read_ai_ppt_project_asset") {
        const assetRef = String(args.assetRef || "");
        const asset = window.__AI_PPT_PREVIEW_ASSETS__?.[assetRef];
        if (asset) return { asset } as T;
      }
      throw new Error("Preview mode is read-only.");
    },
    async updateModelContext() {},
    async sendFollowUp() { count("sendFollowUp"); },
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

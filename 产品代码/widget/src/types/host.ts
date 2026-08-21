import type { ContentReviewSurfaceData } from "./content-review";
import type { ToolContractMap } from "./tool-contracts";
import type { VisualReviewSurfaceData } from "./visual-review";

export type ReviewSurfaceData =
  | ContentReviewSurfaceData
  | VisualReviewSurfaceData;

export interface HostBridgeCallOptions {
  signal?: AbortSignal;
}

export interface VisualArtifactRecoveryScope {
  projectRoot: string;
  expectedRevision: number;
  reviewSessionId: string;
  sourceVersion: string;
  savedArtifactRef: string;
}

export interface VisualHostNotificationRecoveryResult {
  savedArtifactRef: string;
  hostNotificationStatus: "sent";
  snapshotRevision: number;
}

export interface VisualAiReceiptRecoveryInput extends VisualArtifactRecoveryScope {
  receiptIdentity: string;
}

export interface VisualAiReceiptRecoveryResult {
  savedArtifactRef: string;
  aiReceiptStatus: "received";
  snapshotRevision: number;
}

export interface BrowserReviewRecoveryBridge {
  retryVisualHostNotification(
    input: VisualArtifactRecoveryScope,
    options?: HostBridgeCallOptions,
  ): Promise<VisualHostNotificationRecoveryResult>;
  verifyVisualAiReceipt(
    input: VisualAiReceiptRecoveryInput,
    options?: HostBridgeCallOptions,
  ): Promise<VisualAiReceiptRecoveryResult>;
}

export interface HostBridge {
  connect(onData?: (data: ReviewSurfaceData) => void): Promise<void>;
  callTool<K extends keyof ToolContractMap>(
    name: K,
    args: ToolContractMap[K]["input"],
    options?: HostBridgeCallOptions,
  ): Promise<ToolContractMap[K]["output"]>;
  switchReview?(reviewType: "content" | "visual"): Promise<void>;
  retryVisualHostNotification?: BrowserReviewRecoveryBridge["retryVisualHostNotification"];
  verifyVisualAiReceipt?: BrowserReviewRecoveryBridge["verifyVisualAiReceipt"];
}

declare global {
  interface Window {
    __AI_PPT_PREVIEW__?: ReviewSurfaceData;
    __AI_PPT_PREVIEW_ASSETS__?: Record<
      string,
      {
        assetRef: string;
        mimeType: string;
        bytes: number;
        dataBase64: string;
      }
    >;
  }
}

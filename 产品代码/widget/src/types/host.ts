import type { HostBridge as LegacyHostBridge } from "../types";

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

export interface HostBridge extends LegacyHostBridge {
  retryVisualHostNotification?: (
    input: VisualArtifactRecoveryScope,
    options?: HostBridgeCallOptions,
  ) => Promise<VisualHostNotificationRecoveryResult>;
  verifyVisualAiReceipt?: (
    input: VisualAiReceiptRecoveryInput,
    options?: HostBridgeCallOptions,
  ) => Promise<VisualAiReceiptRecoveryResult>;
}

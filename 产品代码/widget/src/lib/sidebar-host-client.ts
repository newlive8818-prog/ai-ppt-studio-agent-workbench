import type {
  HostBridge,
  MissionConfirmationResult,
  SurfaceData,
} from "../types";
import { parseToolOutput, type ToolContractMap } from "../types/tool-contracts";

function sidebarError(code: string, message: string) {
  const error = new Error(message) as Error & { code?: string };
  error.code = code;
  return error;
}

export function createSidebarHostClient(): HostBridge {
  const adapter = window.__AI_PPT_SIDEBAR_HOST__;
  if (!adapter) {
    const unavailable = async () => {
      throw sidebarError(
        "HOST_SIDEBAR_UNAVAILABLE",
        "当前 Codex 宿主未提供可验证的持久侧边栏入口",
      );
    };
    return {
      connect: unavailable,
      callTool: unavailable,
      updateModelContext: unavailable,
      sendFollowUp: unavailable,
      confirmMission: unavailable,
      getHostEnvironment: () => undefined,
      notifySize() {},
    };
  }
  return {
    async connect(onData?: (data: SurfaceData) => void) {
      await adapter.connect(onData);
    },
    async callTool<K extends keyof ToolContractMap>(
      name: K,
      args: ToolContractMap[K]["input"],
    ) {
      const value = await adapter.callTool(
        name,
        args as unknown as Record<string, unknown>,
      );
      return parseToolOutput(name, value);
    },
    async updateModelContext(context) {
      await adapter.updateModelContext?.(context);
    },
    async sendFollowUp(message) {
      if (!adapter.sendFollowUp) {
        throw new Error("Sidebar follow-up messaging is unavailable");
      }
      await adapter.sendFollowUp(message);
    },
    async confirmMission(args) {
      if (!adapter.confirmMission) {
        throw sidebarError(
          "MISSION_NOT_CONFIRMED",
          "当前侧边栏宿主没有可验证的用户确认动作通道",
        );
      }
      return adapter.confirmMission<MissionConfirmationResult>(args);
    },
    getHostEnvironment() {
      return adapter.getHostEnvironment?.();
    },
    notifySize() {
      adapter.notifySize?.();
    },
  };
}

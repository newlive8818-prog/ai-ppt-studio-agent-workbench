import { Presentation } from "lucide-react";
import { useEffect, useState } from "react";

import { CompactWorkspace } from "./components/CompactWorkspace";
import { StableNavigation } from "./components/StableNavigation";
import type { HostBridge, SpaceId, WidgetData } from "./types";

interface Props {
  initialData?: WidgetData;
  bridge: HostBridge;
  managedConnection?: boolean;
}

interface BrowserReviewOpenResult {
  status?: "opened" | "review-session-ready";
  opened?: boolean;
  openMode?: "host-adapter" | "agent-browser";
  browserAction?: "open-scoped-url";
  url?: string;
}

export function App({ initialData, bridge, managedConnection = false }: Props) {
  const [data, setData] = useState<WidgetData | undefined>(initialData);
  const [activeSpace, setActiveSpace] = useState<SpaceId>(
    initialData?.initialSpace || initialData?.snapshot.workspace.active_space || "overview",
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (managedConnection) return;
    let mounted = true;
    bridge.connect((incoming) => {
      if (!mounted || !("snapshot" in incoming)) return;
      setData(incoming);
      setActiveSpace(incoming.initialSpace || incoming.snapshot.workspace.active_space || "overview");
    }).catch(() => {
      if (mounted && !initialData) setNotice("工作台未能连接 Codex 宿主；项目数据未被修改。");
    });
    return () => { mounted = false; };
  }, [bridge, initialData, managedConnection]);

  useEffect(() => { bridge.notifySize(); }, [bridge, data, activeSpace, notice]);

  if (!data) {
    return (
      <main className="loading-shell" aria-live="polite">
        <div className="loading-mark">PPT</div>
        <h1>正在恢复 AI PPT 项目</h1>
        <p>{notice || "读取同一份项目快照与 revision。"}</p>
      </main>
    );
  }

  const snapshot = data.snapshot;

  async function openReview(reviewType: "content" | "visual") {
    setBusy(true);
    setNotice("正在通过 Codex 内置 Browser 打开完整专业审阅…");
    try {
      const sourceVersion = reviewType === "content"
        ? snapshot.workspace.blueprint.source_version
        : snapshot.workspace.visual.source_version;
      const result = await bridge.callTool<BrowserReviewOpenResult>("open_ai_ppt_browser_review", {
        projectRoot: snapshot.project.project_root,
        reviewType,
        sourceVersion,
      });
      const label = reviewType === "content" ? "内容审阅" : "视觉合同";
      if (result.status === "opened" && result.opened === true) {
        setNotice(`已在 Codex 内置 Browser 打开${label}。`);
      } else if (
        result.status === "review-session-ready" &&
        result.opened === false &&
        result.openMode === "agent-browser" &&
        result.browserAction === "open-scoped-url" &&
        result.url
      ) {
        setNotice(`专业审阅会话已准备，正在交给 Codex Agent 使用内置 Browser 打开${label}；Browser 导航成功前不会显示为已打开。`);
      } else {
        throw new Error("Browser review returned an invalid open result");
      }
    } catch (error) {
      const code = (error as Error & { code?: string }).code;
      setNotice(
        code === "BROWSER_REVIEW_SAVE_UNAVAILABLE"
          ? "Browser 可以阅读但无法可靠保存标记，完整审阅闭环保持阻断。"
          : "Codex 内置 Browser 专业审阅暂未打开；当前项目状态未被修改，可重试。",
      );
    } finally {
      setBusy(false);
    }
  }

  async function continueChat(focus: string) {
    setBusy(true);
    try {
      await bridge.sendFollowUp(`继续 AI PPT 项目：${focus}`);
      setNotice("已把当前焦点提交给 Codex 聊天继续处理。");
    } catch (_error) {
      setNotice("宿主未能自动发起后续对话；项目状态未丢失，请返回 Codex 聊天继续。");
    } finally {
      setBusy(false);
    }
  }

  async function confirmMission() {
    const overview = snapshot.workspace.overview;
    const card = overview.mission_card;
    if (!card || overview.mission_status !== "confirmable") {
      setNotice("当前任务草稿尚未达到可确认状态。请先在 Codex 聊天补充关键信息。");
      return;
    }
    setBusy(true);
    setNotice("正在通过侧边栏宿主验证你的确认动作…");
    try {
      const result = await bridge.confirmMission({
        projectRoot: snapshot.project.project_root,
        expectedRevision: snapshot.revision,
        missionDraftRef: overview.mission_draft_ref || snapshot.missionDraftRef || "",
        materialMode: card.material_state === "materials-provided"
          ? "materials-provided"
          : "no-materials-confirmed",
        materialInventoryRef: card.material_inventory_ref,
      });
      setData((current) => current ? { ...current, snapshot: result.snapshot } : current);
      setNotice(
        card.material_state === "materials-provided"
          ? "任务与当前材料已经你确认，可以开始内容策划。"
          : "任务与当前无材料状态已经你确认，将以方案建议模式开始内容策划。",
      );
    } catch (error) {
      const code = (error as Error & { code?: string }).code;
      setNotice(
        code === "MISSION_NOT_CONFIRMED"
          ? "宿主没有返回可验证的用户确认凭据，任务仍保持待确认。"
          : "任务确认未保存；项目状态未被修改，可重试。",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="compact-app-shell">
      <header className="compact-project-header">
        <div className="compact-brand">
          <span aria-hidden="true"><Presentation size={17} /></span>
          <div><strong>AI PPT Studio</strong><small>{snapshot.project.name}</small></div>
        </div>
        <div className="compact-sync" aria-live="polite">
          <i />revision {snapshot.revision}
        </div>
      </header>
      <StableNavigation
        active={activeSpace}
        items={snapshot.workspace.navigation}
        onChange={setActiveSpace}
      />
      <main className="compact-main">
        <CompactWorkspace
          snapshot={snapshot}
          activeSpace={activeSpace}
          busy={busy}
          onOpenReview={openReview}
          onContinueChat={continueChat}
          onConfirmMission={confirmMission}
        />
        {notice && <p className="compact-notice" role="status">{notice}</p>}
      </main>
    </div>
  );
}

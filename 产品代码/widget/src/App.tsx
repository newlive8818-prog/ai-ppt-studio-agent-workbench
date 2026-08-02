import { useEffect, useMemo, useState } from "react";

import { CognitionMap } from "./components/CognitionMap";
import { BlueprintWorkspace } from "./components/BlueprintWorkspace";
import { ContextInspector } from "./components/ContextInspector";
import { DecisionPanel } from "./components/DecisionPanel";
import { DeliveryWorkspace } from "./components/DeliveryWorkspace";
import { MaterialsWorkspace } from "./components/MaterialsWorkspace";
import { ProjectHeader } from "./components/ProjectHeader";
import { StableNavigation } from "./components/StableNavigation";
import { VisualWorkspace } from "./components/VisualWorkspace";
import type { DecisionResult, HostBridge, SpaceId, WidgetData } from "./types";

interface Props {
  initialData?: WidgetData;
  bridge: HostBridge;
}

export function App({ initialData, bridge }: Props) {
  const [data, setData] = useState<WidgetData | undefined>(initialData);
  const [activeSpace, setActiveSpace] = useState<SpaceId>(initialData?.initialSpace || "overview");
  const [selected, setSelected] = useState("");
  const [feedback, setFeedback] = useState("");
  const [phase, setPhase] = useState<"connecting" | "ready" | "saving" | "saved" | "fallback" | "conflict" | "error">(initialData ? "ready" : "connecting");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let mounted = true;
    bridge.connect((incoming) => {
      if (!mounted) return;
      setData(incoming);
      setActiveSpace(incoming.initialSpace || incoming.snapshot.active_space || "overview");
      setPhase("ready");
    }).catch(() => {
      if (mounted && !initialData) {
        setPhase("error");
        setNotice("工作台未能连接 Codex 宿主。项目数据未被修改，请重新打开。 ");
      }
    });
    return () => { mounted = false; };
  }, [bridge, initialData]);

  useEffect(() => { bridge.notifySize(); }, [bridge, data, notice]);

  const statusLabel = useMemo(() => {
    if (phase === "saving") return "正在保存";
    if (phase === "saved") return "已同步";
    if (phase === "fallback") return "已保存，待对话";
    if (phase === "conflict") return "版本冲突";
    if (phase === "error") return "需要恢复";
    if (phase === "connecting") return "正在连接";
    return "状态已同步";
  }, [phase]);

  if (!data) {
    return (
      <main className="loading-shell" aria-live="polite">
        <div className="loading-mark">PPT</div>
        <h1>正在恢复 AI PPT 项目</h1>
        <p>{notice || "读取上一份有效项目快照，不会依赖浏览器缓存。"}</p>
      </main>
    );
  }

  const snapshot = data.snapshot;

  async function refresh() {
    setNotice("请在 Codex 中重新打开工作台以读取最新项目状态。");
  }

  async function requestFullscreen() {
    try {
      await bridge.requestDisplayMode("fullscreen");
    } catch (_error) {
      setNotice("当前 Codex 宿主不支持全屏；你仍可在紧凑视图完成判断。 ");
    }
  }

  async function submitDecision() {
    if (!selected) return;
    setPhase("saving");
    setNotice("正在先保存项目判断，再交给 Codex 继续处理…");
    try {
      const result = await bridge.callTool("submit_ai_ppt_human_decision", {
        projectRoot: snapshot.project.project_root,
        expectedRevision: snapshot.revision,
        targetRef: snapshot.current_decision.target_ref,
        choice: selected,
        feedback,
      });
      setData({ ...data, snapshot: result.snapshot });
      setPhase("saved");
      setNotice(`已保存为 revision ${result.snapshot.revision}，正在同步给 Codex。`);
      try {
        await bridge.updateModelContext(result.model_context);
        await bridge.sendFollowUp(result.follow_up_message);
        setNotice(`已保存为 revision ${result.snapshot.revision}，并已提交给 Codex 继续处理。`);
      } catch (_hostError) {
        setPhase("fallback");
        setNotice(`判断已保存，但宿主未自动发起后续对话。请返回 Codex 对话继续，项目 revision ${result.snapshot.revision} 不会丢失。`);
      }
      setSelected("");
      setFeedback("");
    } catch (error) {
      const code = (error as Error & { code?: string }).code;
      if (code === "REVISION_CONFLICT") {
        setPhase("conflict");
        setNotice("项目已在其他位置更新。你的选择仍被保留，请刷新后重新提交，系统没有覆盖新版本。 ");
      } else {
        setPhase("error");
        setNotice("判断尚未保存。你的输入仍在当前页面，可以重试或返回 Codex 继续。 ");
      }
    }
  }

  async function runWorkspaceTool(
    name: string,
    args: Record<string, unknown>,
    continueInCodex = true,
  ): Promise<DecisionResult> {
    setPhase("saving");
    setNotice("正在先写入项目，再更新 AI 上下文…");
    try {
      const result = await bridge.callTool<DecisionResult>(name, args);
      setData((current) => current ? { ...current, snapshot: result.snapshot } : current);
      setPhase("saved");
      setNotice(`已保存为 revision ${result.snapshot.revision}。`);
      if (continueInCodex && result.follow_up_message) {
        try {
          await bridge.updateModelContext(result.model_context);
          await bridge.sendFollowUp(result.follow_up_message);
          setNotice(`已保存为 revision ${result.snapshot.revision}，并已提交给 Codex 继续处理。`);
        } catch (_hostError) {
          setPhase("fallback");
          setNotice(`操作已保存，但宿主未自动发起后续对话。请返回 Codex 对话继续，项目 revision ${result.snapshot.revision} 不会丢失。`);
        }
      }
      return result;
    } catch (error) {
      const code = (error as Error & { code?: string }).code;
      if (code === "REVISION_CONFLICT") {
        setPhase("conflict");
        setNotice("项目已在其他位置更新。当前输入仍被保留，请刷新后重新提交，系统没有覆盖新版本。");
      } else if (code === "GATE_BLOCKED") {
        setPhase("error");
        setNotice("当前质量门仍缺少必要证据。项目未被修改，请先补齐页面提示的内容。");
      } else {
        setPhase("error");
        setNotice("操作尚未保存。当前输入仍在页面中，可以重试或返回 Codex 继续。");
      }
      throw error;
    }
  }

  return (
    <div className="app-shell">
      <ProjectHeader projectName={snapshot.project.name} revision={snapshot.revision} status={statusLabel} onFullscreen={requestFullscreen} onRefresh={refresh} />
      <div className="mobile-space-tabs"><StableNavigation active={activeSpace} onChange={setActiveSpace} /></div>
      <div className={`workbench-grid ${activeSpace === "overview" ? "" : "without-inspector"}`}>
        <StableNavigation active={activeSpace} onChange={setActiveSpace} />
        <main className="main-surface">
          {activeSpace === "overview" ? (
            <>
              <section className="conclusion-strip">
                <div>
                  <span>AI 当前结论</span>
                  <h1>{snapshot.cognition_map.outcome_status}，当前焦点是「{snapshot.cognition_map.dialogue_focus}」</h1>
                </div>
                <div className="gate-pill">{snapshot.gate_state.current_gate}<small>当前质量门</small></div>
              </section>
              <CognitionMap snapshot={snapshot} />
              <DecisionPanel decision={snapshot.current_decision} selected={selected} feedback={feedback} submitting={phase === "saving"} onSelected={setSelected} onFeedback={setFeedback} onSubmit={submitDecision} />
            </>
          ) : activeSpace === "materials" && snapshot.space_projections?.materials ? (
            <MaterialsWorkspace
              projectRoot={snapshot.project.project_root}
              revision={snapshot.revision}
              projection={snapshot.space_projections.materials}
              busy={phase === "saving"}
              onRunTool={runWorkspaceTool}
            />
          ) : activeSpace === "blueprint" && snapshot.space_projections?.blueprint ? (
            <BlueprintWorkspace
              projectRoot={snapshot.project.project_root}
              revision={snapshot.revision}
              gateStatus={snapshot.gate_state.gates.G0 || "locked"}
              projection={snapshot.space_projections.blueprint}
              busy={phase === "saving"}
              onRunTool={runWorkspaceTool}
            />
          ) : activeSpace === "visual" && snapshot.space_projections?.visual ? (
            <VisualWorkspace
              bridge={bridge}
              projectRoot={snapshot.project.project_root}
              revision={snapshot.revision}
              gates={snapshot.gate_state.gates}
              projection={snapshot.space_projections.visual}
              busy={phase === "saving"}
              onRunTool={runWorkspaceTool}
            />
          ) : activeSpace === "delivery" && snapshot.space_projections?.delivery ? (
            <DeliveryWorkspace
              bridge={bridge}
              projectRoot={snapshot.project.project_root}
              revision={snapshot.revision}
              projection={snapshot.space_projections.delivery}
              busy={phase === "saving"}
              onRunTool={runWorkspaceTool}
            />
          ) : (
            <section className="phase-placeholder">
              <span>{activeSpace === "materials" ? "Phase B" : activeSpace === "blueprint" ? "Phase B" : activeSpace === "visual" ? "Phase C" : "Phase D"}</span>
              <h1>这个认知空间尚未接通</h1>
              <p>Phase A 只实现项目总览的真实读写闭环。当前页面不会伪造材料、蓝图、视觉或交付状态。</p>
              <button className="secondary-button" type="button" onClick={() => setActiveSpace("overview")}>返回项目总览</button>
            </section>
          )}
          {notice && <div className={`system-notice ${phase}`} role="status">{notice}</div>}
        </main>
        {activeSpace === "overview" && <ContextInspector snapshot={snapshot} />}
      </div>
    </div>
  );
}

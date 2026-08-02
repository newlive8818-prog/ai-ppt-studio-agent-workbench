import { Check, Images, LoaderCircle, PencilRuler, Sparkles, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { DecisionResult, HostBridge, VisualProjection } from "../types";
import { ProjectAssetImage } from "./ProjectAssetImage";
import { SpaceConclusion } from "./SpaceConclusion";


interface Props {
  bridge: HostBridge;
  projectRoot: string;
  revision: number;
  gates: Record<string, string>;
  projection: VisualProjection;
  busy: boolean;
  onRunTool: (
    name: string,
    args: Record<string, unknown>,
    continueInCodex?: boolean,
  ) => Promise<DecisionResult>;
}

export function VisualWorkspace({ bridge, projectRoot, revision, gates, projection, busy, onRunTool }: Props) {
  const initialDirection = projection.selected_direction || projection.recommended_direction || projection.directions[0]?.id || "";
  const [selectedId, setSelectedId] = useState(initialDirection);
  useEffect(() => {
    if (projection.selected_direction) setSelectedId(projection.selected_direction);
  }, [projection.selected_direction]);

  const selected = useMemo(
    () => projection.directions.find((direction) => direction.id === selectedId),
    [projection.directions, selectedId],
  );
  const currentGate: "G1" | "G2" | "G3" | "complete" = gates.G3 === "passed"
    ? "complete"
    : ((["G1", "G2", "G3"] as const).find((gate) => gates[gate] === "open") || "G3");

  async function saveDirection() {
    if (!selected) return;
    await onRunTool(
      "submit_ai_ppt_human_decision",
      {
        projectRoot,
        expectedRevision: revision,
        targetRef: "concept://direction",
        choice: selected.id,
        feedback: `选择视觉方向：${selected.name}`,
      },
      false,
    );
  }

  async function confirmGate(gate: "G1" | "G2" | "G3") {
    await onRunTool(
      "confirm_ai_ppt_gate",
      { projectRoot, expectedRevision: revision, gate },
      true,
    );
  }

  async function requestAction(actionType: string, targetRefs: string[], instructions: string) {
    await onRunTool(
      "request_ai_ppt_agent_action",
      { projectRoot, expectedRevision: revision, actionType, targetRefs, instructions },
      true,
    );
  }

  function primaryAction() {
    if (gates.G0 !== "passed") {
      return <button className="primary-button" type="button" disabled>请先确认内容蓝图</button>;
    }
    if (currentGate === "complete") {
      return <button className="primary-button" type="button" disabled><Check size={16} />视觉实现合同已确认</button>;
    }
    if (currentGate === "G1") {
      if (!projection.directions.length) {
        return <button className="primary-button" type="button" disabled={busy} onClick={() => void requestAction("explore-concepts", ["artifact://visual-brief", "artifact://concept-set"], "基于已确认内容蓝图，用 Image 2 形成至少两个结构不同的高质量视觉方向和关键页样张。")}>{busy ? <LoaderCircle size={16} /> : <Sparkles size={16} />}生成视觉方向</button>;
      }
      if (!projection.selected_direction || projection.selected_direction !== selectedId) {
        return <button className="primary-button" type="button" disabled={busy || !selected} onClick={() => void saveDirection()}><Check size={16} />保存方向 {selectedId}</button>;
      }
      return <button className="primary-button" type="button" disabled={busy} onClick={() => void confirmGate("G1")}><Check size={16} />确认视觉方向并通过 G1</button>;
    }
    if (currentGate === "G2") {
      if (!projection.engineering_samples.length) {
        return <button className="primary-button" type="button" disabled={busy} onClick={() => void requestAction("build-engineering-samples", ["artifact://concept-set", "artifact://engineering-samples"], "使用 Codex Presentations 把关键页构想还原为原生可编辑 PPTX 工程样张，渲染并记录原生元素覆盖率与风险。")}>{busy ? <LoaderCircle size={16} /> : <PencilRuler size={16} />}生成可编辑工程样张</button>;
      }
      return <button className="primary-button" type="button" disabled={busy} onClick={() => void confirmGate("G2")}><Check size={16} />确认工程可行性并通过 G2</button>;
    }
    if (!projection.visual_contract.design_thesis || !projection.scene_graph_coverage) {
      return <button className="primary-button" type="button" disabled={busy} onClick={() => void requestAction("freeze-visual-contract", ["artifact://visual-contract", "artifact://slide-scene-graph"], "把选定方向和工程样张固化为 Visual Contract 与逐页 Scene Graph，明确原生可编辑实现约束。")}>{busy ? <LoaderCircle size={16} /> : <PencilRuler size={16} />}生成视觉实现合同</button>;
    }
    return <button className="primary-button" type="button" disabled={busy} onClick={() => void confirmGate("G3")}><Check size={16} />冻结视觉实现合同并通过 G3</button>;
  }

  return (
    <div className="space-page visual-workspace">
      <SpaceConclusion
        eyebrow="视觉策略结论"
        title="视觉设计"
        summary={projection.visual_brief.design_challenge || "内容蓝图确认后，AI 将先探索视觉方向，再验证可编辑实现。"}
        metric={<><strong>{projection.direction_count}</strong><span>结构方向</span></>}
      />

      <section className="visual-brief-strip">
        <div><span>期望反应</span><strong>{projection.visual_brief.desired_response || "待形成视觉策略"}</strong></div>
        <div><span>设计姿态</span><strong>{projection.visual_brief.design_posture || "待定义"}</strong></div>
        <div><span>硬约束</span><strong>{projection.visual_brief.constraints.join(" · ") || "内容准确、原生可编辑"}</strong></div>
      </section>

      <section className="workspace-section">
        <div className="section-heading"><div><span>第一层 · 视觉探索</span><h2>比较结构不同的视觉方向</h2></div><span className="route-label"><Sparkles size={13} />Image 2 只负责视觉构想</span></div>
        {projection.directions.length ? (
          <div className="direction-grid">
            {projection.directions.map((direction) => (
              <button
                className={`direction-card ${selectedId === direction.id ? "selected" : ""}`}
                type="button"
                key={direction.id}
                aria-label={`选择${direction.name}`}
                onClick={() => setSelectedId(direction.id)}
              >
                <div className="direction-preview">
                  {direction.sample_asset_ref && direction.sample_exists ? (
                    <ProjectAssetImage bridge={bridge} projectRoot={projectRoot} assetRef={direction.sample_asset_ref} alt={`${direction.name}视觉构想`} />
                  ) : <div className="concept-wireframe"><Images size={24} /><span>结构方向 {direction.id}</span></div>}
                  <span className="media-label">Image 2 视觉构想</span>
                </div>
                <div className="direction-copy">
                  <div><span>{direction.id}</span><strong>{direction.name}</strong>{projection.recommended_direction === direction.id && <small>AI 推荐</small>}</div>
                  <p>{direction.thesis}</p>
                  <dl><div><dt>构图</dt><dd>{direction.composition || "待细化"}</dd></div><div><dt>密度</dt><dd>{direction.density || "待细化"}</dd></div></dl>
                  {direction.risk && <em><TriangleAlert size={13} />{direction.risk}</em>}
                </div>
              </button>
            ))}
          </div>
        ) : <div className="empty-state">G0 通过后，使用 Image 2 生成至少两个结构不同的视觉方向。</div>}
      </section>

      {projection.engineering_samples.length > 0 && (
        <section className="workspace-section engineering-section">
          <div className="section-heading"><div><span>第二层 · 工程验证</span><h2>PPTX 工程样张</h2></div><span className="route-label native"><PencilRuler size={13} />Codex Presentations 原生实现</span></div>
          <div className="engineering-grid">
            {projection.engineering_samples.map((sample) => (
              <article className="engineering-card" key={sample.sample_id}>
                <div className="engineering-preview">
                  {sample.render_ref && sample.render_exists ? <ProjectAssetImage bridge={bridge} projectRoot={projectRoot} assetRef={sample.render_ref} alt={`${sample.sample_id}工程样张`} /> : <div className="concept-wireframe"><PencilRuler size={24} /><span>等待渲染</span></div>}
                  <span className="media-label native">PPTX 工程样张</span>
                </div>
                <div><strong>{sample.slide_refs.join(" · ") || sample.sample_id}</strong><p>{sample.notes}</p><span>原生元素 {Math.round((sample.native_element_ratio || 0) * 100)}%</span></div>
              </article>
            ))}
            <aside className="editability-proof">
              <span>工程证据</span>
              <strong>{projection.engineering_summary}</strong>
              <ul>
                {Object.entries(projection.native_coverage).filter(([key]) => key !== "whole_slide_bitmap").map(([key, value]) => <li key={key}><Check size={13} />{key}：{value ? "原生" : "待验证"}</li>)}
                <li><Check size={13} />整页位图：{projection.native_coverage.whole_slide_bitmap === false ? "未使用" : "存在风险"}</li>
              </ul>
            </aside>
          </div>
        </section>
      )}

      {projection.visual_contract.design_thesis && (
        <section className="contract-grid">
          <div className="workspace-section contract-thesis"><span>视觉合同</span><h2>{projection.visual_contract.design_thesis}</h2><p>{projection.scene_graph_coverage} 页场景图</p></div>
          <div className="workspace-section contract-rules"><span>实现边界</span><ul>{projection.visual_contract.editability_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul></div>
          <div className="workspace-section palette-panel"><span>视觉语言</span><div>{Object.entries(projection.visual_contract.palette).map(([name, color]) => <i key={name} title={`${name} ${color}`} style={{ background: color }} />)}</div><p>{projection.visual_contract.layout_rules.join(" · ")}</p></div>
        </section>
      )}

      <section className="visual-primary-action">
        <div><span>{currentGate === "complete" ? "G3 · 已通过" : `${currentGate} · 当前视觉质量门`}</span><h2>{currentGate === "G1" ? "先选定方向，再进入可编辑工程验证" : currentGate === "G2" ? "用真实 PPTX 样张证明构想能够实现" : currentGate === "complete" ? "视觉方向、工程可行性与实现合同已锁定" : "冻结设计规则与逐页实现图"}</h2></div>
        {primaryAction()}
      </section>
    </div>
  );
}

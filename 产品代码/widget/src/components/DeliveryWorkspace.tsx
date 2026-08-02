import { Check, CircleAlert, Download, FileCheck2, LoaderCircle, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import type { DecisionResult, DeliveryProjection, HostBridge } from "../types";
import { GateStrip } from "./GateStrip";
import { ProjectAssetImage } from "./ProjectAssetImage";
import { SlideContactSheet } from "./SlideContactSheet";
import { SpaceConclusion } from "./SpaceConclusion";


interface Props {
  bridge: HostBridge;
  projectRoot: string;
  revision: number;
  projection: DeliveryProjection;
  busy: boolean;
  onRunTool: (
    name: string,
    args: Record<string, unknown>,
    continueInCodex?: boolean,
  ) => Promise<DecisionResult>;
}

const CHECK_LABELS: Record<string, string> = {
  artifact_tool_export: "PPTX 导出",
  external_render: "外部渲染",
  full_size_visual_inspection: "全尺寸视觉检查",
  overflow: "溢出检查",
  pptx_archive: "PPTX 压缩包结构",
  speaker_notes_sources: "备注与来源",
  whole_slide_bitmap: "整页位图",
  native_editable_shapes: "原生可编辑形状",
  replaceable_images: "可替换图片",
};

function checkValue(value: unknown) {
  if (Array.isArray(value)) return value.join(" / ");
  return String(value).replaceAll("_", " ");
}

export function DeliveryWorkspace({ bridge, projectRoot, revision, projection, busy, onRunTool }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selectedRender = projection.renders[selectedIndex] || projection.renders[0];
  const g4Passed = projection.gate_state.gates.G4 === "passed";

  async function requestAction(actionType: "build-pptx" | "qa-render" | "repair-pptx", instructions: string) {
    await onRunTool(
      "request_ai_ppt_agent_action",
      {
        projectRoot,
        expectedRevision: revision,
        actionType,
        targetRefs: ["artifact://presentation-handoff", "artifact://delivery"],
        instructions,
      },
      true,
    );
  }

  async function confirmG4() {
    await onRunTool(
      "confirm_ai_ppt_gate",
      { projectRoot, expectedRevision: revision, gate: "G4" },
      true,
    );
  }

  function primaryAction() {
    if (projection.gate_state.gates.G3 !== "passed") {
      return <button className="primary-button" type="button" disabled>请先通过 G3</button>;
    }
    if (!projection.pptx_exists) {
      return <button className="primary-button" type="button" disabled={busy} onClick={() => void requestAction("build-pptx", "使用 Codex Presentations 按内容蓝图、视觉合同和 Scene Graph 制作原生可编辑 PPTX，并输出逐页渲染。")}>{busy ? <LoaderCircle size={16} /> : <FileCheck2 size={16} />}用 Presentations 制作 PPTX</button>;
    }
    if (projection.qa_status === "failed") {
      return <button className="primary-button" type="button" disabled={busy} onClick={() => void requestAction("repair-pptx", "保留上一份有效构建，使用 Codex Presentations 修复 QA 问题，重新渲染并检查。")}>{busy ? <LoaderCircle size={16} /> : <RefreshCw size={16} />}用 Presentations 修复并重新检查</button>;
    }
    if (projection.qa_status !== "passed") {
      return <button className="primary-button" type="button" disabled={busy} onClick={() => void requestAction("qa-render", "使用 Codex Presentations 渲染完整 PPTX，检查溢出、布局、来源备注、可编辑性和整页位图风险。")}>{busy ? <LoaderCircle size={16} /> : <ShieldCheck size={16} />}渲染并执行完整 QA</button>;
    }
    if (g4Passed) return <button className="primary-button accepted" type="button" disabled><Check size={16} />交付已验收</button>;
    return <button className="primary-button" type="button" disabled={busy} onClick={() => void confirmG4()}><Check size={16} />验收交付并通过 G4</button>;
  }

  const summary = projection.qa_status === "passed"
    ? `可编辑 PPTX、${projection.render_count} 页真实渲染与 QA 证据已齐备，等待最终验收。`
    : projection.pptx_exists
      ? "PPTX 已形成，但完整 QA 尚未通过；系统保留现有成果并等待修复。"
      : "视觉实现合同已确认，等待 Codex Presentations 制作可编辑 PPTX。";

  return (
    <div className="space-page delivery-workspace">
      <SpaceConclusion
        eyebrow="交付状态结论"
        title="制作与交付"
        summary={summary}
        metric={<><strong>{projection.slide_count}</strong><span>交付页面</span></>}
      />
      <GateStrip gates={projection.gate_state.gates} />

      <section className="delivery-evidence-strip">
        <div className={projection.editable ? "passed" : "failed"}><FileCheck2 size={17} /><span>可编辑 PPTX</span><strong>{projection.editable ? "已证明" : "待证明"}</strong></div>
        <div className={projection.render_count ? "passed" : "pending"}><Download size={17} /><span>真实渲染</span><strong>{projection.render_count} 页</strong></div>
        <div className={projection.qa_status === "passed" ? "passed" : "failed"}><ShieldCheck size={17} /><span>{projection.qa_status === "passed" ? "QA 已通过" : "QA 未通过"}</span><strong>{Object.keys(projection.qa_checks).length} 项检查</strong></div>
        <div className={!projection.whole_slide_bitmap ? "passed" : "failed"}><Check size={17} /><span>整页位图</span><strong>{projection.whole_slide_bitmap ? "存在风险" : "未使用"}</strong></div>
      </section>

      {projection.pptx_exists && projection.qa_status === "failed" && (
        <div className="build-preserved"><CircleAlert size={16} /><span>上一份有效 PPTX 与已完成渲染已保留；修复会生成新版本，不会覆盖历史成果。</span></div>
      )}

      {projection.renders.length > 0 && (
        <div className="delivery-visual-grid">
          <section className="render-stage">
            <div className="section-heading"><div><span>当前页</span><h2>全尺寸渲染检查</h2></div><small>{selectedIndex + 1} / {projection.renders.length}</small></div>
            <div className="selected-render">
              {selectedRender?.exists ? <ProjectAssetImage bridge={bridge} projectRoot={projectRoot} assetRef={selectedRender.asset_ref} alt={`第 ${selectedIndex + 1} 页渲染大图`} /> : <span>当前页缺少渲染</span>}
            </div>
          </section>
          <section className="contact-panel">
            <div className="section-heading"><div><span>真实渲染</span><h2>页面接触表</h2></div></div>
            <SlideContactSheet bridge={bridge} projectRoot={projectRoot} renders={projection.renders} selectedIndex={selectedIndex} onSelected={setSelectedIndex} />
          </section>
        </div>
      )}

      <div className="delivery-inspection-grid">
        <section className="workspace-section qa-panel">
          <div className="section-heading"><div><span>质量验证</span><h2>QA 与可编辑性证据</h2></div></div>
          <div className="qa-checks">
            {Object.entries(projection.qa_checks).map(([key, value]) => (
              <div key={key}><span>{CHECK_LABELS[key] || key}</span><strong>{checkValue(value)}</strong></div>
            ))}
          </div>
          {projection.qa_notes.map((note) => <p className="qa-note" key={note}><Check size={13} />{note}</p>)}
          {projection.qa_issues.map((issue) => <p className="qa-issue" key={issue}><CircleAlert size={13} />{issue}</p>)}
        </section>
        <section className="workspace-section delivery-files">
          <div className="section-heading"><div><span>交付文件</span><h2>项目内真实产物</h2></div></div>
          <div><FileCheck2 size={18} /><span>PowerPoint</span><code>{projection.pptx_ref || "尚未生成"}</code></div>
          <div><ShieldCheck size={18} /><span>QA 记录</span><code>{projection.validation_ref || "尚未生成"}</code></div>
          <p>{projection.source_count} 份用户材料已进入来源链。</p>
        </section>
      </div>

      <section className="delivery-primary-action">
        <div><span>{g4Passed ? "G4 已通过" : "G4 · 最终交付门"}</span><h2>{g4Passed ? "当前交付已被用户验收" : "只有 PPTX、渲染、QA 和可编辑性证据同时成立，才算完成"}</h2></div>
        {primaryAction()}
      </section>
    </div>
  );
}

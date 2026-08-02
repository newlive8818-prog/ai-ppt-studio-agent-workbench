import { Check, FilePenLine, LoaderCircle, MessageSquareText } from "lucide-react";
import { useMemo, useState } from "react";

import type { BlueprintProjection, DecisionResult } from "../types";
import { SpaceConclusion } from "./SpaceConclusion";


interface Props {
  projectRoot: string;
  revision: number;
  gateStatus: string;
  projection: BlueprintProjection;
  busy: boolean;
  onRunTool: (
    name: string,
    args: Record<string, unknown>,
    continueInCodex?: boolean,
  ) => Promise<DecisionResult>;
}

export function BlueprintWorkspace({ projectRoot, revision, gateStatus, projection, busy, onRunTool }: Props) {
  const [selectedId, setSelectedId] = useState(projection.slides[0]?.slide_id || "");
  const [showRevision, setShowRevision] = useState(false);
  const [feedback, setFeedback] = useState("");
  const selected = useMemo(
    () => projection.slides.find((slide) => slide.slide_id === selectedId) || projection.slides[0],
    [projection.slides, selectedId],
  );

  async function request(actionType: "generate-blueprint" | "revise-blueprint") {
    await onRunTool(
      "request_ai_ppt_agent_action",
      {
        projectRoot,
        expectedRevision: revision,
        actionType,
        targetRefs: ["artifact://mission", "artifact://content-blueprint"],
        instructions: feedback || "基于用户任务书和材料提炼逐页内容、目标、主张、可见文字、讲解稿及来源。",
      },
      true,
    );
    setFeedback("");
    setShowRevision(false);
  }

  async function confirmG0() {
    await onRunTool(
      "confirm_ai_ppt_gate",
      { projectRoot, expectedRevision: revision, gate: "G0" },
      true,
    );
  }

  return (
    <div className="space-page blueprint-workspace">
      <SpaceConclusion
        eyebrow="内容策划结论"
        title="内容蓝图"
        summary={projection.narrative_thesis || "尚未形成内容蓝图。AI 将先根据任务书和材料组织叙事。"}
        metric={<><strong>{projection.slide_count}</strong><span>规划页面</span></>}
      />
      <div className="content-only-rule">
        <FilePenLine size={17} />
        <span>本阶段只确认内容、证据与叙事；不讨论颜色、布局、配图或视觉评分。</span>
      </div>

      {projection.slides.length ? (
        <>
          <section className="blueprint-meta-grid">
            <div><span>汇报对象</span><strong>{projection.audience || "待确认"}</strong></div>
            <div><span>期望决策</span><strong>{projection.goal || "待确认"}</strong></div>
            <div><span>材料覆盖</span><strong>{projection.source_coverage.referenced}/{projection.source_coverage.available} 份已引用</strong></div>
          </section>
          <div className="blueprint-grid">
            <section className="chapter-panel">
              <div className="section-heading"><div><span>叙事结构</span><h2>章节与逐页框架</h2></div></div>
              <div className="chapter-list">
                {projection.chapters.map((chapter, index) => (
                  <div className="chapter-block" key={`${chapter.title}-${index}`}>
                    <strong><small>{String(index + 1).padStart(2, "0")}</small>{chapter.title}</strong>
                    {chapter.slide_ids.map((slideId) => {
                      const slide = projection.slides.find((item) => item.slide_id === slideId);
                      if (!slide) return null;
                      return (
                        <button className={selected?.slide_id === slideId ? "active" : ""} type="button" key={slideId} onClick={() => setSelectedId(slideId)}>
                          <span>{slideId}</span>{slide.title}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            </section>
            {selected && (
              <section className="slide-inspector">
                <div className="slide-inspector-head"><span>{selected.slide_id} · {selected.role || "页面内容"}</span><strong>{selected.title}</strong></div>
                <dl>
                  <div><dt>页面目标</dt><dd>{selected.purpose}</dd></div>
                  <div><dt>核心主张</dt><dd>{selected.claim}</dd></div>
                  <div><dt>页面文字</dt><dd><ul>{selected.visible_content.map((item) => <li key={item}>{item}</li>)}</ul></dd></div>
                  <div><dt>讲解稿</dt><dd>{selected.speaker_notes}</dd></div>
                  <div><dt>引用依据</dt><dd>{selected.source_refs.join(" · ") || "尚未引用材料"}</dd></div>
                </dl>
              </section>
            )}
          </div>
          <section className="gate-action-panel">
            <div>
              <span>{gateStatus === "passed" ? "G0 已通过" : "等待用户确认"}</span>
              <h2>{gateStatus === "passed" ? "内容已冻结，可以进入视觉构想" : "整体内容是否准确、完整并符合汇报目标？"}</h2>
              <p>确认后才进入视觉设计；后续仍可重新打开 G0，不会删除历史版本。</p>
            </div>
            <div className="gate-actions">
              <button className="secondary-button" type="button" disabled={busy} onClick={() => setShowRevision((value) => !value)}><MessageSquareText size={16} />提出整体修改</button>
              {gateStatus !== "passed" && <button className="primary-button" type="button" disabled={busy} onClick={() => void confirmG0()}><Check size={17} />确认内容蓝图并通过 G0</button>}
            </div>
            {showRevision && (
              <div className="revision-form">
                <label htmlFor="blueprint-feedback">整体修改意见</label>
                <textarea id="blueprint-feedback" rows={4} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="例如：先讲建设必要性，再展开架构；补充现有案例和真实截图引用。" />
                <button className="primary-button" type="button" disabled={busy || !feedback.trim()} onClick={() => void request("revise-blueprint")}><LoaderCircle size={16} />保存意见并交给 Codex 修订</button>
              </div>
            )}
          </section>
        </>
      ) : (
        <section className="empty-blueprint">
          <FilePenLine size={26} />
          <h2>尚未生成逐页内容蓝图</h2>
          <p>AI 将先确定叙事主线、章节、每页目标、主张、可见文字、讲解稿和材料引用。</p>
          <button className="primary-button" type="button" disabled={busy} onClick={() => void request("generate-blueprint")}>
            {projection.active_task ? <LoaderCircle size={16} /> : <FilePenLine size={16} />}
            {projection.active_task ? "AI 正在策划内容" : "开始生成内容蓝图"}
          </button>
        </section>
      )}
    </div>
  );
}

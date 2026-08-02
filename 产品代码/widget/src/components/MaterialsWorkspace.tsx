import { FileText, Link2, LoaderCircle, Plus, Upload, WandSparkles } from "lucide-react";
import { useRef, useState } from "react";

import type { DecisionResult, MaterialsProjection } from "../types";
import { SpaceConclusion } from "./SpaceConclusion";


interface Props {
  projectRoot: string;
  revision: number;
  projection: MaterialsProjection;
  busy: boolean;
  onRunTool: (
    name: string,
    args: Record<string, unknown>,
    continueInCodex?: boolean,
  ) => Promise<DecisionResult>;
}

async function fileBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
  }
  return btoa(binary);
}

function formatBytes(value: number | null) {
  if (!value) return "引用";
  if (value < 1024) return `${value} B`;
  return `${(value / 1024).toFixed(value < 10240 ? 1 : 0)} KB`;
}

export function MaterialsWorkspace({ projectRoot, revision, projection, busy, onRunTool }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [showText, setShowText] = useState(false);
  const [material, setMaterial] = useState("");

  async function requestClassification(expectedRevision: number) {
    return onRunTool(
      "request_ai_ppt_agent_action",
      {
        projectRoot,
        expectedRevision,
        actionType: "classify-materials",
        targetRefs: ["project://sources", "artifact://material-findings"],
        instructions: "自动识别材料用途，提炼可引用事实、案例、图片、冲突与缺口；保留来源定位。",
      },
      true,
    );
  }

  async function addTextOrUrl() {
    const value = material.trim();
    if (!value) return;
    const isUrl = /^https?:\/\//i.test(value);
    const added = await onRunTool(
      "add_ai_ppt_material",
      {
        projectRoot,
        expectedRevision: revision,
        materialType: isUrl ? "url" : "text",
        value,
        label: isUrl ? "用户提供链接" : "用户补充材料",
      },
      false,
    );
    setMaterial("");
    await requestClassification(added.snapshot.revision);
  }

  async function addFiles(files: FileList | null) {
    if (!files?.length) return;
    let expectedRevision = revision;
    for (const file of Array.from(files)) {
      const result = await onRunTool(
        "add_ai_ppt_material",
        {
          projectRoot,
          expectedRevision,
          materialType: "bytes",
          dataBase64: await fileBase64(file),
          filename: file.name,
          mimeType: file.type || "application/octet-stream",
        },
        false,
      );
      expectedRevision = result.snapshot.revision;
    }
    await requestClassification(expectedRevision);
    if (fileInput.current) fileInput.current.value = "";
  }

  return (
    <div className="space-page materials-workspace">
      <SpaceConclusion
        eyebrow="材料认知结论"
        title="材料工作台"
        summary={projection.summary}
        metric={<><strong>{projection.source_count}</strong><span>已接收材料</span></>}
      />

      <section className="intake-panel" aria-label="统一材料入口">
        <div className="intake-copy">
          <WandSparkles size={18} />
          <div>
            <h2>文件、图片、文字和链接都从这里进入</h2>
            <p>无需预先整理目录。系统接收后由 AI 自动识别用途、提炼证据与案例。</p>
          </div>
        </div>
        <div className="intake-actions">
          <input
            ref={fileInput}
            className="sr-only"
            type="file"
            multiple
            aria-label="上传材料文件"
            onChange={(event) => void addFiles(event.target.files)}
          />
          <button className="primary-button compact" type="button" disabled={busy} onClick={() => fileInput.current?.click()}>
            <Upload size={16} />选择文件
          </button>
          <button className="secondary-button" type="button" disabled={busy} onClick={() => setShowText((value) => !value)}>
            <Plus size={16} />粘贴文字或链接
          </button>
        </div>
        {showText && (
          <div className="inline-material-form">
            <label htmlFor="material-text">补充材料</label>
            <textarea
              id="material-text"
              value={material}
              onChange={(event) => setMaterial(event.target.value)}
              placeholder="粘贴会议纪要、补充说明，或输入 https:// 开头的用户提供链接"
              rows={4}
            />
            <button className="primary-button" type="button" disabled={busy || !material.trim()} onClick={() => void addTextOrUrl()}>
              {busy ? <LoaderCircle size={16} /> : <WandSparkles size={16} />}
              添加并自动提炼
            </button>
          </div>
        )}
        <p className="privacy-note">AI 只使用你提供的材料，不会主动搜索客户信息或外部素材。</p>
      </section>

      <section className="workspace-section">
        <div className="section-heading">
          <div><span>已接收材料</span><h2>系统自动分类，不要求用户预先归档</h2></div>
          {projection.active_task && <span className="task-badge"><LoaderCircle size={13} />{projection.active_task.status}</span>}
        </div>
        {projection.sources.length ? (
          <div className="source-table" role="table" aria-label="项目材料">
            {projection.sources.map((source) => (
              <div className="source-row" role="row" key={source.source_id}>
                <span className="source-icon">{source.kind === "url" ? <Link2 size={16} /> : <FileText size={16} />}</span>
                <div className="source-primary"><strong>{source.name}</strong><small>{source.kind} · {formatBytes(source.size_bytes)}</small></div>
                <div className="source-classification"><span>{source.classification}</span><small>{source.purposes.join(" · ") || "等待用途判断"}</small></div>
                <span className={`status-chip ${source.status}`}>{source.status === "usable" ? "可用" : source.status === "partial" ? "部分可用" : "待提炼"}</span>
              </div>
            ))}
          </div>
        ) : <div className="empty-state">添加现有材料后，AI 将在这里形成材料地图。</div>}
      </section>

      <div className="findings-grid">
        <section className="workspace-section">
          <div className="section-heading"><div><span>可引用内容</span><h2>事实、案例与证据</h2></div></div>
          {projection.findings.length ? projection.findings.map((finding) => (
            <article className="finding-card" key={finding.finding_id}>
              <span>{finding.finding_type} · {finding.fact_status}</span>
              <strong>{finding.content}</strong>
              <small>{finding.source_ref} · {finding.locator}</small>
            </article>
          )) : <p className="muted-copy">等待 AI 从当前材料中提炼。</p>}
        </section>
        <section className="workspace-section attention-section">
          <div className="section-heading"><div><span>影响内容蓝图</span><h2>缺口与冲突</h2></div></div>
          {projection.conflicts.concat(projection.gaps).length ? (
            <ul className="attention-list">{projection.conflicts.concat(projection.gaps).map((item) => <li key={item}>{item}</li>)}</ul>
          ) : <p className="muted-copy">当前没有识别到阻断性冲突。</p>}
        </section>
      </div>
    </div>
  );
}

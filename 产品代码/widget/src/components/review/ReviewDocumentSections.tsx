import { Bookmark } from "lucide-react";

import type { GateStatus, ReviewField, ReviewMark } from "../../types";

const FIELD_LABELS: Record<string, string> = {
  title: "标题", audience: "听众", audiences: "听众", goal: "目标", purpose: "页面任务", claim: "核心主张",
  visible_content: "页面文字", speaker_notes: "讲解备注", source_refs: "来源引用", material_refs: "材料引用",
  design_thesis: "设计命题", palette: "色彩系统", typography: "字体系统", layout_rules: "版式规则",
  image_language: "图像语言", editability_rules: "可编辑性规则", communication_goal: "页面目标",
  core_claim: "核心主张", fact_status: "事实身份", visible_copy: "冻结文字", frozen_text: "冻结文字",
  page_family: "页面家族", composition_intent: "构图意图", information_hierarchy: "信息层级",
  reading_order: "阅读顺序", regions: "区域划分", object_relationships: "对象关系", image_selection: "图片选取",
  image_selection_and_crop: "图片选择与裁切", typography_application: "字体应用", color_application: "色彩应用",
  native_bitmap_routing: "原生对象 / 位图边界", editability_requirements: "可编辑性要求", fallbacks: "降级规则",
  allowed_exceptions: "允许例外", acceptance_criteria: "验收条件", acceptance_checks: "验收核对",
  layout_contract: "版式合同", diagram_chart_table_treatment: "图示 / 图表 / 表格策略",
  status: "当前状态", production_route: "正式生产路线", content_blueprint_ref: "内容蓝图引用",
  deck_design_system_ref: "Deck Design System 引用", visual_contract_set_ref: "逐页视觉合同引用",
  anchor_slide_set_ref: "锚点页集合引用", anchor_identity: "锚点页证据身份", deck_framework: "整套 PPT 框架",
  target_evidence_refs: "四目标证据引用", target_evidence_identities: "四目标证据身份",
  internal_review_refs: "内部审查引用", role_runs: "视觉角色运行身份", acceptance_ref: "内容内部通过证据",
  claim_evidence_map: "主张—证据地图", claim_evidence_map_ref: "主张—证据地图引用", draft_ref: "逐页内容版本引用",
  strategy: "售前内容策略", strategy_ref: "售前内容策略引用", argument_map: "整套论证结构",
  slides: "逐页框架", theme_proposition: "主题命题", page_families: "页面家族", composition_grammar: "构图语法",
  typography_tokens: "字体 Token", color_tokens: "色彩 Token", imagery_strategy: "图像策略",
  diagram_strategy: "图示策略", table_strategy: "表格策略", fallback_fonts: "跨平台字体替代",
  forbidden_patterns: "明确禁止", rule_definitions: "规则定义", decision_stage: "客户决策阶段",
  core_tension: "核心矛盾", decision_objective: "期望决策", persuasion_proposition: "说服命题",
  solution_boundary: "方案边界", evidence_requirements: "证据要求", red_lines: "红线", open_issues: "未决事项",
  target_id: "目标标识", operating_system: "操作系统", operating_system_version: "系统版本",
  application: "桌面应用", application_version: "应用版本", font_inventory_ref: "字体清单引用",
  font_substitution_plan_ref: "字体替代方案引用", source_pptx_ref: "源 PPTX 引用", pptx_sha256: "PPTX SHA-256",
  overall_result: "实机结论", evidence_ref: "实机证据引用", display_name: "中文角色名称",
  role_kind: "角色类型", context_pack_version: "Context Pack 版本", tool_pack_version: "工具任务包版本",
  slide_id: "页面标识", order: "页序", chapter: "章节", region_id: "区域标识", expected_outcome: "预期结果",
  criterion_id: "规则标识", level: "规则级别", condition: "适用条件", evidence_method: "证据方法",
};

export function readableLabel(label: string) {
  return FIELD_LABELS[label] || label.replaceAll("_", " ");
}

const STATUS_LABELS: Record<string, string> = {
  passed: "通过", failed: "未通过", missing: "缺失", stale: "过期", locked: "未开放",
  open: "待完成", "user-reviewable": "可审阅", draft: "草稿", "pending-governance": "待专业治理",
  production: "生产角色", review: "独立审查角色", "strict-B": "严格路线 B",
  "must-follow": "必须严格遵守", "minimum-aesthetic": "最低审美要求",
  "minimum-content-quality": "最低内容质量", "reference-implementation": "参考实现",
};

export function statusLabel(status: string | undefined): string {
  if (!status) return "未提供";
  return STATUS_LABELS[status] || status;
}

function isArtifactReference(value: string) {
  return value.startsWith("artifact://");
}

function targetTitle(row: Record<string, unknown>) {
  return `${String(row.operating_system || row.target_id || "未知目标")} · ${String(row.application || "未知应用")}`;
}

function ReviewValue({ value, valueKey = "" }: { value: unknown; valueKey?: string }) {
  if (value === null || value === undefined || value === "") {
    return <p className="review-empty-value">未填写</p>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <p className="review-empty-value">未填写</p>;
    if (value.every((item) => typeof item === "string")) {
      return <ul className="review-value-list">{(value as string[]).map((item, index) => <li key={index}><ReviewValue value={item} /></li>)}</ul>;
    }
    return <div className="review-object-list">{value.map((item, index) => <div className="review-object-item" key={index}><ReviewValue value={item} /></div>)}</div>;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    const isPalette = entries.length > 0 && entries.every(([, child]) => typeof child === "string" && /^#[0-9a-f]{3,8}$/i.test(child));
    if (isPalette) {
      return <div className="review-color-tokens">{entries.map(([key, child]) => <div key={key}><i style={{ background: String(child) }} /><span>{readableLabel(key)}</span><code>{String(child)}</code></div>)}</div>;
    }
    return (
      <dl className="review-data-object">
        {entries.map(([key, child]) => (
          <div className="review-data-row" key={key}>
            <dt>{readableLabel(key)}</dt>
            <dd><ReviewValue value={child} valueKey={key} /></dd>
          </div>
        ))}
      </dl>
    );
  }
  const text = String(value);
  if (isArtifactReference(text)) return <code className="review-artifact-ref">{text}</code>;
  if (valueKey.includes("status") || valueKey.includes("result") || valueKey === "level" || valueKey === "production_route" || valueKey === "role_kind") {
    return <span className={`review-value-status status-${text}`}>{statusLabel(text)}</span>;
  }
  return <p className="review-value-text">{text}</p>;
}

function TargetEvidenceMatrix({ value }: { value: unknown }) {
  if (!Array.isArray(value)) return <ReviewValue value={value} />;
  const rows = value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item));
  return (
    <section className="review-target-evidence" aria-labelledby="target-evidence-title">
      <header>
        <span>同一 PPTX · 四个独立目标</span>
        <h3 id="target-evidence-title">四目标桌面实机证据</h3>
        <p>每个目标分别显示操作系统、桌面应用、字体策略、同一 PPTX 哈希和不可变证据身份；目标之间不做兼容性外推。</p>
      </header>
      <div className="review-target-grid">
        {rows.map((row, index) => {
          const result = String(row.overall_result || "missing");
          const detailKeys = ["target_id", "operating_system_version", "application_version", "font_inventory_ref", "font_substitution_plan_ref", "source_pptx_ref", "evidence_ref"];
          return (
            <article className={`review-target-card result-${result}`} key={String(row.target_id || index)}>
              <div className="review-target-card-head">
                <div><small>目标 {String(index + 1).padStart(2, "0")}</small><strong>{targetTitle(row)}</strong></div>
                <span>{statusLabel(result)}</span>
              </div>
              <div className="review-target-hash"><small>PPTX SHA-256</small><code>{String(row.pptx_sha256 || "未提供")}</code></div>
              <dl className="review-target-details">
                {detailKeys.map((key) => <div key={key}><dt>{readableLabel(key)}</dt><dd><ReviewValue value={row[key]} valueKey={key} /></dd></div>)}
              </dl>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function StrategyFieldValue({ field }: { field: ReviewField }) {
  if (field.label === "target_evidence_identities") return <TargetEvidenceMatrix value={field.value} />;
  if (field.label === "deck_framework") {
    return <section className="review-framework-block"><span>DECK FRAMEWORK</span><h3>整套 PPT 框架</h3><ReviewValue value={field.value} valueKey={field.label} /></section>;
  }
  if (field.label === "anchor_identity") {
    return <section className="review-anchor-identity"><span>ANCHOR SLIDE IDENTITY</span><h3>原生可编辑锚点页证据身份</h3><p>锚点页预览在聊天中发送；这里保留与正式制品一致的可追溯身份。</p><ReviewValue value={field.value} valueKey={field.label} /></section>;
  }
  return <ReviewValue value={field.value} valueKey={field.label} />;
}

function FieldMarkButton({ anchor, label, onMark }: { anchor: string; label?: string; onMark: (anchor: string) => void }) {
  return (
    <button type="button" className="review-field-mark-btn" aria-label={`为字段 ${label || anchor} 添加标记`} onClick={() => onMark(anchor)}>
      <Bookmark size={15} />
    </button>
  );
}

interface SheetProps {
  section: { anchor: string; title: string; fields: ReviewField[] };
  index: number;
  marks: ReviewMark[];
  onMark: (anchor: string) => void;
  status?: GateStatus | string;
  targetEvidenceCount?: number;
}

export function ContentSheet({ section, index, marks, onMark, status = "open" }: SheetProps) {
  const pageNum = String(index + 1).padStart(2, "0");
  const hasMarks = marks.some((mark) => mark.field_anchor.startsWith(section.anchor));
  const slideMarks = marks.filter((mark) => mark.field_anchor.startsWith(section.anchor));
  const metaLabels = new Set(["fact_status", "source_refs", "material_refs", "source", "material", "来源", "素材"]);
  const contentFields = section.fields.filter((field) => !metaLabels.has(field.label));
  const metaFields = section.fields.filter((field) => metaLabels.has(field.label));

  return (
    <article
      className={`review-sheet${hasMarks ? " has-marks" : ""}`}
      id={section.anchor}
      data-page={`S${pageNum}`}
      data-review-page-anchor={section.anchor}
    >
      <div className="review-sheet-index"><div><b>S{pageNum}</b><span>{section.title}</span></div><span className={`sheet-state status-${status}`}>{status === "user-reviewable" || status === "passed" ? "内部审查通过" : "待内部复核"}</span></div>
      <h3>{section.title}</h3>
      <div className="review-sheet-grid">
        <div className="review-field-stack">
          {contentFields.map((field) => (
            <div className="review-field" key={field.anchor} id={field.anchor} data-field-anchor={field.anchor}>
              <span>{readableLabel(field.label)}</span><ReviewValue value={field.value} />
              <FieldMarkButton anchor={field.anchor} label={field.label} onMark={onMark} />
            </div>
          ))}
          {slideMarks.map((mark) => (
            <div className="review-inline-comment" key={mark.mark_id}>
              <div className="review-comment-inline-head"><strong>已保存标记</strong><span>{mark.field_anchor}</span></div>
              <p>{mark.comment}</p>
              {mark.exact_text && <p style={{ color: "#969ca8", fontSize: 10, marginTop: 4 }}>选中: {mark.exact_text}</p>}
            </div>
          ))}
        </div>
        {metaFields.length > 0 && (
          <aside className="review-sheet-meta">
            {metaFields.map((field) => (
              <div className="review-meta-block" key={field.anchor} data-field-anchor={field.anchor}>
                <span>{readableLabel(field.label)}</span><ReviewValue value={field.value} />
              </div>
            ))}
          </aside>
        )}
      </div>
    </article>
  );
}

export function VisualContractSheet({ section, index, onMark, status = "open", targetEvidenceCount = 0 }: SheetProps) {
  const contentLabels = new Set(["title", "visible_content", "visible_copy", "frozen_text", "speaker_notes", "source_refs", "material_refs"]);
  const contractLabels = new Set([
    "page_family", "composition_intent", "information_hierarchy", "reading_order", "regions", "object_relationships",
    "image_selection", "typography_application", "color_application", "native_bitmap_routing", "editability_requirements",
    "fallbacks", "acceptance_criteria", "acceptance_checks", "layout_contract",
  ]);
  const contentFields = section.fields.filter((field) => contentLabels.has(field.label));
  const contractFields = section.fields.filter((field) => contractLabels.has(field.label));
  const otherFields = section.fields.filter((field) => !contentLabels.has(field.label) && !contractLabels.has(field.label));
  const pageNum = `V${String(index + 1).padStart(2, "0")}`;
  const renderField = (field: ReviewField) => (
    <div className="review-contract-field" key={field.anchor} id={field.anchor} data-field-anchor={field.anchor}>
      <span>{readableLabel(field.label)}</span><ReviewValue value={field.value} />
      <FieldMarkButton anchor={field.anchor} label={field.label} onMark={onMark} />
    </div>
  );
  return (
    <article
      className="review-sheet"
      id={section.anchor}
      data-page={pageNum}
      data-review-page-anchor={section.anchor}
    >
      <div className="review-sheet-index"><div><b>{pageNum}</b><span>{section.title}</span></div><span className={`sheet-state status-${status}`}>{status === "passed" ? "合同通过" : "待工程复核"}</span></div>
      <h3>{section.title}</h3>
      <div className="review-contract-two-col">
        <section className="review-contract-column"><h4>冻结内容</h4>{contentFields.map(renderField)}{otherFields.map(renderField)}</section>
        <section className="review-contract-column"><h4>视觉实现合同</h4>{contractFields.map(renderField)}</section>
      </div>
      <div className="review-contract-state">
        <span>G2 四重硬门：{statusLabel(status)}</span>
        <span>{targetEvidenceCount}/4 个桌面目标具有当前证据身份 · 同一 PPTX</span>
      </div>
    </article>
  );
}

export function StrategySection({ fields, onMark }: { fields: ReviewField[]; onMark: (anchor: string) => void }) {
  if (!fields.length) return null;
  return (
    <div className="review-strategy-table">
      {fields.map((field) => (
        <div className={`review-strategy-row${["deck_framework", "anchor_identity", "target_evidence_identities"].includes(field.label) ? " review-strategy-row-featured" : ""}`} key={field.anchor} data-field-anchor={field.anchor}>
          <div className="review-strategy-label">{readableLabel(field.label)}</div><div className="review-strategy-value"><StrategyFieldValue field={field} /></div>
          <FieldMarkButton anchor={field.anchor} label={field.label} onMark={onMark} />
        </div>
      ))}
    </div>
  );
}

export function ArgumentMapSection({ fields, onMark }: { fields: ReviewField[]; onMark: (anchor: string) => void }) {
  const argumentFields = fields.filter((field) => field.label.includes("chapter") || field.label.includes("argument") || field.label.includes("narrative"));
  if (!argumentFields.length) return null;
  return (
    <div className="review-argument-map">
      {argumentFields.slice(0, 3).map((field, index) => (
        <div className="review-argument-stage" key={field.anchor} data-field-anchor={field.anchor}>
          <small>STAGE {String(index + 1).padStart(2, "0")}</small><strong>{readableLabel(field.label)}</strong>
          <div style={{ marginTop: 9 }}><ReviewValue value={field.value} /></div>
          <FieldMarkButton anchor={field.anchor} onMark={onMark} />
        </div>
      ))}
    </div>
  );
}

import { ArrowUpRight, Check, CircleAlert } from "lucide-react";

import type {
  CognitionSpaceProjection,
  ProjectSnapshot,
  SpaceId,
  WorkspacePrimaryAction,
} from "../types";

interface Props {
  snapshot: ProjectSnapshot;
  activeSpace: SpaceId;
  busy: boolean;
  onOpenReview: (reviewType: "content" | "visual") => void;
  onContinueChat: (focus: string) => void;
  onConfirmMission: () => void;
}

const targetLabels = {
  "macos-powerpoint": "macOS PowerPoint",
  "macos-wps": "macOS WPS",
  "windows-powerpoint": "Windows PowerPoint",
  "windows-wps": "Windows WPS",
} as const;

function PrimaryAction({ action, busy, focus, onOpenReview, onContinueChat, onConfirmMission }: {
  action: WorkspacePrimaryAction;
  busy: boolean;
  focus: string;
  onOpenReview: Props["onOpenReview"];
  onContinueChat: Props["onContinueChat"];
  onConfirmMission: Props["onConfirmMission"];
}) {
  if (action.kind === "none") return null;

  const handleClick = () => {
    if (action.kind === "open-visual-review") onOpenReview("visual");
    else if (action.kind === "confirm-mission") onConfirmMission();
    else onContinueChat(focus);
  };

  return (
    <button
      className="compact-primary-action"
      type="button"
      disabled={busy || !action.enabled}
      onClick={handleClick}
    >
      <span>{busy ? "正在处理…" : action.label}</span>
      <ArrowUpRight size={17} />
    </button>
  );
}

function CompactCognitionLine({
  projection,
  eyebrow,
  title,
  judgmentTitle,
  children,
  busy,
  onOpenReview,
  onContinueChat,
  onConfirmMission,
}: {
  projection: CognitionSpaceProjection;
  eyebrow: string;
  title: string;
  judgmentTitle: string;
  children: React.ReactNode;
  busy: boolean;
  onOpenReview: Props["onOpenReview"];
  onContinueChat: Props["onContinueChat"];
  onConfirmMission: Props["onConfirmMission"];
}) {
  return (
    <article className="compact-cognition-line">
      <section className="compact-line-conclusion" data-cognition-step="conclusion">
        <span>{eyebrow}</span>
        <h2>{title}</h2>
        <p>{projection.conclusion}</p>
      </section>
      <section className="compact-line-focus" data-cognition-step="focus-risk">
        <div>
          <h3>当前焦点</h3>
          <p>{projection.focus}</p>
        </div>
        <div className={projection.high_impact_count ? "has-risk" : ""}>
          <h3>当前风险</h3>
          <p>{projection.risk}</p>
        </div>
      </section>
      <section className="compact-line-artifacts" data-cognition-step="artifacts">
        <h3>受影响成果</h3>
        {projection.affected_artifacts.length ? (
          <ul>
            {projection.affected_artifacts.map((reference) => <li key={reference}>{reference}</li>)}
          </ul>
        ) : <p>暂无已绑定成果</p>}
      </section>
      <section className="compact-line-judgment" data-cognition-step="judgment">
        <h3>{judgmentTitle}</h3>
        {children}
      </section>
      <div className="compact-line-action" data-cognition-step="action">
        <PrimaryAction
          action={projection.primary_action}
          busy={busy}
          focus={projection.focus}
          onOpenReview={onOpenReview}
          onContinueChat={onContinueChat}
          onConfirmMission={onConfirmMission}
        />
      </div>
    </article>
  );
}

function Overview({ snapshot, ...actions }: Omit<Props, "activeSpace">) {
  const projection = snapshot.workspace.overview;
  const card = projection.mission_card;
  const needsConfirmation = projection.mission_status === "confirmable"
    && projection.content_identity_mode === "blocked"
    && Boolean(card);
  return (
    <CompactCognitionLine
      projection={projection}
      eyebrow="AI 判断"
      title="AI 当前结论"
      judgmentTitle={needsConfirmation ? "请确认本次汇报任务" : "当前成果"}
      {...actions}
    >
      {needsConfirmation && card ? (
        <div className="mission-confirmation-card" data-testid="mission-confirmation-card">
          <dl>
            <div><dt>汇报对象</dt><dd>{card.primary_audience}</dd></div>
            <div><dt>汇报主题</dt><dd>{card.topic}</dd></div>
            <div><dt>期望判断或行动</dt><dd>{card.desired_judgment_or_action}</dd></div>
            <div>
              <dt>当前材料</dt>
              <dd>
                {card.material_state === "materials-provided"
                  ? card.materials.join("、")
                  : "当前明确无材料"}
              </dd>
            </div>
            <div><dt>关键背景</dt><dd>{card.background.join("；") || "暂无已知背景"}</dd></div>
            <div><dt>限制</dt><dd>{card.constraints.join("；") || "暂无已知限制"}</dd></div>
            <div><dt>禁区</dt><dd>{card.red_lines.join("；") || "暂无已知禁区"}</dd></div>
            <div><dt>仍未知</dt><dd>{card.unknowns.join("；") || "暂无影响内容准确性的未知项"}</dd></div>
          </dl>
          {card.material_state === "no-materials" && (
            <p className="proposal-only-notice">
              <strong>将以方案建议模式继续</strong>
              <span>客户现状只作为诊断假设，方案作为建议，能力与结果待联合验证。</span>
            </p>
          )}
        </div>
      ) : (
        <>
          <p>{projection.delivery_goal}</p>
          <small>{projection.audiences.join("、")}</small>
        </>
      )}
    </CompactCognitionLine>
  );
}

function Materials({ snapshot, ...actions }: Omit<Props, "activeSpace">) {
  const projection = snapshot.workspace.materials;
  return (
    <CompactCognitionLine
      projection={projection}
      eyebrow="材料状态"
      title="材料工作台"
      judgmentTitle="材料提炼"
      {...actions}
    >
      <div className="compact-facts">
        <strong>{projection.source_count} 份可追溯材料</strong>
        <strong>{projection.parsed_count} 份已解析</strong>
        <strong>{projection.failed_count} 份失败</strong>
      </div>
    </CompactCognitionLine>
  );
}

function Blueprint({ snapshot, ...actions }: Omit<Props, "activeSpace">) {
  const projection = snapshot.workspace.blueprint;
  const title = projection.internal_status === "passed"
    ? "内容蓝图已通过内部审查"
    : "内容蓝图正在内部审查";
  return (
    <CompactCognitionLine
      projection={projection}
      eyebrow="内容状态"
      title="内容蓝图"
      judgmentTitle={title}
      {...actions}
    >
      <div className="compact-facts">
        <strong>{projection.slide_count} 页内容已形成</strong>
        <strong>已判断 {projection.completed_page_count} 页</strong>
        <strong>剩余 {projection.remaining_page_count} 页</strong>
      </div>
    </CompactCognitionLine>
  );
}

function Visual({ snapshot, ...actions }: Omit<Props, "activeSpace">) {
  const projection = snapshot.workspace.visual;
  const title = projection.g1_status === "passed" && projection.g2_status === "passed"
    ? "整套视觉合同已通过 G1 / G2"
    : "整套视觉合同正在内部收敛";
  return (
    <CompactCognitionLine
      projection={projection}
      eyebrow="视觉状态"
      title="视觉设计"
      judgmentTitle={title}
      {...actions}
    >
      <div className="compact-facts">
        <strong>G1 {projection.g1_status}</strong>
        <strong>G2 {projection.g2_status}</strong>
        <strong>已保存 {projection.saved_mark_count} 条标记</strong>
      </div>
    </CompactCognitionLine>
  );
}

function Delivery({ snapshot, ...actions }: Omit<Props, "activeSpace">) {
  const projection = snapshot.workspace.delivery;
  const binaryGates = [
    ["业务语义", projection.quality_gates.semantic],
    ["视觉完成度", projection.quality_gates.aesthetic],
    ["排版工程", projection.quality_gates.engineering],
    ["目标软件渲染", projection.quality_gates.target_render],
  ] as const;
  const sent = projection.chat_send.status === "sent";
  return (
    <CompactCognitionLine
      projection={projection}
      eyebrow="制作阶段 · 等待 G4 聊天验收"
      title="制作与交付"
      judgmentTitle="整套成稿质量门"
      {...actions}
    >
      <div className="binary-gate-grid">
        {binaryGates.map(([label, status]) => {
          const passed = status === "passed";
          return (
            <div key={label} data-testid={`binary-gate-${label}`} className={passed ? "passed" : "failed"}>
              {passed ? <Check size={15} /> : <CircleAlert size={15} />}
              <span>{label}</span>
              <strong>{passed ? "通过" : "未通过"}</strong>
            </div>
          );
        })}
      </div>
      <p className="delivery-blocker" data-testid="delivery-blocker">
        <CircleAlert size={15} />{projection.highest_blocker || projection.risk}
      </p>
      <h3>当前发布目标证据</h3>
      <div className="delivery-targets" aria-label="当前发布目标证据">
        {projection.targets.map((target) => (
          <div
            key={target.target_id}
            data-testid={`target-${target.target_id}`}
            data-pptx-sha256={target.pptx_sha256 || undefined}
          >
            <span>{targetLabels[target.target_id]}</span>
            <strong>
              {target.status === "deferred"
                ? "延期 · 当前版本不验收"
                : target.status === "passed"
                  ? target.target_id === "macos-powerpoint"
                    ? "已验证：macOS Microsoft PowerPoint"
                    : `已验证：${targetLabels[target.target_id]}`
                  : "未通过"}
            </strong>
          </div>
        ))}
      </div>
      <dl className="compact-delivery-meta">
        <div><dt>PPTX SHA-256</dt><dd>{projection.hash_identity || "待验证"}</dd></div>
        <div><dt>聊天发送</dt><dd>聊天发送：{sent ? "已发送" : "未发送"}</dd></div>
      </dl>
    </CompactCognitionLine>
  );
}

export function CompactWorkspace(props: Props) {
  if (props.activeSpace === "materials") return <Materials {...props} />;
  if (props.activeSpace === "blueprint") return <Blueprint {...props} />;
  if (props.activeSpace === "visual") return <Visual {...props} />;
  if (props.activeSpace === "delivery") return <Delivery {...props} />;
  return <Overview {...props} />;
}

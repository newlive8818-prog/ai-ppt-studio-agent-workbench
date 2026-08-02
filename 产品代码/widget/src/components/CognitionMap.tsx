import { ArrowDown, CheckCircle2, CircleAlert, Database, Sparkles, Target } from "lucide-react";

import type { ProjectSnapshot } from "../types";

interface Props {
  snapshot: ProjectSnapshot;
}

function Node({ tone, label, title, children, icon: Icon }: { tone: string; label: string; title: string; children: React.ReactNode; icon: typeof Target }) {
  return (
    <section className={`cognition-node ${tone}`}>
      <div className="node-meta"><Icon size={16} /><span>{label}</span></div>
      <h2>{title}</h2>
      <div className="node-body">{children}</div>
    </section>
  );
}

function Connector() {
  return <div className="map-connector" aria-hidden="true"><span /><ArrowDown size={15} /></div>;
}

export function CognitionMap({ snapshot }: Props) {
  const map = snapshot.cognition_map;
  const fact = map.facts[0] as { summary?: string } | undefined;
  const latestDecision = map.confirmed_decisions.at(-1) as { choice?: string } | undefined;
  return (
    <div className="cognition-map" aria-label="AI 交付认知地图">
      <Node tone="goal" label="交付目标" title={map.delivery_goal} icon={Target}>
        <p><strong>主要听众</strong>{map.audiences.length ? map.audiences.join(" · ") : "尚未确认"}</p>
        <p><strong>要解决的问题</strong>{map.problem}</p>
      </Node>
      <Connector />
      <div className="map-evidence-row">
        <Node tone="fact" label="事实" title={fact?.summary || "尚未收到可追溯材料"} icon={Database}>
          <p>来源：用户提供的受管项目材料</p>
        </Node>
        <Node tone="inference" label="AI 推论" title="AI 当前判断" icon={Sparkles}>
          <p>{map.ai_judgment}</p>
        </Node>
      </div>
      <Connector />
      <div className="map-evidence-row">
        <Node tone="confirmed" label="已确认" title={latestDecision?.choice || "已确认决定将随项目持续沉淀"} icon={CheckCircle2}>
          <p>{map.confirmed_decisions.length} 项结构化人工决定</p>
        </Node>
        <Node tone="uncertain" label="待澄清" title="当前不确定性" icon={CircleAlert}>
          <p>{map.uncertainty}</p>
        </Node>
      </div>
      <Connector />
      <section className="outcome-strip">
        <div><span>成果状态</span><strong>{map.outcome_status}</strong></div>
        <div><span>当前质量门</span><strong>{snapshot.gate_state.current_gate}</strong></div>
        <div><span>已形成产物</span><strong>{Object.keys(snapshot.artifacts).length} 类</strong></div>
      </section>
    </div>
  );
}

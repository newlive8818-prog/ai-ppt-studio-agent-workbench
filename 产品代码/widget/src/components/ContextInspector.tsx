import { ArrowUpRight, Braces, Focus, GitBranch } from "lucide-react";

import type { ProjectSnapshot } from "../types";

export function ContextInspector({ snapshot }: { snapshot: ProjectSnapshot }) {
  const map = snapshot.cognition_map;
  return (
    <aside className="context-inspector" aria-label="当前认知焦点">
      <div className="inspector-title"><Focus size={17} /><span>当前认知焦点</span></div>
      <h2>{map.dialogue_focus}</h2>
      <p>这一判断会改变 AI 接下来优先处理的内容范围，但不会静默覆盖已确认版本。</p>
      <div className="inspector-section">
        <span><GitBranch size={15} />影响范围</span>
        <ul>
          {(map.affected_artifacts.length ? map.affected_artifacts : ["project"]).slice(0, 5).map((item) => <li key={item}>{item}</li>)}
        </ul>
      </div>
      <div className="inspector-section">
        <span><Braces size={15} />AI 可见上下文</span>
        <p>项目 revision、当前空间、决定对象、选择与影响范围。</p>
      </div>
      <button type="button" className="text-button">查看来源与版本 <ArrowUpRight size={15} /></button>
    </aside>
  );
}

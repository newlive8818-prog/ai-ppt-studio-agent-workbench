import { Boxes, FileText, LayoutDashboard, PackageCheck, Palette } from "lucide-react";

import type { SpaceId } from "../types";

const spaces: Array<{ id: SpaceId; label: string; icon: typeof LayoutDashboard; phase: string }> = [
  { id: "overview", label: "项目总览", icon: LayoutDashboard, phase: "当前" },
  { id: "materials", label: "材料工作台", icon: Boxes, phase: "Phase B" },
  { id: "blueprint", label: "内容蓝图", icon: FileText, phase: "Phase B" },
  { id: "visual", label: "视觉设计", icon: Palette, phase: "Phase C" },
  { id: "delivery", label: "制作与交付", icon: PackageCheck, phase: "Phase D" },
];

interface Props {
  active: SpaceId;
  onChange: (space: SpaceId) => void;
}

export function StableNavigation({ active, onChange }: Props) {
  return (
    <nav className="stable-navigation" aria-label="AI PPT 认知空间">
      <p className="nav-eyebrow">AI 认知空间</p>
      {spaces.map(({ id, label, icon: Icon, phase }) => (
        <button
          key={id}
          type="button"
          className={active === id ? "nav-item active" : "nav-item"}
          aria-current={active === id ? "page" : undefined}
          aria-label={`${label}，${phase}`}
          onClick={() => onChange(id)}
        >
          <Icon size={19} />
          <span className="nav-label">{label}</span>
          <small>{phase}</small>
        </button>
      ))}
    </nav>
  );
}

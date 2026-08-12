import { Boxes, FileText, LayoutDashboard, PackageCheck, Palette } from "lucide-react";

import type { SpaceId } from "../types";

const icons = {
  overview: LayoutDashboard,
  materials: Boxes,
  blueprint: FileText,
  visual: Palette,
  delivery: PackageCheck,
} satisfies Record<SpaceId, typeof LayoutDashboard>;

interface Props {
  active: SpaceId;
  items: Array<{
    space_id: SpaceId;
    label: string;
    status: string;
    high_impact_count: number;
  }>;
  onChange: (space: SpaceId) => void;
}

export function StableNavigation({ active, items, onChange }: Props) {
  return (
    <nav className="stable-navigation" aria-label="AI PPT 认知空间">
      <p className="nav-eyebrow">AI 认知空间</p>
      {items.map(({ space_id: id, label, status, high_impact_count: highImpactCount }) => {
        const Icon = icons[id];
        return (
        <button
          key={id}
          type="button"
          className={active === id ? "nav-item active" : "nav-item"}
          aria-current={active === id ? "page" : undefined}
          aria-label={`${label}，${status}${highImpactCount ? `，${highImpactCount} 项高影响` : ""}`}
          onClick={() => onChange(id)}
        >
          <Icon size={19} />
          <span className="nav-label">{label}</span>
          <small>{highImpactCount ? `${highImpactCount} 项` : status}</small>
        </button>
        );
      })}
    </nav>
  );
}

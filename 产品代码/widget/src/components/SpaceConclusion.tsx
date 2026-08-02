import type { ReactNode } from "react";


interface Props {
  eyebrow: string;
  title: string;
  summary: string;
  metric?: ReactNode;
}

export function SpaceConclusion({ eyebrow, title, summary, metric }: Props) {
  return (
    <section className="space-conclusion">
      <div>
        <span>{eyebrow}</span>
        <h1>{title}</h1>
        <p>{summary}</p>
      </div>
      {metric && <div className="space-metric">{metric}</div>}
    </section>
  );
}

import { Check, LockKeyhole } from "lucide-react";


const GATES = [
  ["G0", "内容"],
  ["G1", "方向"],
  ["G2", "工程"],
  ["G3", "合同"],
  ["G4", "交付"],
] as const;

export function GateStrip({ gates }: { gates: Record<string, string> }) {
  return (
    <section className="gate-strip" aria-label="G0 到 G4 质量门">
      {GATES.map(([gate, label]) => {
        const status = gates[gate] || "locked";
        return (
          <div className={status} key={gate}>
            <span>{gate}</span>
            <strong>{label}</strong>
            <small>{status === "passed" ? <><Check size={11} />已通过</> : status === "open" ? "待确认" : <><LockKeyhole size={10} />未开放</>}</small>
          </div>
        );
      })}
    </section>
  );
}

import type { RiskReport } from "../types";

const STYLES: Record<string, { bg: string; border: string; text: string }> = {
  SAFE: { bg: "#052e16", border: "#22c55e", text: "#bbf7d0" },
  LOW: { bg: "#172554", border: "#60a5fa", text: "#bfdbfe" },
  MEDIUM: { bg: "#451a03", border: "#fbbf24", text: "#fef3c7" },
  HIGH: { bg: "#431407", border: "#fb923c", text: "#ffedd5" },
  CRITICAL: { bg: "#450a0a", border: "#f87171", text: "#fee2e2" },
};

export function RiskBadge({ risk }: { risk: RiskReport }) {
  const style = STYLES[risk.risk] ?? STYLES.SAFE;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className="px-2 py-0.5 rounded font-medium"
        style={{
          background: style.bg,
          border: `0.5px solid ${style.border}`,
          color: style.text,
        }}
      >
        ⚠ {risk.risk}
      </span>
      <span className="text-gray-500">
        {risk.reason ?? ""}
        {risk.affectedObjects ? ` — ${risk.affectedObjects} objects` : ""}
      </span>
      {risk.blocked && <span className="text-red-400">[BLOCKED]</span>}
    </div>
  );
}

import { ReportResponse } from "../api";

const STYLES: Record<ReportResponse["verdict"], { bg: string; emoji: string; label: string }> = {
  SHIP: { bg: "bg-green-50 border-green-300 text-green-900", emoji: "✅", label: "READY TO SHIP" },
  HOLD: { bg: "bg-red-50 border-red-300 text-red-900", emoji: "🛑", label: "DO NOT SHIP" },
  REVIEW: {
    bg: "bg-amber-50 border-amber-300 text-amber-900",
    emoji: "⚠️",
    label: "REVIEW BEFORE SHIPPING",
  },
};

export default function VerdictBanner({ verdict, reason }: { verdict: ReportResponse["verdict"]; reason: string }) {
  const s = STYLES[verdict];
  return (
    <div className={`rounded-lg border-2 px-6 py-5 ${s.bg}`}>
      <div className="flex items-center gap-3">
        <span className="text-3xl" aria-hidden>
          {s.emoji}
        </span>
        <div>
          <div className="text-xs font-semibold tracking-wider opacity-70">VERDICT</div>
          <div className="text-xl font-bold tracking-tight">{s.label}</div>
        </div>
      </div>
      <p className="mt-3 text-sm">{reason}</p>
    </div>
  );
}

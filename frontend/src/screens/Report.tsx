import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ReportResponse } from "../api";
import VerdictBanner from "../components/VerdictBanner";
import ClusterCard from "../components/ClusterCard";
import DangerousFailureCard from "../components/DangerousFailureCard";

export default function Report() {
  const { runId = "" } = useParams();
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getReport(runId).then(setReport).catch((e) => setError((e as Error).message));
  }, [runId]);

  if (error) return <div className="rounded-md bg-red-50 text-red-800 p-3">{error}</div>;
  if (!report) return <div className="text-slate-500">Loading report…</div>;

  function downloadJSON() {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `preflight-${runId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const successPct = Math.round(report.success_rate * 100);
  const unclearPct = Math.round(report.unclear_rate * 100);
  const avgLatencySec = (report.avg_latency_ms / 1000).toFixed(1);

  return (
    <div className="space-y-6">
      <VerdictBanner verdict={report.verdict} reason={report.verdict_reason} />

      <div className="grid grid-cols-4 gap-4">
        <Stat label="Success rate" value={`${successPct}%`} />
        <Stat label="Total runs" value={report.total_runs.toString()} />
        <Stat label="Avg latency" value={`${avgLatencySec}s`} />
        <Stat label="Unclear" value={`${unclearPct}%`} />
      </div>

      <section>
        <h2 className="text-lg font-semibold mb-3">Top failure modes</h2>
        {report.failure_clusters.length === 0 ? (
          <div className="text-sm text-slate-500">No failure clusters detected.</div>
        ) : (
          <div className="space-y-3">
            {report.failure_clusters.map((c, i) => (
              <ClusterCard key={i} cluster={c} index={i} />
            ))}
          </div>
        )}
      </section>

      {report.most_dangerous_failure && (
        <DangerousFailureCard failure={report.most_dangerous_failure} />
      )}

      <div className="flex gap-3 pt-4 border-t border-slate-200">
        <button
          type="button"
          onClick={downloadJSON}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50"
        >
          Download JSON
        </button>
        <Link
          to="/"
          className="rounded-md bg-sky-600 text-white px-4 py-2 text-sm hover:bg-sky-700"
        >
          Run again
        </Link>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <div className="text-xs text-slate-500 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}

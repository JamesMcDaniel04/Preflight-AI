import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, RunStatus } from "../api";

export default function Progress() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | null = null;

    async function poll() {
      try {
        const s = await api.getStatus(runId);
        if (cancelled) return;
        setStatus(s);
        if (s.status === "complete") {
          if (interval) clearInterval(interval);
          navigate(`/runs/${runId}/report`);
        } else if (s.status === "failed") {
          if (interval) clearInterval(interval);
          setError(s.error ?? "Run failed.");
        }
      } catch (err) {
        if (cancelled) return;
        setError((err as Error).message);
      }
    }

    poll();
    interval = setInterval(poll, 2000);

    return () => {
      cancelled = true;
      if (interval) clearInterval(interval);
    };
  }, [runId, navigate]);

  const pct = status?.progress_pct ?? 0;
  const partial = status?.partial_results;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Running simulation</h1>

      <div>
        <div className="flex justify-between text-sm text-slate-600 mb-1">
          <span>{status?.status === "pending" ? "Generating scenarios…" : `${pct}% complete`}</span>
          <span className="font-mono">{runId.slice(0, 8)}</span>
        </div>
        <div className="h-3 rounded-full bg-slate-200 overflow-hidden">
          <div
            className="h-full bg-sky-500 transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {partial && (
        <div className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-700 mb-2">So far</h2>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-slate-500">Passing</div>
              <div className="text-2xl font-semibold">
                {Math.round(partial.success_rate_so_far * 100)}%
              </div>
            </div>
            <div>
              <div className="text-slate-500">Failures</div>
              <div className="text-2xl font-semibold">{partial.failure_count_so_far}</div>
            </div>
            <div>
              <div className="text-slate-500">Top issue</div>
              <div className="text-sm font-medium pt-2">
                {partial.top_emerging_failure ?? "—"}
              </div>
            </div>
          </div>
          <div className="text-xs text-slate-500 mt-3">
            {partial.scenarios_complete} scenarios classified
          </div>
        </div>
      )}

      {error && <div className="rounded-md bg-red-50 text-red-800 text-sm p-3">{error}</div>}
    </div>
  );
}

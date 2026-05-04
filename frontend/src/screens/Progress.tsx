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
        const next = await api.getStatus(runId);
        if (cancelled) return;
        setStatus(next);
        if (next.status === "complete") {
          if (interval) clearInterval(interval);
          navigate(`/runs/${runId}/report`);
        } else if (next.status === "failed") {
          if (interval) clearInterval(interval);
          setError(next.error ?? "Run failed.");
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      }
    }

    poll();
    interval = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      if (interval) clearInterval(interval);
    };
  }, [navigate, runId]);

  const pct = status?.progress_pct ?? 0;
  const partial = status?.partial_results;
  const completeCount =
    partial?.scenarios_complete ??
    Math.floor(((status?.scenario_count ?? 0) * (status?.progress_pct ?? 0)) / 100);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Running simulation</h1>

      <div>
        <div className="mb-1 flex justify-between text-sm text-slate-600">
          <span>
            Simulating {completeCount} / {status?.scenario_count ?? 0} scenarios
          </span>
          <span className="font-mono">{runId.slice(0, 8)}</span>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-slate-200">
          <div className="h-full bg-sky-500 transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
        <div className="mt-2 text-xs uppercase tracking-wide text-slate-500">
          {status?.run_mode === "multi_turn" ? "Multi-turn simulation" : "Single-turn simulation"}
        </div>
      </div>

      {partial && (
        <div className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">So far</h2>
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
              <div className="pt-2 text-sm font-medium">
                {partial.top_emerging_failure ?? "-"}
              </div>
            </div>
          </div>
          <div className="mt-3 text-xs text-slate-500">
            {partial.scenarios_complete} scenarios classified
          </div>
        </div>
      )}

      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</div>}
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RunSummary } from "../api";

const VERDICT_BADGE: Record<string, string> = {
  SHIP: "border-green-300 bg-green-100 text-green-800",
  HOLD: "border-red-300 bg-red-100 text-red-800",
  REVIEW: "border-amber-300 bg-amber-100 text-amber-800",
};

export default function History() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listRuns().then(setRuns).catch((err) => setError((err as Error).message));
  }, []);

  if (error) return <div className="rounded-md bg-red-50 p-3 text-red-800">{error}</div>;
  if (!runs) return <div className="text-slate-500">Loading runs...</div>;
  if (runs.length === 0) {
    return (
      <div className="text-slate-500">
        No runs yet.{" "}
        <Link to="/" className="text-sky-600 hover:underline">
          Run your first.
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Run history</h1>
      <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
            <tr>
              <th className="px-4 py-2 text-left">Date</th>
              <th className="px-4 py-2 text-left">Prompt</th>
              <th className="px-4 py-2 text-left">Profile</th>
              <th className="px-4 py-2 text-left">Connection</th>
              <th className="px-4 py-2 text-left">Mode</th>
              <th className="px-4 py-2 text-left">N</th>
              <th className="px-4 py-2 text-left">Status</th>
              <th className="px-4 py-2 text-left">Success</th>
              <th className="px-4 py-2 text-left">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => {
              const target =
                run.status === "complete"
                  ? `/runs/${run.run_id}/report`
                  : `/runs/${run.run_id}/progress`;
              return (
                <tr key={run.run_id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                  <td className="max-w-md truncate px-4 py-3">
                    <Link to={target} className="hover:underline">
                      {run.base_prompt_preview}
                    </Link>
                  </td>
                  <td className="px-4 py-3 capitalize text-xs text-slate-600">
                    {(run.test_profile ?? "general").replace(/_/g, " ")}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {run.connection_type === "http_endpoint" && run.endpoint_url
                      ? new URL(run.endpoint_url).host
                      : "Prompt"}
                  </td>
                  <td className="px-4 py-3 capitalize">
                    {run.run_mode === "multi_turn" ? "Multi turn" : "Single turn"}
                  </td>
                  <td className="px-4 py-3">{run.scenario_count}</td>
                  <td className="px-4 py-3 capitalize">{run.status}</td>
                  <td className="px-4 py-3">
                    {run.success_rate != null ? `${Math.round(run.success_rate * 100)}%` : "-"}
                  </td>
                  <td className="px-4 py-3">
                    {run.verdict ? (
                      <span
                        className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${VERDICT_BADGE[run.verdict]}`}
                      >
                        {run.verdict}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">-</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

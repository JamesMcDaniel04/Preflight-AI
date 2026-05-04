import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RunSummary } from "../api";

const VERDICT_BADGE: Record<string, string> = {
  SHIP: "bg-green-100 text-green-800 border-green-300",
  HOLD: "bg-red-100 text-red-800 border-red-300",
  REVIEW: "bg-amber-100 text-amber-800 border-amber-300",
};

export default function History() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listRuns().then(setRuns).catch((e) => setError((e as Error).message));
  }, []);

  if (error) return <div className="rounded-md bg-red-50 text-red-800 p-3">{error}</div>;
  if (!runs) return <div className="text-slate-500">Loading runs…</div>;
  if (runs.length === 0)
    return (
      <div className="text-slate-500">
        No runs yet. <Link to="/" className="text-sky-600 hover:underline">Run your first.</Link>
      </div>
    );

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight mb-4">Run history</h1>
      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
            <tr>
              <th className="text-left px-4 py-2">Date</th>
              <th className="text-left px-4 py-2">Prompt</th>
              <th className="text-left px-4 py-2">N</th>
              <th className="text-left px-4 py-2">Status</th>
              <th className="text-left px-4 py-2">Success</th>
              <th className="text-left px-4 py-2">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => {
              const target =
                r.status === "complete"
                  ? `/runs/${r.run_id}/report`
                  : `/runs/${r.run_id}/progress`;
              return (
                <tr key={r.run_id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 max-w-md truncate">
                    <Link to={target} className="hover:underline">
                      {r.base_prompt_preview}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{r.scenario_count}</td>
                  <td className="px-4 py-3 capitalize">{r.status}</td>
                  <td className="px-4 py-3">
                    {r.success_rate != null ? `${Math.round(r.success_rate * 100)}%` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {r.verdict ? (
                      <span
                        className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${VERDICT_BADGE[r.verdict]}`}
                      >
                        {r.verdict}
                      </span>
                    ) : (
                      <span className="text-slate-400 text-xs">—</span>
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

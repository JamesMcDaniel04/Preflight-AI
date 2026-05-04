import { useState } from "react";
import { api, RerunResponse } from "../api";

export default function RerunButton({
  runId,
  scenarioId,
}: {
  runId: string;
  scenarioId: string | null;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RerunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!scenarioId) return null;

  async function rerun() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.rerunScenario(runId, scenarioId!);
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={rerun}
        disabled={busy}
        className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs hover:bg-slate-50 disabled:bg-slate-100 disabled:text-slate-400"
      >
        {busy ? "Re-running..." : "Re-run scenario"}
      </button>

      {error && <div className="mt-2 text-xs text-red-700">{error}</div>}

      {result && (
        <div className="mt-3 space-y-2 rounded border border-slate-200 bg-slate-50 p-3 text-xs">
          <div className="flex items-center gap-3">
            <span
              className={`inline-block rounded px-2 py-0.5 font-medium ${badgeClass(
                result.classified_as
              )}`}
            >
              {result.classified_as.toUpperCase()}
            </span>
            <span className="text-slate-500">{result.latency_ms} ms</span>
            {result.heuristic_flag && <span className="text-slate-500">flag: {result.heuristic_flag}</span>}
          </div>
          {result.failure_reason && <div className="text-slate-700">{result.failure_reason}</div>}
          {result.transcript && result.transcript.length > 0 ? (
            <div>
              <div className="font-semibold uppercase text-slate-500">New transcript</div>
              <div className="mt-1 space-y-2 rounded border border-slate-200 bg-white p-2">
                {result.transcript.map((message, index) => (
                  <div key={`${message.role}-${index}`}>
                    <div className="text-[10px] font-semibold uppercase text-slate-500">
                      {message.role}
                    </div>
                    <pre className="whitespace-pre-wrap font-mono text-[11px]">{message.content}</pre>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <div className="font-semibold uppercase text-slate-500">New output</div>
              <pre className="mt-1 whitespace-pre-wrap rounded border border-slate-200 bg-white p-2 font-mono text-[11px]">
                {result.output || "(empty)"}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function badgeClass(classifiedAs: RerunResponse["classified_as"]): string {
  if (classifiedAs === "success") return "bg-green-100 text-green-800";
  if (classifiedAs === "failure") return "bg-red-100 text-red-800";
  return "bg-amber-100 text-amber-800";
}

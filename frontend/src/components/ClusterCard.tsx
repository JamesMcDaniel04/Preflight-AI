import { useState } from "react";
import { FailureCluster } from "../api";

export default function ClusterCard({ cluster, index }: { cluster: FailureCluster; index: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="text-sm text-slate-500 mb-0.5">#{index + 1}</div>
          <div className="font-medium text-slate-900">{cluster.label}</div>
        </div>
        <div className="text-right">
          <div className="text-xl font-semibold">{cluster.count}</div>
          <div className="text-xs text-slate-500">cases</div>
        </div>
      </div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="mt-2 text-xs text-sky-600 hover:underline"
      >
        {open ? "Hide example" : "View example"}
      </button>
      {open && (
        <div className="mt-3 space-y-2 text-sm">
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase">Input</div>
            <pre className="mt-1 whitespace-pre-wrap rounded bg-slate-50 p-2 font-mono text-xs">
              {cluster.example_input}
            </pre>
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase">Output</div>
            <pre className="mt-1 whitespace-pre-wrap rounded bg-slate-50 p-2 font-mono text-xs">
              {cluster.example_output}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

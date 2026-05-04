import { DangerousFailure } from "../api";

export default function DangerousFailureCard({ failure }: { failure: DangerousFailure }) {
  return (
    <div className="rounded-md border-2 border-red-300 bg-red-50 p-4 space-y-3">
      <div className="flex items-center gap-2 text-red-800 font-semibold">
        <span aria-hidden>⚠️</span>
        <span>Most Dangerous Failure</span>
      </div>
      <div>
        <div className="text-xs font-semibold text-red-700 uppercase">Input</div>
        <pre className="mt-1 whitespace-pre-wrap rounded bg-white p-2 font-mono text-xs text-slate-800 border border-red-200">
          {failure.input}
        </pre>
      </div>
      <div>
        <div className="text-xs font-semibold text-red-700 uppercase">Output</div>
        <pre className="mt-1 whitespace-pre-wrap rounded bg-white p-2 font-mono text-xs text-slate-800 border border-red-200">
          {failure.output}
        </pre>
      </div>
      <div>
        <div className="text-xs font-semibold text-red-700 uppercase">Why this is dangerous</div>
        <p className="mt-1 text-sm text-red-900">{failure.reason}</p>
      </div>
    </div>
  );
}

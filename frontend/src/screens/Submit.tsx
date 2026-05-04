import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const N_OPTIONS = [50, 100, 250, 500] as const;
const MODEL_OPTIONS = ["gpt-4o-mini", "gpt-4o"] as const;
const DEFAULT_CRITERIA =
  "The agent returns a complete, accurate response without refusing or hallucinating.";

// Linear interp anchors mirroring backend cost.py — kept client-side so the user
// sees an instant estimate without a roundtrip.
const COST_TABLE: Record<number, [number, number]> = {
  50: [0.06, 90],
  100: [0.11, 150],
  250: [0.3, 300],
  500: [0.57, 540],
};

export default function Submit() {
  const navigate = useNavigate();
  const [basePrompt, setBasePrompt] = useState("");
  const [criteria, setCriteria] = useState(DEFAULT_CRITERIA);
  const [n, setN] = useState<number>(100);
  const [model, setModel] = useState<string>(MODEL_OPTIONS[0]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [estCost, estSecs] = useMemo(() => COST_TABLE[n], [n]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.createRun({
        base_prompt: basePrompt,
        success_criteria: criteria,
        scenario_count: n,
        model,
      });
      navigate(`/runs/${res.run_id}/progress`);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Run Preflight</h1>
        <p className="text-slate-600 mt-1">
          Paste your agent's system prompt. We'll generate {n} scenarios across 5 personas and
          tell you if it's safe to ship.
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">Base prompt</label>
        <textarea
          required
          value={basePrompt}
          onChange={(e) => setBasePrompt(e.target.value)}
          rows={6}
          minLength={10}
          maxLength={4000}
          className="w-full rounded-md border border-slate-300 p-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
          placeholder="You are an invoice processing assistant. Given an invoice, extract..."
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Success criteria
          <span className="ml-2 text-slate-400 font-normal">
            What does a "good" response look like?
          </span>
        </label>
        <textarea
          required
          value={criteria}
          onChange={(e) => setCriteria(e.target.value)}
          rows={3}
          minLength={5}
          maxLength={2000}
          className="w-full rounded-md border border-slate-300 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
        />
      </div>

      <div className="flex items-center gap-6">
        <div className="flex-1">
          <label className="block text-sm font-medium text-slate-700 mb-1">Scenarios</label>
          <div className="flex gap-2">
            {N_OPTIONS.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setN(opt)}
                className={`px-3 py-1.5 rounded-md text-sm border transition ${
                  n === opt
                    ? "bg-sky-600 text-white border-sky-600"
                    : "bg-white border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium text-slate-700 mb-1">Model</label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded-md border border-slate-300 p-2 text-sm bg-white"
          >
            {MODEL_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="rounded-md bg-slate-100 px-4 py-3 text-sm text-slate-700">
        Estimated cost: <span className="font-medium">${estCost.toFixed(2)}</span>
        <span className="mx-2 text-slate-400">·</span>
        Estimated time: <span className="font-medium">{Math.round(estSecs / 60)} min</span>
        <span className="ml-2 text-xs text-slate-500">
          (using your OpenAI key — billed by OpenAI directly)
        </span>
      </div>

      {error && <div className="rounded-md bg-red-50 text-red-800 text-sm p-3">{error}</div>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-sky-600 text-white px-5 py-2.5 text-sm font-medium hover:bg-sky-700 disabled:bg-slate-300"
      >
        {submitting ? "Starting…" : "Run Preflight"}
      </button>
    </form>
  );
}

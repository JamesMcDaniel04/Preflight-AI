import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { getAnthropicKey, getOpenAIKey } from "../keyStore";

const N_OPTIONS = [50, 100, 250, 500] as const;
const MODEL_OPTIONS = [
  { value: "gpt-4o-mini", label: "gpt-4o-mini", provider: "openai" },
  { value: "gpt-4o", label: "gpt-4o", provider: "openai" },
  { value: "claude-3-5-sonnet-latest", label: "claude-3-5-sonnet-latest", provider: "anthropic" },
] as const;
const DEFAULT_CRITERIA =
  "The agent returns a complete, accurate response without refusing or hallucinating.";
const COST_TABLE: Record<number, [number, number]> = {
  50: [0.06, 90],
  100: [0.11, 150],
  250: [0.3, 300],
  500: [0.57, 540],
};

function providerForModel(model: string): "openai" | "anthropic" {
  return model.startsWith("claude") ? "anthropic" : "openai";
}

export default function Submit({ onOpenSettings }: { onOpenSettings: () => void }) {
  const navigate = useNavigate();
  const [basePrompt, setBasePrompt] = useState("");
  const [criteria, setCriteria] = useState(DEFAULT_CRITERIA);
  const [n, setN] = useState<number>(100);
  const [model, setModel] = useState<string>(MODEL_OPTIONS[0].value);
  const [runMode, setRunMode] = useState<"single_turn" | "multi_turn">("single_turn");
  const [shipThreshold, setShipThreshold] = useState(0.85);
  const [holdThreshold, setHoldThreshold] = useState(0.7);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openaiKey, setOpenaiKey] = useState<string | null>(() => getOpenAIKey());
  const [anthropicKey, setAnthropicKey] = useState<string | null>(() => getAnthropicKey());

  useEffect(() => {
    function refresh() {
      setOpenaiKey(getOpenAIKey());
      setAnthropicKey(getAnthropicKey());
    }
    window.addEventListener("focus", refresh);
    const id = setInterval(refresh, 1000);
    return () => {
      window.removeEventListener("focus", refresh);
      clearInterval(id);
    };
  }, []);

  const provider = providerForModel(model);
  const requiresAnthropic = provider === "anthropic";
  const hasRequiredKeys = requiresAnthropic
    ? Boolean(openaiKey && anthropicKey)
    : Boolean(openaiKey);
  const missingLabel = requiresAnthropic
    ? "Add both OpenAI and Anthropic keys to continue."
    : "Add an OpenAI key to continue.";
  const [estCost, estSecs] = useMemo(() => COST_TABLE[n], [n]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    if (shipThreshold <= holdThreshold) {
      setError("Ship threshold must be greater than hold threshold.");
      setSubmitting(false);
      return;
    }
    try {
      const res = await api.createRun({
        base_prompt: basePrompt,
        success_criteria: criteria,
        scenario_count: n,
        model,
        run_mode: runMode,
        ship_threshold: shipThreshold,
        hold_threshold: holdThreshold,
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
        <p className="mt-1 text-slate-600">
          Paste your agent's system prompt. We'll generate {n} scenarios across 5 personas and
          tell you if it's safe to ship.
        </p>
      </div>

      {!hasRequiredKeys && (
        <div className="flex items-center justify-between rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm">
          <span className="text-amber-900">{missingLabel}</span>
          <button
            type="button"
            onClick={onOpenSettings}
            className="rounded-md bg-amber-600 px-3 py-1 text-xs text-white hover:bg-amber-700"
          >
            Add keys
          </button>
        </div>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">Base prompt</label>
        <textarea
          required
          value={basePrompt}
          onChange={(event) => setBasePrompt(event.target.value)}
          rows={6}
          minLength={10}
          maxLength={4000}
          className="w-full rounded-md border border-slate-300 p-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
          placeholder="You are an invoice processing assistant. Given an invoice, extract..."
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          Success criteria
          <span className="ml-2 font-normal text-slate-400">
            What does a good response look like?
          </span>
        </label>
        <textarea
          required
          value={criteria}
          onChange={(event) => setCriteria(event.target.value)}
          rows={3}
          minLength={5}
          maxLength={2000}
          className="w-full rounded-md border border-slate-300 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
        />
      </div>

      <div className="flex gap-6">
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium text-slate-700">Scenarios</label>
          <div className="flex gap-2">
            {N_OPTIONS.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setN(opt)}
                className={`rounded-md border px-3 py-1.5 text-sm transition ${
                  n === opt
                    ? "border-sky-600 bg-sky-600 text-white"
                    : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium text-slate-700">Model</label>
          <select
            value={model}
            onChange={(event) => setModel(event.target.value)}
            className="w-full rounded-md border border-slate-300 bg-white p-2 text-sm"
          >
            {MODEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setAdvancedOpen((value) => !value)}
        className="text-sm text-sky-600 hover:underline"
      >
        {advancedOpen ? "Hide advanced options" : "Show advanced options"}
      </button>

      {advancedOpen && (
        <div className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Run mode</label>
            <select
              value={runMode}
              onChange={(event) => setRunMode(event.target.value as "single_turn" | "multi_turn")}
              className="w-full rounded-md border border-slate-300 bg-white p-2 text-sm"
            >
              <option value="single_turn">Single turn</option>
              <option value="multi_turn">Multi turn</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Ship threshold</label>
            <input
              type="number"
              min={0.5}
              max={1}
              step={0.01}
              value={shipThreshold}
              onChange={(event) => setShipThreshold(Number(event.target.value))}
              className="w-full rounded-md border border-slate-300 p-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Hold threshold</label>
            <input
              type="number"
              min={0}
              max={0.99}
              step={0.01}
              value={holdThreshold}
              onChange={(event) => setHoldThreshold(Number(event.target.value))}
              className="w-full rounded-md border border-slate-300 p-2 text-sm"
            />
          </div>
        </div>
      )}

      <div className="rounded-md bg-slate-100 px-4 py-3 text-sm text-slate-700">
        Estimated cost: <span className="font-medium">${estCost.toFixed(2)}</span>
        <span className="mx-2 text-slate-400">|</span>
        Estimated time: <span className="font-medium">{Math.round(estSecs / 60)} min</span>
        <span className="ml-2 text-xs text-slate-500">
          BYOK is local-only in the UI; async runs still pass keys transiently through Redis so the
          worker can complete.
        </span>
      </div>

      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</div>}

      <button
        type="submit"
        disabled={submitting || !hasRequiredKeys}
        className="rounded-md bg-sky-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-sky-700 disabled:bg-slate-300"
      >
        {submitting ? "Starting..." : hasRequiredKeys ? "Run Preflight" : missingLabel}
      </button>
    </form>
  );
}

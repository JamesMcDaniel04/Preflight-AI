import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, TestProfile } from "../api";
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
  const [profiles, setProfiles] = useState<TestProfile[] | null>(null);
  const [profileId, setProfileId] = useState<string>("general");
  // Track which fields the user has personally edited so we don't clobber
  // their text when they switch profiles.
  const [promptDirty, setPromptDirty] = useState(false);
  const [criteriaDirty, setCriteriaDirty] = useState(false);

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

  // Load profile catalog from the backend on mount so the dropdown is always
  // in sync with what the server actually supports.
  useEffect(() => {
    api
      .listProfiles()
      .then((items) => setProfiles(items))
      .catch(() => setProfiles([]));
  }, []);

  // When the user picks a profile, prefill the prompt + criteria with that
  // profile's defaults — but only if they haven't edited those fields yet.
  useEffect(() => {
    if (!profiles) return;
    const chosen = profiles.find((p) => p.id === profileId);
    if (!chosen) return;
    if (!promptDirty) setBasePrompt(chosen.default_base_prompt);
    if (!criteriaDirty) setCriteria(chosen.default_success_criteria);
  }, [profileId, profiles, promptDirty, criteriaDirty]);

  const provider = providerForModel(model);
  // Operator-key model: backend env vars are the source of truth. Local BYOK
  // keys are an optional override. Surface them only as informational.
  const usingOpenAIOverride = Boolean(openaiKey);
  const usingAnthropicOverride = Boolean(anthropicKey);
  const overrideActive =
    (provider === "openai" && usingOpenAIOverride) ||
    (provider === "anthropic" && usingAnthropicOverride);
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
        test_profile: profileId,
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

      {overrideActive && (
        <div className="flex items-center justify-between rounded-md border border-sky-200 bg-sky-50 px-4 py-3 text-sm">
          <span className="text-sky-900">
            Using your own {provider === "anthropic" ? "Anthropic" : "OpenAI"} key from this
            browser. Clear it in Settings to fall back to the server key.
          </span>
          <button
            type="button"
            onClick={onOpenSettings}
            className="rounded-md border border-sky-300 px-3 py-1 text-xs text-sky-800 hover:bg-sky-100"
          >
            Settings
          </button>
        </div>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">Test profile</label>
        <p className="mb-2 text-xs text-slate-500">
          Pick what you want to test. Each profile biases scenario generation toward a specific risk
          surface and prefills a starter prompt + success criteria.
        </p>
        {profiles === null ? (
          <div className="text-sm text-slate-500">Loading profiles…</div>
        ) : (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            {profiles.map((profile) => {
              const active = profile.id === profileId;
              return (
                <button
                  type="button"
                  key={profile.id}
                  onClick={() => setProfileId(profile.id)}
                  className={`rounded-md border px-3 py-2 text-left text-sm transition ${
                    active
                      ? "border-sky-600 bg-sky-50 ring-1 ring-sky-300"
                      : "border-slate-300 bg-white hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-slate-900">{profile.label}</span>
                    {profile.has_scoring_rules && (
                      <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800">
                        regex
                      </span>
                    )}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{profile.description}</div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          Base prompt
          <span className="ml-2 font-normal text-slate-400">
            Prefilled by profile — edit if you have your own agent.
          </span>
        </label>
        <textarea
          required
          value={basePrompt}
          onChange={(event) => {
            setBasePrompt(event.target.value);
            setPromptDirty(true);
          }}
          rows={6}
          minLength={10}
          maxLength={4000}
          className="w-full rounded-md border border-slate-300 p-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
          placeholder="You are an invoice processing assistant. Given an invoice, extract..."
        />
        {promptDirty && (
          <button
            type="button"
            onClick={() => setPromptDirty(false)}
            className="mt-1 text-xs text-sky-600 hover:underline"
          >
            Reset to profile default
          </button>
        )}
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
          onChange={(event) => {
            setCriteria(event.target.value);
            setCriteriaDirty(true);
          }}
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
      </div>

      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</div>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-sky-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-sky-700 disabled:bg-slate-300"
      >
        {submitting ? "Starting..." : "Run Preflight"}
      </button>
    </form>
  );
}

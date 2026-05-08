import { getAnthropicKey, getOpenAIKey } from "./keyStore";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
const CSRF_COOKIE_NAME = "preflight_csrf";

export type User = {
  id: string;
  email: string;
};

export type AuthResponse = {
  user: User | null;
};

export type CreateRunRequest = {
  base_prompt: string;
  success_criteria: string;
  scenario_count: number;
  model: string;
  run_mode: "single_turn" | "multi_turn";
  test_profile: string;
  ship_threshold: number;
  hold_threshold: number;
};

export type TestProfile = {
  id: string;
  label: string;
  description: string;
  default_base_prompt: string;
  default_success_criteria: string;
  has_scoring_rules: boolean;
};

export type CreateRunResponse = {
  run_id: string;
  estimated_cost_usd: number;
  estimated_seconds: number;
};

export type PartialResults = {
  scenarios_complete: number;
  success_rate_so_far: number;
  failure_count_so_far: number;
  top_emerging_failure: string | null;
};

export type RunStatus = {
  run_id: string;
  run_mode: "single_turn" | "multi_turn";
  scenario_count: number;
  status: "pending" | "running" | "complete" | "failed";
  progress_pct: number;
  partial_results: PartialResults | null;
  error: string | null;
};

export type FailureCluster = {
  label: string;
  count: number;
  example_scenario_id: string | null;
  example_input: string;
  example_output: string;
};

export type DangerousFailure = {
  scenario_id: string | null;
  input: string;
  output: string;
  reason: string;
};

export type RerunResponse = {
  new_scenario_id: string;
  input: string;
  output: string;
  transcript: Array<{ role: string; content: string }> | null;
  latency_ms: number;
  classified_as: "success" | "failure" | "unclear";
  failure_reason: string | null;
  heuristic_flag: string | null;
};

export type ReportResponse = {
  run_id: string;
  base_prompt: string;
  success_criteria: string;
  model: string;
  run_mode: "single_turn" | "multi_turn";
  test_profile: string;
  ship_threshold: number;
  hold_threshold: number;
  success_rate: number;
  total_runs: number;
  avg_latency_ms: number;
  unclear_rate: number;
  failure_clusters: FailureCluster[];
  most_dangerous_failure: DangerousFailure | null;
  verdict: "SHIP" | "HOLD" | "REVIEW";
  verdict_reason: string;
  generated_at: string;
};

export type RunSummary = {
  run_id: string;
  created_at: string;
  base_prompt_preview: string;
  scenario_count: number;
  model: string;
  run_mode: "single_turn" | "multi_turn";
  test_profile: string;
  status: RunStatus["status"];
  progress_pct: number;
  success_rate: number | null;
  verdict: ReportResponse["verdict"] | null;
};

function readCookie(name: string): string | null {
  const parts = document.cookie.split(";").map((part) => part.trim());
  const match = parts.find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=", 2)[1]) : null;
}

async function request<T>(
  path: string,
  init?: RequestInit & { sendProviderKeys?: boolean }
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  const method = (init?.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = readCookie(CSRF_COOKIE_NAME);
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  if (init?.sendProviderKeys) {
    const openai = getOpenAIKey();
    const anthropic = getAnthropicKey();
    if (openai) headers["X-OpenAI-Key"] = openai;
    if (anthropic) headers["X-Anthropic-Key"] = anthropic;
  }
  const { sendProviderKeys: _omit, ...fetchInit } = init ?? {};
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    ...fetchInit,
    headers,
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      msg = data.detail ?? msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getMe: () => request<AuthResponse>("/api/auth/me"),
  signup: (email: string, password: string) =>
    request<AuthResponse>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<AuthResponse>("/api/auth/logout", { method: "POST" }),
  listProfiles: () => request<TestProfile[]>("/api/profiles"),
  createRun: (body: CreateRunRequest) =>
    request<CreateRunResponse>("/api/runs", {
      method: "POST",
      body: JSON.stringify(body),
      sendProviderKeys: true,
    }),
  getStatus: (runId: string) => request<RunStatus>(`/api/runs/${runId}/status`),
  getReport: (runId: string) => request<ReportResponse>(`/api/runs/${runId}/report`),
  listRuns: () => request<RunSummary[]>("/api/runs"),
  rerunScenario: (runId: string, scenarioId: string) =>
    request<RerunResponse>(`/api/runs/${runId}/scenarios/${scenarioId}/rerun`, {
      method: "POST",
      sendProviderKeys: true,
    }),
};

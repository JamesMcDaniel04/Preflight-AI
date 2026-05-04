const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export type CreateRunRequest = {
  base_prompt: string;
  success_criteria: string;
  scenario_count: number;
  model: string;
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
  status: "pending" | "running" | "complete" | "failed";
  progress_pct: number;
  partial_results: PartialResults | null;
  error: string | null;
};

export type FailureCluster = {
  label: string;
  count: number;
  example_input: string;
  example_output: string;
};

export type DangerousFailure = {
  input: string;
  output: string;
  reason: string;
};

export type ReportResponse = {
  run_id: string;
  base_prompt: string;
  success_criteria: string;
  model: string;
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
  status: RunStatus["status"];
  progress_pct: number;
  success_rate: number | null;
  verdict: ReportResponse["verdict"] | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      msg = data.detail ?? msg;
    } catch {
      /* swallow */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  createRun: (body: CreateRunRequest) =>
    request<CreateRunResponse>("/api/runs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getStatus: (runId: string) => request<RunStatus>(`/api/runs/${runId}/status`),
  getReport: (runId: string) => request<ReportResponse>(`/api/runs/${runId}/report`),
  listRuns: () => request<RunSummary[]>("/api/runs"),
};

# Preflight AI

> Upload your AI agent or prompt. We run it 500 times and tell you whether it's safe to ship.

Preflight AI is a pre-deployment failure-intelligence tool for LLM agents. It generates varied scenarios across five user personas, runs your agent against each one, classifies the outputs, clusters the failures, surfaces the most dangerous one, and emits a deterministic **SHIP / HOLD / REVIEW** verdict.

This is the MVP — single-flow, no accounts, BYOK.

---

## What's in the box

- **Backend** — FastAPI + SQLAlchemy (SQLite) + Celery (Redis broker) + scikit-learn for KMeans clustering. OpenAI client for chat + embeddings.
- **Frontend** — Vite + React + TypeScript + Tailwind. Four screens: Submit, Progress, Report, History.
- **Pipeline** — generates ~N scenarios per run, applies a deterministic heuristic pre-filter (saves ~30% of classifier calls), runs Stage-2 LLM classification on the rest, clusters failures with embeddings + KMeans, and asks the LLM to identify the single most dangerous failure.

---

## Quickstart (local dev)

### 1. Configure your API key

```bash
cd backend
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
```

### 2. Start Redis + worker + API + UI

You can run everything via Docker Compose:

```bash
docker compose up --build
```

Or run them separately:

```bash
# Terminal 1 — Redis
docker run --rm -p 6379:6379 redis:7-alpine

# Terminal 2 — API
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Celery worker (optional; API falls back to threads if no broker)
cd backend && source .venv/bin/activate
celery -A celery_app worker --loglevel=info

# Terminal 4 — Frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and submit a run.

---

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

Includes deterministic unit tests for the heuristic filter, verdict computation, persona allocation, and cost estimation, plus an end-to-end pipeline smoke test that mocks LLM calls.

---

## API

| Endpoint | Description |
|---|---|
| `POST /api/runs` | Create a run. Returns `{run_id, estimated_cost_usd, estimated_seconds}`. |
| `GET /api/runs/{id}/status` | Poll progress. Returns `partial_results` once 25/50/75% milestones cross. |
| `GET /api/runs/{id}/report` | Final report — verdict, success rate, failure clusters, most dangerous failure. |
| `GET /api/runs` | Last 20 runs with verdict badges. |

---

## Verdict thresholds

| Condition | Verdict |
|---|---|
| `success_rate >= 0.85` and no dangerous failure | **SHIP** |
| `success_rate < 0.70` or any dangerous failure | **HOLD** |
| otherwise | **REVIEW** |

Hardcoded for the MVP; configurable in v1.1.

---

## Deploy

- **Backend**: deploy `backend/` to Railway (Docker template). Provision Redis. Set `OPENAI_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `ALLOW_ORIGINS` env vars. Run two services from the same image: web (`uvicorn app.main:app`) and worker (`celery -A celery_app worker`).
- **Frontend**: deploy `frontend/` to Vercel. Set `VITE_API_BASE` to your Railway URL.

---

## Cost reality check

| N scenarios | Approx cost |
|---|---|
| 50 | $0.06 |
| 100 | $0.11 |
| 250 | $0.30 |
| 500 | $0.57 |

Heuristic pre-filter eliminates ~30% of classification calls. Numbers above assume `gpt-4o-mini`.

---

## What's not in the MVP

- No auth / accounts.
- No per-scenario rerun endpoint.
- No configurable verdict thresholds.
- No multi-agent simulation.
- BYOK from frontend (currently env-var only) — designed for, not implemented.

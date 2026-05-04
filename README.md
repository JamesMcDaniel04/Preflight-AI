# Preflight AI

> Upload your AI agent or prompt. We run it 500 times and tell you whether it's safe to ship.

Preflight AI is a pre-deployment failure-intelligence tool for LLM agents. It generates varied scenarios across five user personas, runs your agent against each one, classifies the outputs, clusters the failures, surfaces the most dangerous one, and emits a deterministic **SHIP / HOLD / REVIEW** verdict.

This repo now includes:

- Email/password auth with JWT session cookies and per-user run ownership
- Local-only BYOK settings for OpenAI and Anthropic
- Per-run verdict threshold overrides
- Single-turn and multi-turn simulation modes
- Debug reruns for report-linked failure scenarios

## Stack

- Backend: FastAPI, SQLAlchemy, SQLite, Celery, Redis, scikit-learn
- Frontend: React, Vite, TypeScript, Tailwind
- Providers: OpenAI chat + embeddings, Anthropic chat

## Quickstart

### 1. Configure backend env

```bash
cd backend
cp .env.example .env
```

Set at least:

- `SESSION_SECRET` to a long random string
- `OPENAI_API_KEY` if you want server-side fallback for OpenAI calls
- `ANTHROPIC_API_KEY` if you want server-side fallback for Anthropic calls

Frontend BYOK is also supported, so server provider keys are optional for local use.

### 2. Start Redis, API, worker, and frontend

```bash
docker compose up --build
```

Or run them separately:

```bash
# Terminal 1
docker run --rm -p 6379:6379 redis:7-alpine

# Terminal 2
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 3
cd backend
source .venv/bin/activate
celery -A celery_app worker --loglevel=info

# Terminal 4
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, create an account, sign in, open Settings, and add your provider keys.

## BYOK behavior

- OpenAI and Anthropic keys entered in the UI are stored only in browser `localStorage`.
- The frontend sends them per request as `X-OpenAI-Key` and `X-Anthropic-Key`.
- Keys are not stored in the application database.
- Async Celery runs still pass keys transiently through the Redis task payload so the worker can complete the run.
- Anthropic simulation runs still require an OpenAI key for embeddings, clustering, and dangerous-failure analysis.

## Run modes

- `single_turn`: one generated user input, one agent response, classify that output
- `multi_turn`: one generated opening message plus a hidden user goal, then a fixed three-reply dialogue, classified on the full transcript

## Auth and API

Session auth uses an httpOnly JWT cookie. State-changing endpoints also require a CSRF token header that the frontend bootstraps from `GET /api/auth/me`.

Core endpoints:

- `GET /api/auth/me`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/runs`
- `GET /api/runs/{id}/status`
- `GET /api/runs/{id}/report`
- `GET /api/runs`
- `POST /api/runs/{id}/scenarios/{scenario_id}/rerun`

## Tests

Backend:

```bash
cd backend
.venv/bin/pytest -q
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run build
```

The backend suite covers auth, CSRF, ownership, BYOK requirements, verdict thresholds, rerun exclusion from report math, multi-turn transcripts, and an authenticated API smoke test with mocked LLM calls.

## Deploy

- Backend: deploy `backend/` as the API service and a second worker service from the same image.
- Frontend: deploy `frontend/` to Vercel and set `VITE_API_BASE`.
- Production backend env should set `COOKIE_SECURE=true` and a strong `SESSION_SECRET`.
- Set `ALLOW_ORIGINS` to the deployed frontend origin.

## Notes

- Thresholds are configurable per run, not globally.
- Runs are private to the authenticated owner.
- Report reruns are debug-only and do not mutate the original run verdict or aggregate metrics.

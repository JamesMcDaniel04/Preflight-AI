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

## Deploy (Railway + Vercel)

Target architecture:

- **Vercel** — static frontend (`frontend/`), built by Vite.
- **Railway** — three services in one project: `api` (FastAPI), `worker` (Celery), and Railway plugins for `redis` and `postgres`.

### A. Railway backend

Prerequisite: install the Railway CLI and authenticate.

```bash
brew install railway     # or: npm i -g @railway/cli
railway login
```

#### 1. Create the project + plugins

```bash
cd backend
railway init                  # create a new project, name it "preflight"
railway add --database postgres
railway add --database redis
```

This provisions Redis and Postgres and exposes `DATABASE_URL` and `REDIS_URL` as project variables that any service can reference. (On older Railway CLIs the flag was `--plugin`; current CLI uses `--database`. Run `railway add --help` if either fails.)

#### 2. Create the **api** service

In the Railway dashboard for the project, create a new service from the `backend/` directory. Settings:

| Setting | Value |
|---|---|
| Builder | Dockerfile (auto-detected via `backend/railway.json`) |
| Start command | (leave default — `uvicorn app.main:app --host 0.0.0.0 --port 8000`) |
| Healthcheck path | `/health` (already in `railway.json`) |

Set these environment variables (use `${{Redis.REDIS_URL}}` / `${{Postgres.DATABASE_URL}}` to reference plugin URLs):

```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
SESSION_SECRET=<openssl rand -hex 32>
COOKIE_SECURE=true
ALLOW_ORIGINS=https://<your-vercel-domain>.vercel.app
DEFAULT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
MAX_CONCURRENT_LLM_CALLS=5
# Optional server-side fallback keys (frontend BYOK works without these):
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

Deploy: `railway up` from `backend/`, or push to a connected GitHub branch.

#### 3. Create the **worker** service

Add a second service from the same `backend/` directory. Identical to the api service except:

| Setting | Value |
|---|---|
| Start command | `celery -A celery_app worker --loglevel=info --concurrency=2` |
| Healthcheck path | (leave blank) |

Use the **same** environment variables as the api service so the worker reads the same Postgres + Redis. (In Railway you can copy variables from one service to another via "Reference Variable.")

#### 4. Verify

```bash
curl https://<your-api-service>.up.railway.app/health
# {"ok": true}
```

### B. Vercel frontend

```bash
cd frontend
npm i -g vercel              # if you don't have it
vercel link                  # links to a Vercel project, picks org
```

Project settings — auto-detected from `frontend/vercel.json`:

| Setting | Value |
|---|---|
| Framework | Vite |
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `dist` |

One env var on the project:

```bash
VITE_API_BASE=https://<your-api-service>.up.railway.app
```

Deploy:

```bash
vercel --prod
```

After the first deploy, take the resulting Vercel domain and set it as `ALLOW_ORIGINS` on the Railway api service (and worker, if you mirrored). Cookies require an exact origin match.

### C. Post-deploy smoke test

1. Open the Vercel URL.
2. Sign up.
3. Open Settings → paste your OpenAI key.
4. Run a small N=10 single-turn run with a known-good prompt.
5. Confirm verdict appears, history shows the run, JSON download works.

### D. Common gotchas

- **CSRF / cookie failure** — frontend and backend on different origins must use `COOKIE_SECURE=true` (forces `SameSite=None`); browsers reject `SameSite=Lax` cookies on cross-site fetches.
- **`ALLOW_ORIGINS` missing the Vercel preview domain** — add wildcards or each preview origin explicitly if you use preview deploys.
- **Worker starts before Postgres is reachable** — Railway sometimes orders services oddly on first deploy; restart the worker after Postgres is up.
- **`DATABASE_URL` from Railway uses `postgresql://`** — `app/db.py` rewrites this to `postgresql+psycopg://` automatically; no action needed.

## Notes

- Thresholds are configurable per run, not globally.
- Runs are private to the authenticated owner.
- Report reruns are debug-only and do not mutate the original run verdict or aggregate metrics.

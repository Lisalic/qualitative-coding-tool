# Getting Started

## Prerequisites

- Python 3 with `pip`, for the FastAPI backend.
- Node.js with `npm`, for the Vite/React frontend.
- A running PostgreSQL instance.
- An [OpenRouter](https://openrouter.ai/) API key, for the six AI-backed tools (Filter Data, Generate Codebook, Apply Codebook, Compare Codebooks, Compare Codings, Summarize Coding). Not needed to import, browse, or view data.

## Install

```bash
make install          # both backend + frontend
make install-backend  # pip install -r backend/requirements.txt into .venv
make install-frontend # npm install in frontend/
```

A `.venv` at the repo root (used by the Makefile) and a `backend/venv` may both exist locally — both are gitignored; prefer `.venv` to match the Makefile.

## Configure

Create `backend/.env` with:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` (or `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`/`PGDATABASE`) | PostgreSQL connection |
| `JWT_SECRET_KEY` | Signs the hand-rolled HMAC-SHA256 JWTs issued on login/register — see [architecture.md#auth](architecture.md#auth) |
| `OPENROUTER_API_KEY` | Only needed by backend-side scripts/tests that call OpenRouter directly; the app's own AI tools take a per-request key from the browser, not this variable |

Create `frontend/.env` (optional) with:

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Base URL the frontend's `axios`/`fetch` clients call — see `frontend/src/api.js` |

## Run

Backend (from the repo root, so `backend.app.*` imports resolve):

```bash
.venv/bin/python -m uvicorn backend.app.main:app --reload
```

Frontend:

```bash
cd frontend && npm run dev
```

## First-run walkthrough

1. Register an account at `/register`, or log in at `/login` if one already exists — see [Authentication](tools/authentication.md).
2. Set your OpenRouter API key in the navbar (top of every page) — required before any AI tool will run.
3. Create a project from the home page — see [Projects](tools/projects.md).
4. Import a `.zst` dataset into that project — see [Import Data](tools/import-data.md).
5. Optionally filter the raw data down to a subset — see [Filter Data](tools/filter-data.md).
6. Generate a codebook from the raw or filtered data — see [Generate Codebook](tools/generate-codebook.md).
7. Apply the codebook to produce coded output — see [Apply Codebook](tools/apply-codebook.md).
8. Compare codebooks/codings or summarize the coding output, as needed.

The full pipeline and how each stage depends on the previous one is diagrammed in [workflow.md](workflow.md#end-to-end-workflow).

## Tests

Frontend (Vitest — covers `frontend/src/lib/**` and `frontend/src/api.js`, pure logic, no component/DOM tests):

```bash
cd frontend && npm run test:run
```

Backend (pytest — unit tests run against in-memory SQLite and mocked engines, no real Postgres needed):

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/python -m pytest -q
```

Opt-in integration tests under `tests/backend/integration/` need a real throwaway Postgres and are excluded by default; run them explicitly with `pytest -m integration` once `DATABASE_URL` points at a disposable database.

## Lint / build

```bash
cd frontend && npm run lint
cd frontend && npm run build
```

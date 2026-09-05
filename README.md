# dCortex Agentic Crew Ops Advisor — Sarvam Backend

Hackathon-ready FastAPI backend using the supplied synthetic dCortex Air dataset and deterministic legality engine. Sarvam-105B is only the natural-language/tool-orchestration layer.

## Setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `SARVAM_API_KEY`.

## Run

```bash
uvicorn backend.main:app --reload
```

From the repository root. API docs: `http://localhost:8000/docs`

## Test

```bash
pytest -q
```

## Demo

POST `/api/chat` with:

`Captain C-1042 called in sick for 15 September — what should I do?`

With Sarvam configured, the agent will call deterministic tools. Without a key, the local fallback demonstrates the main C-1042 path.

## Data safety

Only supplied `data/*.json` files are included. `internal/held_out_scenarios.json` is intentionally excluded.

## React integration

Send:

```json
POST /api/chat
{"message":"Captain C-1042 called in sick for 15 September. What should I do?"}
```

Response shape:

```json
{"answer":"..."}
```

For UI cards, call `/api/disruptions/analyze`, `/api/replacements/find`, and `/api/recommendations/rank` directly; these return deterministic structured results.

## Important

The included `data/` was regenerated from the supplied `generate.py` (seed 42) because the library contained the supplied generator/README but not the raw JSON archive in the active runtime. No new airline facts were authored. `internal/held_out_scenarios.json` is not included.

## Frontend

The included `frontend/` is a React + TypeScript + Vite control-center UI wired to the FastAPI endpoints.

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:5173` while the backend is running on `http://localhost:8000`.

### Sarvam AI

Set `SARVAM_API_KEY` in the backend `.env`. The agent uses Sarvam's `sarvam-105b` chat completion with native tool calling. The LLM selects tools and explains results; deterministic tools/rules remain authoritative.

Official docs: https://docs.sarvam.ai/api/api-guides-tutorials/chat-completion/overview

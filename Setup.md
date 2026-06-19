# Distributed Agentic Microgrid System

> **Work in progress** — This is an active research/simulation prototype, not production-ready software. APIs, agent behavior, Docker layout, and auth flows may change.

Multi-agent microgrid control: orchestration agents (**microgrid**, **control**, **research**, **monitor**), KQML over mTLS, RAG documentation search, MCP grid state, SQLite audit instrumentation, and a React chat UI.

The **Monitor Agent** reviews Control Agent decisions (audit trail + structured decisions + KQML), flags issues for operators, and sends advisory KQML feedback to Control and Microgrid agents.

## What works today

| Component | Status |
|-----------|--------|
| Docker stack (Redis, Keycloak, orchestration agents, MCP grid state) | Runnable |
| RAG + `src/chat_server.py` (Gemini ADK agents) | Runnable on host |
| `src/demo_chat_simple.py` (mock agents, no Gemini) | Runnable |
| React chat UI | Runnable; expects API on port **8002** |
| SQLite audit (`GlobalInstrumentationPlugin`) | Wired for ADK agents + chat |

## Project layout

```
microgrid_agent.py   control_agent.py   research_agent.py   monitor_agent.py   # ADK agents (repo root)
src/
  shared/            # config, auth, KQML, RAG, state, mTLS, audit plugins
  shared/docs/       # RAG knowledge base (markdown)
  shared/certs/      # mTLS cert generation — see README there
  mcp_servers/       # MCP grid state server
  microgrid_ui/      # React chat frontend
  chat_server.py     # Full chat API (ADK + RAG + instrumentation)
  demo_chat_simple.py
  setup_chat.py
  tests/
docker-compose.yml
Setup.md
```

## Prerequisites

- Python 3.11+
- Node.js 18+ (UI)
- Docker & Docker Compose (multi-agent stack)
- [Gemini API key](https://aistudio.google.com/apikey) for ADK agents and `src/chat_server.py`

## Quick start — chat UI with real agents

```bash
cp .env.example .env          # set GEMINI_API_KEY and Keycloak vars
pip install -r requirements.txt
python3 src/setup_chat.py         # optional: warm ChromaDB from src/shared/docs

python3 src/chat_server.py        # listens on http://localhost:8002
# another terminal:
cd src/microgrid_ui && npm install && npm start
```

Open http://localhost:3000. Select **Microgrid**, **Research**, or **Monitor** agent. `GET http://localhost:8002/alerts` lists operator alerts.

**Port note:** Docker **control-agent** binds host **8001**. Run `src/chat_server.py` on **8002** (default) so it does not conflict with Compose.

## Quick start — mock demo (no Gemini)

```bash
pip install fastapi uvicorn pydantic
python3 src/demo_chat_simple.py   # default port 8001 — UI is hard-coded to 8002
```

For the React UI with the mock API, either run the demo on 8002 (`python3 -c "from src.demo_chat_simple import run_demo_server; run_demo_server(8002)"`) or use `src/chat_server.py` above.

## Full stack (Docker)

```bash
cp .env.example .env
cd src/shared/certs && ./generate_certs.sh generate   # first time only
docker compose up -d
```

**Compose services:** `redis`, `keycloak`, `microgrid-agent`, `control-agent`, `monitor-agent`, `researcher-agent`, `mcp-grid-state`.

| Service | Host ports (approx.) |
|---------|----------------------|
| Keycloak | 8080 |
| control-agent | 8001, 8444 |
| researcher-agent | 8002, 8445 |
| microgrid-agent | 8000, 8443 |
| monitor-agent | 8006, 8446 |
| mcp-grid-state | 8010 |

Run `src/chat_server.py` on the **host** for the UI unless you add it as a Compose service.

## Environment

Copy `.env.example` to `.env`.

| Variable | Required |
|----------|----------|
| `GEMINI_API_KEY` | Yes (ADK agents) |
| `KEYCLOAK_CLIENT_SECRET` | Yes when `AUTH_MODE=local` |
| `AUTH_MODE` | `local` (Keycloak) or `cloud` (Google) |

`JWT_SECRET` is **not** used; auth is OIDC via Keycloak or Google.

## Audit / instrumentation (SQLite)

ADK agents use `LoggingPlugin` + `GlobalInstrumentationPlugin` when `ENABLE_LOCAL_INSTRUMENTATION=true` (default in Docker). Events go to `audit_trail.db` (shared volume across agents).

- **Docker:** `AUDIT_DB_PATH=/app/audit_trail.db`
- **Chat server:** same path on host; each `/chat` call sets a `request_id` for correlation

```bash
python3 src/tests/test_instrumentation_plugin.py
```

## Tests

### Quick run (no Gemini, no Docker agents required)

```bash
python3 src/tests/test_structure.py
python3 src/tests/test_instrumentation_plugin.py
python3 src/tests/test_agent_messaging.py --skip-llm
python3 src/test_kqml_mcp_integration.py
```

### Test suites

| Script | What it checks |
|--------|----------------|
| `src/tests/test_structure.py` | Repo layout and key file contents (no network) |
| `src/tests/test_instrumentation_plugin.py` | SQLite audit plugin writes and reads |
| `src/tests/test_agent_messaging.py` | KQML, Redis, inform delivery, optional Gemini, optional Docker `/health` |
| `src/test_kqml_mcp_integration.py` | KQML create/parse, grid state, audit DB, agent interface helpers |

### `test_agent_messaging.py` layers

Run in order; later layers skip gracefully when dependencies are missing.

1. **KQML round-trip** — 12 inform messages across all orchestration agent pairs (`microgrid`, `control`, `researcher`, `monitor`). Always runs; no external deps.
2. **Redis control → monitor** — `record_control_decision` then `list_control_decisions`. Requires Redis (`docker compose up -d redis` or local Redis on port 6379). Skips if Redis is unavailable.
3. **KQML inform delivery** — monitor → control and monitor → microgrid via `deliver_kqml_inform`. Always runs (HTTP delivery is optional).
4. **ADK / Gemini round-trip** — one natural-language prompt per orchestration agent. Requires `GEMINI_API_KEY` in `.env`. Skipped with `--skip-llm`; fails instead of skipping with `--require-llm`.
5. **HTTP health** — `GET /health` on each Compose service. Skips per-service when that container is not running. Start full stack with `docker compose up -d` to exercise all endpoints.

| Service | Health URL |
|---------|------------|
| microgrid-agent | `http://127.0.0.1:8000/health` |
| control-agent | `http://127.0.0.1:8001/health` |
| researcher-agent | `http://127.0.0.1:8002/health` |
| monitor-agent | `http://127.0.0.1:8006/health` |
| mcp-grid-state | `http://127.0.0.1:8010/health` |

### Flags

```bash
python3 src/tests/test_agent_messaging.py              # default: run LLM tests if GEMINI_API_KEY is set
python3 src/tests/test_agent_messaging.py --skip-llm   # skip layer 4 (no Gemini API calls)
python3 src/tests/test_agent_messaging.py --require-llm  # fail if GEMINI_API_KEY is missing
```

### Full integration (Gemini + Docker)

```bash
cp .env.example .env    # set GEMINI_API_KEY
docker compose up -d
python3 src/tests/test_agent_messaging.py --require-llm
```

### Tool schema sanity check (microgrid-agent)

Verifies ADK tool declarations are valid for Gemini (no unsupported `additional_properties`):

```bash
GEMINI_API_KEY=dummy AUTH_MODE=local python3 -c "
import sys
from pathlib import Path
_root = Path('.').resolve()
for _p in (_root / 'src', _root):
    sys.path.insert(0, str(_p))
from google.adk.tools import FunctionTool
from microgrid_agent import microgrid_agent
for t in microgrid_agent.tools:
    fn = t if callable(t) else getattr(t, 'func', t)
    decl = FunctionTool(fn)._get_declaration()
    assert 'additional_properties=True' not in str(decl.parameters)
print('OK:', len(microgrid_agent.tools), 'tools')
"
```

## Knowledge base

RAG docs: `src/shared/docs/` (`grid_standards.md`, `best_practices.md`, `past_decisions.md`). Reload via `src/setup_chat.py` or on `src/chat_server` startup.

## Known gaps (WIP)

- UI auth uses a placeholder `demo-token`; production path needs Keycloak tokens wired in the UI.
- Monitor auto-review on every control decision requires Control to call `record_control_decision` and Monitor to be invoked (not a background daemon yet).
- No cloud deployment or production hardening.

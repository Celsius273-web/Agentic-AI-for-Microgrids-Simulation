# Distributed Agentic Microgrid System

> **Work in progress** — This is an active research/simulation prototype, not production-ready software. APIs, agent behavior, Docker layout, and auth flows may change. Domain agents (solar, wind, battery, load) exist as code but are not fully wired into the running stack.

Multi-agent microgrid control: orchestration agents (**microgrid**, **control**, **research**, **monitor**), KQML over mTLS, RAG documentation search, MCP grid state, SQLite audit instrumentation, and a React chat UI.

The **Monitor Agent** reviews Control Agent decisions (audit trail + structured decisions + KQML), flags issues for operators, and sends advisory KQML feedback to Control and Microgrid agents.

## What works today

| Component | Status |
|-----------|--------|
| Docker stack (Redis, Keycloak, orchestration agents, MCP grid state) | Runnable |
| RAG + `chat_server.py` (Gemini ADK agents) | Runnable on host |
| `demo_chat_simple.py` (mock agents, no Gemini) | Runnable |
| React chat UI | Runnable; expects API on port **8002** |
| SQLite audit (`GlobalInstrumentationPlugin`) | Wired for ADK agents + chat |
| Domain agents (`solar_agent.py`, etc.) | Stub / not in Compose |

## Project layout

```
microgrid_agent.py   control_agent.py   research_agent.py   monitor_agent.py
shared/              # config, auth, KQML, RAG, state, mTLS, audit plugins
shared/docs/         # RAG knowledge base (markdown)
shared/certs/        # mTLS cert generation — see README there
mcp_servers/         # MCP grid state server
microgrid_ui/        # React chat frontend
chat_server.py       # Full chat API (ADK + RAG + instrumentation)
demo_chat_simple.py  # Mock chat API (no ChromaDB / Gemini)
docker-compose.yml   # Redis, Keycloak, agents, mcp-grid-state
```

## Prerequisites

- Python 3.11+
- Node.js 18+ (UI)
- Docker & Docker Compose (multi-agent stack)
- [Gemini API key](https://aistudio.google.com/apikey) for ADK agents and `chat_server.py`

## Quick start — chat UI with real agents

```bash
cp .env.example .env          # set GEMINI_API_KEY and Keycloak vars
pip install -r requirements.txt
python3 setup_chat.py         # optional: warm ChromaDB from shared/docs

python3 chat_server.py        # listens on http://localhost:8002
# another terminal:
cd microgrid_ui && npm install && npm start
```

Open http://localhost:3000. Select **Microgrid**, **Research**, or **Monitor** agent. `GET http://localhost:8002/alerts` lists operator alerts.

**Port note:** Docker **control-agent** binds host **8001**. Run `chat_server.py` on **8002** (default) so it does not conflict with Compose.

## Quick start — mock demo (no Gemini)

```bash
pip install fastapi uvicorn pydantic
python3 demo_chat_simple.py   # default port 8001 — UI is hard-coded to 8002
```

For the React UI with the mock API, either run the demo on 8002 (`python3 -c "from demo_chat_simple import run_demo_server; run_demo_server(8002)"`) or use `chat_server.py` above.

## Full stack (Docker)

```bash
cp .env.example .env
cd shared/certs && ./generate_certs.sh generate   # first time only
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

Run `chat_server.py` on the **host** for the UI unless you add it as a Compose service.

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
python3 tests/test_instrumentation_plugin.py
```

## Tests

```bash
python3 tests/test_structure.py
python3 tests/test_instrumentation_plugin.py
```

## Knowledge base

RAG docs: `shared/docs/` (`grid_standards.md`, `best_practices.md`, `past_decisions.md`). Reload via `setup_chat.py` or on `chat_server` startup.

## Known gaps (WIP)

- UI auth uses a placeholder `demo-token`; production path needs Keycloak tokens wired in the UI.
- Control → domain agent commands are partly stubbed.
- Monitor auto-review on every control decision requires Control to call `record_control_decision` and Monitor to be invoked (not a background daemon yet).
- No cloud deployment or production hardening.

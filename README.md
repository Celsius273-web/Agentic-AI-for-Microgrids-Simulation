# Distributed Agentic Microgrid System

Multi-agent microgrid control stack: orchestration agents (microgrid, control, research, **monitor**), optional domain agents (solar, wind, battery, load), KQML messaging over mTLS, RAG-backed documentation search, and a React chat UI.

The **Monitor Agent** reviews every Control Agent decision (audit trail + structured decisions + KQML), flags issues for human operators via chat, and sends advisory KQML feedback to Control and Microgrid agents.

## Project layout

```
*.py (repo root)     # Orchestration agents (incl. monitor_agent.py, control_agent.py)
shared/              # Config, auth, KQML, RAG, state, mTLS helpers
shared/docs/         # Markdown knowledge base for RAG
shared/certs/        # mTLS certificate generation (see README there)
mcp_servers/         # MCP grid state server
microgrid_ui/        # React chat frontend
demo_chat_simple.py  # Chat API demo (no ChromaDB / Gemini required)
chat_server.py       # Full chat API (ADK agents + RAG)
docker-compose.yml   # Redis, Keycloak, agent containers
```

## Prerequisites

- Python 3.11+
- Node.js 18+ (for the UI)
- Docker & Docker Compose (full multi-agent stack)
- [Gemini API key](https://aistudio.google.com/apikey) for production agents and `chat_server.py`

## Quick start (demo UI)

No ML stack required; uses mock agents and a small in-memory knowledge base.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn pydantic

python3 demo_chat_simple.py
# In another terminal:
cd microgrid_ui && npm install && npm start
```

Open http://localhost:3000. The UI posts to `http://localhost:8002/chat` (run `python3 chat_server.py`). Select **Monitor Agent** for oversight; `GET /alerts` lists operator alerts. Docker **control-agent** uses host port **8001** — do not run chat on 8001 while Compose is up.

## Full stack (Docker)

```bash
cp .env.example .env   # set GEMINI_API_KEY
docker compose up -d
```

Generate mTLS certs before first run if needed: see [shared/certs/README.md](shared/certs/README.md).

Optional chat API with real agents and RAG (run on host or add a compose service):

```bash
pip install -r requirements.txt
python3 setup_chat.py    # initialize ChromaDB from shared/docs
python3 chat_server.py
```

## Environment

Copy `.env.example` to `.env`. Required variable: `GEMINI_API_KEY`. See the example file for Keycloak vs Google Cloud auth options.

## Audit / instrumentation (SQLite)

All ADK agents use `LoggingPlugin` plus `GlobalInstrumentationPlugin` when `ENABLE_LOCAL_INSTRUMENTATION=true` (default in Docker). Events are written to `audit_trail.db` (shared volume across agents).

- **Container agents:** set `AUDIT_DB_PATH=/app/audit_trail.db` in `docker-compose.yml`
- **Chat server:** same DB path on the host; each `/chat` call sets `request_id` for correlation
- **Console audit lines:** `enable_console_audit=True` only in agent `__main__` (not chat)

```bash
python3 tests/test_instrumentation_plugin.py
```

## Tests

```bash
python3 tests/test_structure.py
python3 tests/test_instrumentation_plugin.py
```

Integration tests that need a running Docker stack are kept local-only (see `.gitignore`).

## Knowledge base

Operational docs for RAG live in `shared/docs/` (`grid_standards.md`, `best_practices.md`, `past_decisions.md`). Reload via `setup_chat.py` or on `chat_server` startup.

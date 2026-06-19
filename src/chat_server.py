import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent
_src = Path(__file__).resolve().parent
for _p in (_src, _repo):
    _entry = str(_p)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.adk.runners import InMemoryRunner

from microgrid_agent import microgrid_agent
from research_agent import researcher_agent
from monitor_agent import monitor_agent
from shared.auth import verify_request
from shared.audit_context import begin_audit_invocation, clear_audit_invocation
from shared.control_decisions import list_operator_alerts
from shared.rag import initialize_rag_system
from shared.runner_plugins import CHAT_AGENT_PROFILES, plugins_for_chat_agent

_DOCS_DIR = str(Path(__file__).resolve().parent / "shared" / "docs")

CHAT_AGENTS = {
    "microgrid": microgrid_agent,
    "researcher": researcher_agent,
    "monitor": monitor_agent,
}

_runners: Dict[str, InMemoryRunner] = {}


class ChatRequest(BaseModel):
    message: str
    agent: str = "microgrid"


class ChatResponse(BaseModel):
    response: str
    agent: str
    timestamp: str
    request_id: str


def get_or_create_runner(agent_key: str) -> InMemoryRunner:
    """One runner per chat agent; plugins write to shared audit_trail.db."""
    if agent_key not in _runners:
        if agent_key not in CHAT_AGENTS:
            raise ValueError(f"Unknown agent: {agent_key}")
        _runners[agent_key] = InMemoryRunner(
            agent=CHAT_AGENTS[agent_key],
            plugins=plugins_for_chat_agent(agent_key),
        )
    return _runners[agent_key]


def build_chat_app() -> FastAPI:
    app = FastAPI(title="Microgrid Chat Server")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup_event():
        print("Initializing RAG system...")
        result = initialize_rag_system(_DOCS_DIR)
        if result["status"] == "success":
            print(f"RAG ready: {result['load_result']['loaded_count']} chunks")
        else:
            print(f"RAG init issue: {result.get('error', 'unknown')}")

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "microgrid-chat",
            "agents": list(CHAT_AGENT_PROFILES.keys()),
            "instrumentation": True,
        }

    @app.get("/alerts")
    async def operator_alerts(limit: int = 20) -> Dict[str, Any]:
        return list_operator_alerts(limit=limit, open_only=True)

    @app.post("/chat", response_model=ChatResponse)
    async def chat_endpoint(
        request: ChatRequest,
        claims: Dict[str, Any] = Depends(verify_request),
    ) -> ChatResponse:
        if request.agent not in CHAT_AGENT_PROFILES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent: {request.agent}. Choose from {list(CHAT_AGENT_PROFILES)}",
            )

        request_id = begin_audit_invocation(
            source="chat_server",
            oidc_claims=claims,
        )
        try:
            runner = get_or_create_runner(request.agent)
            response = await runner.invoke(request.message)

            if hasattr(response, "content"):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            return ChatResponse(
                response=response_text,
                agent=request.agent,
                timestamp=datetime.now(timezone.utc).isoformat(),
                request_id=request_id,
            )
        except Exception as e:
            print(f"Chat endpoint error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Agent communication failed: {str(e)}",
            ) from e
        finally:
            clear_audit_invocation()

    @app.post("/command")
    async def command(
        payload: Optional[Dict[str, Any]] = None,
        claims: Dict[str, Any] = Depends(verify_request),
    ) -> Dict[str, Any]:
        body = payload or {}
        return {
            "status": "success",
            "command": body.get("command"),
            "result": "Command received",
            "auth_account": claims.get("agent_id", "unknown"),
        }

    return app


def run_chat_server(port: int = 8002) -> None:
    """Run chat API (default 8002 to avoid Docker control-agent on 8001)."""
    app = build_chat_app()
    print(f"Microgrid chat server on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    result = initialize_rag_system(_DOCS_DIR)
    if result["status"] == "success":
        print(f"RAG ready: {result['load_result']['loaded_count']} chunks")
    run_chat_server()

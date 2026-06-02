import ssl
from typing import Any, Dict, Optional

import uvicorn
from fastapi import Depends, FastAPI

from shared.auth import verify_request
from shared.config import (
    AGENT_ID,
    CA_CERT,
    MTLS_SERVER_PORT,
    SERVER_CERT,
    SERVER_KEY,
    VERIFY_PEER_CERTS,
)


def build_agent_app(agent_id: str) -> FastAPI:
    app = FastAPI(title=f"{agent_id}-server")

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "healthy", "agent_id": agent_id}

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


def run_agent_server(agent_id: Optional[str] = None) -> None:
    resolved_agent_id = agent_id or AGENT_ID or "unknown-agent"
    app = build_agent_app(resolved_agent_id)

    print(f"STARTING {resolved_agent_id.upper()} WITH mTLS")
    print("=" * 70)
    print(f"Agent ID: {resolved_agent_id}")
    print(f"HTTPS Port: {MTLS_SERVER_PORT}")
    print("mTLS Enabled: true")
    print(f"Server cert: {SERVER_CERT}")
    print(f"CA cert: {CA_CERT}")
    print(f"Peer verification: {VERIFY_PEER_CERTS}")
    print("=" * 70)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=MTLS_SERVER_PORT,
        ssl_certfile=SERVER_CERT,
        ssl_keyfile=SERVER_KEY,
        ssl_ca_certs=CA_CERT,
        ssl_cert_reqs=ssl.CERT_REQUIRED if VERIFY_PEER_CERTS else ssl.CERT_NONE,
    )

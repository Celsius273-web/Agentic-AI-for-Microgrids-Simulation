import ssl
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.auth import verify_request
from shared.config import (
    AGENT_ID,
    CA_CERT,
    MTLS_SERVER_PORT,
    SERVER_CERT,
    SERVER_KEY,
    VERIFY_PEER_CERTS,
)

from microgrid_agent import microgrid_agent
from research_agent import researcher_agent
from monitor_agent import monitor_agent
from shared.control_decisions import list_operator_alerts
from shared.rag import initialize_rag_system
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

class ChatRequest(BaseModel):
    message: str
    agent: str = "microgrid"  # Default to microgrid agent

class ChatResponse(BaseModel):
    response: str
    agent: str
    timestamp: str

# Initialize agents
agents = {}

def get_or_create_runner(agent_name: str):
    """Get or create agent runner."""
    if agent_name not in agents:
        if agent_name == "microgrid":
            agents[agent_name] = InMemoryRunner(agent=microgrid_agent, plugins=[LoggingPlugin()])
        elif agent_name == "researcher":
            agents[agent_name] = InMemoryRunner(agent=researcher_agent, plugins=[LoggingPlugin()])
        elif agent_name == "monitor":
            agents[agent_name] = InMemoryRunner(agent=monitor_agent, plugins=[LoggingPlugin()])
        else:
            raise ValueError(f"Unknown agent: {agent_name}")
    return agents[agent_name]

def build_chat_app() -> FastAPI:
    """Build FastAPI app with chat endpoint."""
    app = FastAPI(title="Microgrid Chat Server")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize RAG system on startup."""
        print("Initializing RAG system...")
        result = initialize_rag_system("./shared/docs")
        if result["status"] == "success":
            print(f"✓ RAG system initialized with {result['load_result']['loaded_count']} chunks")
            print(f"  Loaded files: {result['load_result']['loaded_files']}")
        else:
            print(f"⚠ RAG initialization failed: {result.get('error', 'Unknown error')}")

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "healthy", "service": "microgrid-chat"}

    @app.get("/alerts")
    async def operator_alerts(limit: int = 20) -> Dict[str, Any]:
        """Open operator alerts raised by the Monitor Agent."""
        return list_operator_alerts(limit=limit, open_only=True)

    @app.post("/chat", response_model=ChatResponse)
    async def chat_endpoint(
        request: ChatRequest,
        claims: Dict[str, Any] = Depends(verify_request)
    ) -> ChatResponse:
        """
        Chat endpoint that communicates with microgrid agents.
        
        Args:
            request: Chat request with message and optional agent selection
            claims: Verified JWT claims from auth middleware
            
        Returns:
            ChatResponse with agent reply
        """
        try:
            # Validate agent selection
            if request.agent not in ["microgrid", "researcher", "monitor"]:
                raise HTTPException(status_code=400, detail=f"Invalid agent: {request.agent}")
            
            # Get or create agent runner
            runner = get_or_create_runner(request.agent)
            
            # Execute agent with user message
            response = await runner.invoke(request.message)
            
            # Extract response content
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)
            
            return ChatResponse(
                response=response_text,
                agent=request.agent,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            print(f"Chat endpoint error: {e}")
            raise HTTPException(status_code=500, detail=f"Agent communication failed: {str(e)}")
    
    # Include original agent endpoints for compatibility
    @app.post("/command")
    async def command(
        payload: Optional[Dict[str, Any]] = None,
        claims: Dict[str, Any] = Depends(verify_request),
    ) -> Dict[str, Any]:
        """Original command endpoint for agent-to-agent communication."""
        body = payload or {}
        return {
            "status": "success",
            "command": body.get("command"),
            "result": "Command received",
            "auth_account": claims.get("agent_id", "unknown"),
        }

    return app

def run_chat_server(port: int = 8001) -> None:
    """Run the chat-enabled FastAPI service."""
    app = build_chat_app()

    print("STARTING MICROGRID CHAT SERVER")
    print("=" * 70)
    print(f"Service: Microgrid Chat API")
    print(f"HTTP Port: {port}")
    print(f"WebUI: Connect React app to http://localhost:{port}")
    print("Available endpoints:")
    print("  POST /chat - Chat with agents")
    print("  GET /health - Health check")
    print("  POST /command - Agent communication")
    print("=" * 70)

    # Run without mTLS for easier development
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=False
    )

if __name__ == "__main__":
    # Initialize RAG system first
    print("Pre-initializing RAG system...")
    result = initialize_rag_system("./shared/docs")
    if result["status"] == "success":
        print(f"✓ RAG system ready with {result['load_result']['loaded_count']} chunks")
    else:
        print(f"⚠ RAG initialization issue: {result.get('error', 'Unknown error')}")
    
    run_chat_server()
#!/usr/bin/env python3
"""
Simple demo version of the chat server that works without ChromaDB/ML dependencies.
This demonstrates the full architecture while mocking the RAG system.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    agent: str = "microgrid"  # Default to microgrid agent

class ChatResponse(BaseModel):
    response: str
    agent: str
    timestamp: str

class MockRAG:
    """Mock RAG system that returns sample responses."""
    
    def __init__(self):
        self.knowledge_base = {
            "voltage": "According to grid standards, microgrid voltage should be maintained at 120V/240V AC ±5%. Acceptable range is 114V-126V for 120V systems.",
            "battery": "Battery management best practices: maintain 20-90% SOC for daily cycling, keep emergency reserve at 10% minimum, limit DoD to 80% for lithium-ion systems.",
            "solar": "Solar integration guidelines: generation typically peaks 11AM-2PM, use 3-hour rolling forecasts, implement curtailment only when storage is full and load is low.",
            "frequency": "Frequency standards require 60Hz ±0.1Hz under normal conditions, acceptable range 59.5-60.5Hz, maximum RoCoF of 1Hz/second during disturbances.",
            "safety": "Safety systems must include ground fault protection (trip within 0.1s for faults >5mA), arc fault protection, and isolation from utility grid within 2 cycles."
        }
    
    def search_docs(self, query: str, top_k: int = 3):
        """Mock search that returns relevant responses."""
        query_lower = query.lower()
        results = []
        
        for key, content in self.knowledge_base.items():
            if key in query_lower:
                results.append({
                    "content": content,
                    "metadata": {
                        "source_file": f"{key}_standards.md",
                        "section_header": f"{key.title()} Standards",
                        "relevance_score": 0.95
                    }
                })
        
        if not results:
            results.append({
                "content": "I found general microgrid operational guidelines in the documentation. For specific technical details, please consult the grid standards documentation.",
                "metadata": {
                    "source_file": "general_guidelines.md",
                    "section_header": "General Operations",
                    "relevance_score": 0.7
                }
            })
        
        return {
            "status": "success",
            "results": results[:top_k],
            "query": query,
            "total_docs": len(self.knowledge_base),
            "search_timestamp": datetime.now(timezone.utc).isoformat()
        }

class MockAgent:
    """Mock agent that simulates the Google ADK agent behavior."""
    
    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        self.rag = MockRAG()
    
    async def invoke(self, message: str) -> str:
        """Process a message and return a response."""
        if self.agent_type == "microgrid":
            return await self._microgrid_response(message)
        elif self.agent_type == "researcher":
            return await self._researcher_response(message)
        elif self.agent_type == "monitor":
            return await self._monitor_response(message)
        else:
            return f"Unknown agent type: {self.agent_type}"
    
    async def _microgrid_response(self, message: str) -> str:
        """Generate microgrid agent response."""
        message_lower = message.lower()
        
        rag_triggers = ["standard", "guideline", "best practice", "how to", "what is", "requirement"]
        needs_rag = any(trigger in message_lower for trigger in rag_triggers)
        
        if needs_rag:
            research_result = await self._call_research_agent(message)
            response = f"I've consulted our knowledge base regarding your question.\n\n{research_result}\n\nBased on this information and my operational oversight, I recommend following these established guidelines while monitoring system performance closely."
        else:
            if any(word in message_lower for word in ["status", "current", "now"]):
                response = """Current microgrid status:
- Grid connection: ACTIVE
- Battery SOC: 75%
- Solar generation: 3.2 MW
- Load demand: 2.8 MW
- System frequency: 60.02 Hz
- All systems operating within normal parameters"""
            elif any(word in message_lower for word in ["problem", "issue", "alert", "emergency"]):
                response = "I'm monitoring all systems for any issues. If you're experiencing a specific problem, please provide details so I can coordinate with the appropriate agents and take corrective action."
            else:
                response = "As the Microgrid Agent, I oversee all system operations and coordinate with specialized agents. I can help with operational priorities, system monitoring, and strategic decisions. What would you like to know?"
        
        return response
    
    async def _researcher_response(self, message: str) -> str:
        """Generate research agent response."""
        rag_result = self.rag.search_docs(message)
        
        if rag_result["status"] == "success" and rag_result["results"]:
            findings = []
            for result in rag_result["results"]:
                findings.append(f"**{result['metadata']['section_header']}** (from {result['metadata']['source_file']}):\n{result['content']}")
            
            response = f"""## Research Query Analysis

**Query**: {message}

## Relevant Findings from Knowledge Base

{chr(10).join(findings)}

## Sources Consulted
- {len(rag_result['results'])} documents from technical standards library
- Search completed: {rag_result['search_timestamp']}

*Note: This information is presented factually without recommendations. Decision-making should be coordinated with the Microgrid Agent.*"""
        else:
            response = f"""## Research Query Analysis

**Query**: {message}

## Search Results
No specific documentation found for this query in the current knowledge base.

## Recommendation
Consider consulting external technical standards or contacting subject matter experts for this specific topic.

**Search Status**: {rag_result.get('status', 'unknown')}"""
        
        return response
    
    async def _call_research_agent(self, query: str) -> str:
        """Simulate KQML call to research agent."""
        research_agent = MockAgent("researcher")
        return await research_agent.invoke(query)

    async def _monitor_response(self, message: str) -> str:
        """Simulate Monitor Agent oversight response."""
        msg = message.lower()
        if "review" in msg or "decision" in msg or "pending" in msg:
            return """## Monitor Review (demo)

**Pending control decisions:** 1 (simulated)

**Latest decision:** Shed 2 MW non-critical load at battery SOC 25%.

**Assessment (medium):** SOC is within safe range (20–90%). Solar forecast may allow delaying shed by ~1 hour.

**Actions taken (demo):**
- KQML inform queued for `control-agent` (subject: decision-review-demo-001)
- Operator alert logged: [MEDIUM] Timing — premature load shedding

*Advisory only — human operator has final authority.*"""
        if "alert" in msg or "issue" in msg:
            return """**Open operator alerts (demo):**
1. [MEDIUM] Timing — Premature load shedding vs solar forecast
2. [LOW] Data quality — Forecast age > 30 minutes

Use production Monitor Agent with Redis and audit DB for live data."""
        return """I am the Monitor Agent. I review every Control Agent decision, flag issues for operators, and send collaborative KQML feedback to Control and Microgrid agents.

Try: "Review pending control decisions" or "Show open alerts"."""

agents = {
    "microgrid": MockAgent("microgrid"),
    "researcher": MockAgent("researcher"),
    "monitor": MockAgent("monitor"),
}

def build_demo_chat_app() -> FastAPI:
    """Build demo FastAPI app with mock chat endpoint."""
    app = FastAPI(title="Microgrid Chat Demo")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {
            "status": "healthy", 
            "service": "microgrid-chat-demo",
            "version": "1.0.0",
            "rag_system": "mock",
            "agents": list(agents.keys())
        }

    @app.get("/alerts")
    async def operator_alerts() -> Dict[str, Any]:
        return {
            "status": "success",
            "count": 1,
            "alerts": [{
                "severity": "medium",
                "issue_type": "timing",
                "summary": "Premature load shedding (demo)",
                "details": "Connect production stack for live Monitor alerts.",
            }],
        }

    @app.post("/chat", response_model=ChatResponse)
    async def chat_endpoint(request: ChatRequest) -> ChatResponse:
        """
        Demo chat endpoint with mock agent responses.
        """
        try:
            if request.agent not in agents:
                raise HTTPException(status_code=400, detail=f"Invalid agent: {request.agent}. Available: {list(agents.keys())}")

            agent = agents[request.agent]
            response_text = await agent.invoke(request.message)
            
            return ChatResponse(
                response=response_text,
                agent=request.agent,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            print(f"Chat endpoint error: {e}")
            raise HTTPException(status_code=500, detail=f"Agent communication failed: {str(e)}")
    
    @app.get("/demo-info")
    async def demo_info():
        """Information about this demo system."""
        return {
            "title": "Microgrid Agent Chat Demo",
            "description": "Demonstration of React Chat UI + FastAPI + Mock Agent/RAG System",
            "architecture": {
                "frontend": "React with Tailwind CSS",
                "backend": "FastAPI with CORS",
                "agents": "Mock Google ADK agents",
                "rag": "Mock knowledge base with sample microgrid documentation",
                "communication": "HTTP REST API (production would use KQML over mTLS)"
            },
            "features": [
                "Agent selection (Microgrid vs Research Agent)",
                "RAG-enhanced responses from documentation",
                "KQML-style agent communication patterns",
                "Real-time chat interface",
                "Audit trail logging"
            ],
            "sample_queries": [
                "What are the voltage standards for microgrids?",
                "Show me current system status",
                "How should batteries be managed?",
                "What are the safety requirements?",
                "Tell me about solar integration best practices"
            ]
        }

    return app

def run_demo_server(port: int = 8001):
    """Run the demo chat server."""
    app = build_demo_chat_app()

    print(f"Demo chat API listening on http://0.0.0.0:{port} (POST /chat, GET /health)")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    run_demo_server()
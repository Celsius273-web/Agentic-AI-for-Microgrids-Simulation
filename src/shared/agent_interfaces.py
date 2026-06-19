import requests
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone

from . import auth
from . import config
from . import kqml


def retrieve_grid_state(tool_context: Any) -> Dict[str, Any]:

    try:
        token = auth.get_service_account_token()
        url = f"https://mcp-grid-state:{config.MTLS_SERVER_PORT}/retrieve_grid_state"
        
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            cert=(config.CLIENT_CERT, config.CLIENT_KEY),
            verify=config.CA_CERT,
            timeout=10
        )
        
        response.raise_for_status()
        grid_data = response.json()
        
        return {
            "status": "success",
            "grid_state": grid_data,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "mcp_server": "mcp-grid-state"
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"MCP Grid State Server request failed: {e}",
            "retrieved_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Grid state retrieval failed: {e}",
            "retrieved_at": datetime.now(timezone.utc).isoformat()
        }


def RAG_access(tool_context: Any, query: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Query the RAG knowledge base for best practices and technical references.

    Args:
        query: Natural language query describing the information needed
        top_k: Number of top results to return (default 3)
        
    Returns:
        Dict containing RAG query results or error information
    """
    try:
        from .rag import search_knowledge_base

        search_result = search_knowledge_base(query, top_k)

        return {
            "status": search_result.get("status", "error"),
            "query": query,
            "results": search_result.get("results", []),
            "total_docs": search_result.get("total_docs", 0),
            "search_timestamp": search_result.get("search_timestamp"),
            "error": search_result.get("error") if search_result.get("status") == "error" else None
        }
        
    except ImportError as e:
        return {
            "status": "error",
            "error": f"RAG system not available: {e}",
            "query": query
        }
    except Exception as e:
        return {
            "status": "error", 
            "error": f"RAG query failed: {e}",
            "query": query
        }


def send_grid_alert(receiver_id: str, subject: str, content: str, 
                   priority: str = "medium", grid_impact: str = "stability",
                   affected_components: Optional[List[str]] = None,
                   conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a grid management alert using KQML inform performative.
    
    Args:
        receiver_id: Target agent ID or "all-agents" for broadcast
        subject: Alert subject (e.g., "supply-deficit-warning")
        content: Detailed alert message
        priority: Alert priority (low, medium, high, critical)
        grid_impact: Type of grid impact (stability, efficiency, safety, cost)
        affected_components: List of affected components
        conversation_id: Optional conversation ID
        
    Returns:
        Dict containing communication result
    """
    try:
        alert_msg = kqml.inform(
            sender_id=config.AGENT_ID,
            receiver_id=receiver_id,
            subject=subject,
            content=content,
            conversation_id=conversation_id,
            priority=priority,
            grid_impact=grid_impact,
            affected_components=affected_components or []
        )
        
        return {
            "status": "success",
            "message_type": "grid_alert",
            "conversation_id": alert_msg.conversation_id,
            "kqml_message": alert_msg.to_string(),
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to send grid alert: {e}",
            "message_type": "grid_alert"
        }


def request_research_analysis(researcher_id: str, subject: str, content: str,
                            priority: str = "medium",
                            conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Request research analysis using KQML query performative.
    
    Args:
        researcher_id: Target researcher agent ID
        subject: Research subject (e.g., "load-forecast-accuracy")
        content: Detailed research request
        priority: Request priority
        conversation_id: Optional conversation ID
        
    Returns:
        Dict containing communication result
    """
    try:
        query_msg = kqml.query(
            sender_id=config.AGENT_ID,
            receiver_id=researcher_id,
            subject=subject,
            content=content,
            conversation_id=conversation_id,
            priority=priority,
            grid_impact="efficiency"
        )
        
        return {
            "status": "success",
            "message_type": "research_request",
            "conversation_id": query_msg.conversation_id,
            "kqml_message": query_msg.to_string(),
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to request research analysis: {e}",
            "message_type": "research_request"
        }


def propose_grid_action(receiver_id: str, subject: str, content: str,
                       priority: str = "high", grid_impact: str = "stability",
                       affected_components: Optional[List[str]] = None,
                       conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Propose a grid management action using KQML propose performative.
    
    Args:
        receiver_id: Target agent ID
        subject: Proposal subject (e.g., "emergency-discharge-proposal")
        content: Detailed proposal
        priority: Action priority
        grid_impact: Expected grid impact
        affected_components: Components affected by the action
        conversation_id: Optional conversation ID
        
    Returns:
        Dict containing communication result
    """
    try:
        proposal_msg = kqml.propose(
            sender_id=config.AGENT_ID,
            receiver_id=receiver_id,
            subject=subject,
            content=content,
            conversation_id=conversation_id,
            priority=priority,
            grid_impact=grid_impact,
            affected_components=affected_components or []
        )
        
        return {
            "status": "success",
            "message_type": "grid_proposal",
            "conversation_id": proposal_msg.conversation_id,
            "kqml_message": proposal_msg.to_string(),
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to send grid proposal: {e}",
            "message_type": "grid_proposal"
        }
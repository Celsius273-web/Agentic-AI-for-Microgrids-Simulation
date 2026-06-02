import uuid
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

def _send_agent_request(
    service_name: str,
    receiver_id: str, 
    command: str,
    params: Optional[Dict] = None,
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send HTTPS request with mTLS and OIDC token to an agent service.
    Uses KQML protocol with schema validation.
    
    Args:
        service_name: Docker service name (e.g., "solar-agent")
        receiver_id: Agent ID for KQML message
        command: Command to send
        params: Optional parameters
        conversation_id: Optional conversation ID (auto-generated if not provided)
        
    Returns:
        Dict containing response data or error information
    """
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    try:
        token = auth.get_service_account_token()
        kqml_msg = kqml.request(
            sender_id=config.AGENT_ID,
            receiver_id=receiver_id,
            command=command,
            params=params or {},
            conversation_id=conversation_id
        )

        url = f"https://{service_name}:{config.MTLS_SERVER_PORT}/command"
        
        response = requests.post(
            url,
            data=kqml_msg.to_string(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/kqml"
            },
            cert=(config.CLIENT_CERT, config.CLIENT_KEY),
            verify=config.CA_CERT,
            timeout=30
        )
        
        response.raise_for_status()

        try:
            response_kqml = kqml.parse_kqml(response.text)
        except kqml.ValidationError as e:
            return {
                "status": "validation_error",
                "agent": receiver_id,
                "command": command,
                "error": f"Invalid KQML response: {e}",
                "conversation_id": conversation_id
            }

        kqml.enforce_conversation_id(response_kqml, conversation_id)

        return {
            "status": "success" if response_kqml.performative == "accept" else "rejected",
            "agent": receiver_id,
            "command": command,
            "data": response_kqml.to_dict(),
            "conversation_id": response_kqml.conversation_id,
            "performative": response_kqml.performative,
            "reason": getattr(response_kqml, 'reason', None),
            "subject": getattr(response_kqml, 'subject', None),
            "content": getattr(response_kqml, 'content', None)
        }
        
    except kqml.ValidationError as e:
        return {
            "status": "validation_error",
            "agent": receiver_id,
            "command": command,
            "error": f"KQML validation failed: {e}",
            "conversation_id": conversation_id
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "agent": receiver_id,
            "command": command,
            "error": f"HTTP request failed: {e}",
            "conversation_id": conversation_id
        }
    except Exception as e:
        return {
            "status": "error", 
            "agent": receiver_id,
            "command": command,
            "error": f"Agent communication failed: {e}",
            "conversation_id": conversation_id
        }

def solar_agent_access(tool_context: Any, command: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Send a command to the Solar Agent container using KQML over HTTPS with mTLS.

    Args:
        command: Command to send (e.g. "get_output", "set_curtailment", "get_forecast")
        params: Optional parameters for the command (e.g. {"forecast_hours": 24})
        
    Returns:
        Dict containing solar agent response or error information
    """
    return _send_agent_request("solar-agent", "solar-agent", command, params)

def wind_agent_access(tool_context: Any, command: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Send a command to the Wind Agent container using KQML over HTTPS with mTLS.

    Args:
        command: Command to send (e.g. "get_output", "set_curtailment", "get_forecast")
        params: Optional parameters for the command (e.g. {"forecast_hours": 24})
        
    Returns:
        Dict containing wind agent response or error information
    """
    return _send_agent_request("wind-agent", "wind-agent", command, params)

def battery_agent_access(tool_context: Any, command: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Send a command to the Battery Agent container using KQML over HTTPS with mTLS.

    Args:
        command: Command to send (e.g. "get_soc", "set_charge_rate", "get_capacity")
        params: Optional parameters for the command (e.g. {"charge_rate_mw": 2.5})
        
    Returns:
        Dict containing battery agent response or error information
    """
    return _send_agent_request("battery-agent", "battery-agent", command, params)

def load_agent_access(tool_context: Any, command: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Send a command to the Load Agent container using KQML over HTTPS with mTLS.

    Args:
        command: Command to send (e.g. "get_demand", "shed_load", "get_forecast")
        params: Optional parameters for the command (e.g. {"load_reduction_mw": 1.2})
        
    Returns:
        Dict containing load agent response or error information
    """
    return _send_agent_request("load-agent", "load-agent", command, params)

def get_all_generation_status(tool_context: Any) -> Dict[str, Any]:
    """
    Query all generation agents for current output status.
    
    Returns:
        Dict containing status from solar and wind agents
    """
    results = {}
    solar_result = solar_agent_access(tool_context, "get_output")
    results["solar"] = solar_result
    wind_result = wind_agent_access(tool_context, "get_output")
    results["wind"] = wind_result
    
    return {
        "status": "success",
        "generation_status": results,
        "timestamp": kqml._generate_timestamp()
    }

def get_all_storage_status(tool_context: Any) -> Dict[str, Any]:
    """
    Query storage agents for current status.
    
    Returns:
        Dict containing battery status and load demand
    """
    results = {}
    battery_result = battery_agent_access(tool_context, "get_soc")
    results["battery"] = battery_result
    load_result = load_agent_access(tool_context, "get_demand")
    results["load"] = load_result
    
    return {
        "status": "success", 
        "storage_status": results,
        "timestamp": kqml._generate_timestamp()
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
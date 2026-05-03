import uuid
import requests
from typing import Any, Dict, Optional

from . import auth
from . import config
from . import kqml

# Each function below sends a command to another agent container over Docker's internal network
# using HTTPS with mTLS and OIDC token authentication.
# Commands are sent as KQML performatives for structured agent communication.

def RAG_access(tool_context: Any, query: str) -> Dict[str, Any]:
    """
    Query the RAG knowledge base for best practices and technical references.

    Args:
        query: Natural language query describing the information needed
        
    Returns:
        Dict containing RAG query results or error information
    """
    # TODO: integrate with your chosen vector store (e.g. ChromaDB, Pinecone, Vertex AI Search)
    return {"status": "not_implemented", "query": query}

def _send_agent_request(
    service_name: str,
    receiver_id: str, 
    command: str,
    params: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Send HTTPS request with mTLS and OIDC token to an agent service.
    
    Args:
        service_name: Docker service name (e.g., "solar-agent")
        receiver_id: Agent ID for KQML message
        command: Command to send
        params: Optional parameters
        
    Returns:
        Dict containing response data or error information
    """
    try:
        # Get service account token for Authorization header
        token = auth.get_service_account_token()
        
        # Build KQML request message
        conversation_id = str(uuid.uuid4())
        kqml_msg = kqml.request(
            sender_id=config.AGENT_ID,
            receiver_id=receiver_id,
            command=command,
            params=params or {},
            conversation_id=conversation_id
        )
        
        # Send HTTPS request with mTLS certificates
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
        
        # Parse KQML response
        response_kqml = kqml.parse_kqml(response.text)
        
        # Extract and return structured data
        return {
            "status": "success" if response_kqml.performative == "accept" else "rejected",
            "agent": receiver_id,
            "command": command,
            "data": response_kqml.to_dict(),
            "conversation_id": response_kqml.conversation_id,
            "performative": response_kqml.performative,
            "reason": getattr(response_kqml, 'reason', None)
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

# Additional convenience functions for common agent interactions

def get_all_generation_status(tool_context: Any) -> Dict[str, Any]:
    """
    Query all generation agents for current output status.
    
    Returns:
        Dict containing status from solar and wind agents
    """
    results = {}
    
    # Get solar status
    solar_result = solar_agent_access(tool_context, "get_output")
    results["solar"] = solar_result
    
    # Get wind status  
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
    
    # Get battery status
    battery_result = battery_agent_access(tool_context, "get_soc")
    results["battery"] = battery_result
    
    # Get load demand
    load_result = load_agent_access(tool_context, "get_demand")
    results["load"] = load_result
    
    return {
        "status": "success", 
        "storage_status": results,
        "timestamp": kqml._generate_timestamp()
    }
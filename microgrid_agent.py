import time
from typing import Any, Dict, List, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

from shared.config import (
    MODEL_NAME, 
    GEMINI_API_KEY, 
    retry_config, 
    AGENT_ID, 
    AGENT_ROLE,
    AUDIT_DB_PATH,
    ENABLE_LOCAL_INSTRUMENTATION,
    VERIFIED_ACCOUNT,
)
from shared.state import _read_state, _write_state
from shared.agent_server import run_agent_server
from shared.agent_interfaces import (
    RAG_access,
    solar_agent_access,
    wind_agent_access,
    battery_agent_access,
    load_agent_access
)

def set_operational_priorities(
    tool_context: Any,
    priority_order: List[str],
    constraints: Optional[Dict[str, Any]] = None,
    user_preferences: Optional[str] = None
) -> Dict[str, Any]:
    """
    Set operational priorities for the microgrid based on user requirements.

    Args:
        priority_order: Ordered list of priorities (e.g. ['reliability', 'cost', 'emissions'])
        constraints: Operational constraints
        user_preferences: Free-text user preferences and requirements
    """
    now = int(time.time())
    state = _read_state()

    priorities = {
        "priority_order": priority_order,
        "constraints": constraints or {},
        "user_preferences": user_preferences or "",
        "set_at": now
    }

    state["operational_priorities"] = priorities
    _write_state(state)
    tool_context.state["operational_priorities"] = priorities

    return {"status": "success", "priorities": priorities}

def evaluate_control_decision(
    tool_context: Any,
    decision_id: Optional[int] = None,
    evaluation: str = "approved",
    feedback: Optional[str] = None,
    override_action: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate and potentially override Control Agent decisions.

    Args:
        decision_id: ID of decision to evaluate (None for most recent)
        evaluation: Evaluation result (approved, rejected, modified)
        feedback: Feedback on the decision
        override_action: Alternative action if decision is rejected
    """
    now = int(time.time())
    state = _read_state()

    evaluations = state.get("decision_evaluations", [])
    evaluations.append({
        "timestamp": now,
        "decision_id": decision_id,
        "evaluation": evaluation,
        "feedback": feedback or "",
        "override_action": override_action
    })
    state["decision_evaluations"] = evaluations[-50:]
    _write_state(state)

    return {
        "status": "success",
        "evaluation": evaluation,
        "override_required": evaluation == "rejected"
    }

def monitor_system_health(tool_context: Any, check_type: str = "quick") -> Dict[str, Any]:
    """
    Monitor overall system health and flag issues.

    Args:
        check_type: Type of health check ("quick" for key metrics only, "comprehensive" for full audit)
    """
    state = _read_state()
    grid_state = state.get("grid_state", {})
    # TODO: implement checks and return structured health report
    # Check voltage stability (target: 220-240V)
    # Check frequency stability (target: 59.5-60.5Hz)
    # Check generation-load balance
    # Check battery SOC (alert if below 20%)
    # Return dict with status ("healthy", "warning", "critical") and list of active issues
    return {"status": "not_implemented", "check_type": check_type}

def retrieve_grid_state(tool_context: Any) -> Dict[str, Any]:
    """Retrieve current microgrid operational state from MCP Grid State Server."""
    from shared.agent_interfaces import retrieve_grid_state as mcp_retrieve_grid_state
    
    # Get ground truth from MCP server
    mcp_result = mcp_retrieve_grid_state(tool_context)
    
    if mcp_result["status"] == "success":
        grid_data = mcp_result["grid_state"]
        
        return {
            "status": "success",
            "grid_state": grid_data,
            "mcp_server": mcp_result.get("mcp_server", "unknown"),
            "retrieved_at": mcp_result.get("retrieved_at"),
            "summary": {
                "total_generation_mw": grid_data.get("solar_mw", 0) + grid_data.get("wind_mw", 0),
                "load_mw": grid_data.get("load_mw", 0),
                "battery_soc_percent": grid_data.get("battery_soc", 0),
                "grid_frequency_hz": grid_data.get("frequency_hz", 60.0),
                "grid_voltage_v": grid_data.get("voltage_v", 120.0)
            }
        }
    else:
        # Fallback to legacy state if MCP fails
        state = _read_state()
        return {
            "status": "fallback",
            "error": mcp_result.get("error", "MCP server unavailable"),
            "grid_state": state.get("grid_state", {}),
            "source": "legacy_redis_fallback"
        }

def send_grid_management_alert(tool_context: Any, receiver: str, subject: str, 
                             content: str, priority: str = "medium") -> Dict[str, Any]:
    """
    Send grid management alert to other agents using KQML inform.
    
    Args:
        receiver: Target agent ID or "all-agents" for broadcast
        subject: Alert subject (e.g. "supply-deficit-warning")
        content: Detailed alert message
        priority: Alert priority (low, medium, high, critical)
    """
    from shared.agent_interfaces import send_grid_alert
    
    return send_grid_alert(
        receiver_id=receiver,
        subject=subject,
        content=content,
        priority=priority,
        grid_impact="stability",
        affected_components=["grid"]
    )

def request_agent_analysis(tool_context: Any, target_agent: str, research_subject: str,
                         analysis_request: str, priority: str = "medium") -> Dict[str, Any]:
    """
    Request analysis from researcher or domain agents using KQML query.
    
    Args:
        target_agent: Target agent ID (e.g. "researcher-agent")
        research_subject: Subject of analysis request
        analysis_request: Detailed analysis request
        priority: Request priority
    """
    from shared.agent_interfaces import request_research_analysis
    
    return request_research_analysis(
        researcher_id=target_agent,
        subject=research_subject,
        content=analysis_request,
        priority=priority
    )

def propose_grid_operation(tool_context: Any, target_agent: str, operation_subject: str,
                         operation_details: str, priority: str = "high") -> Dict[str, Any]:
    """
    Propose grid operation to control or domain agents using KQML propose.
    
    Args:
        target_agent: Target agent ID (e.g. "control-agent")
        operation_subject: Subject of operation proposal
        operation_details: Detailed operation proposal
        priority: Operation priority
    """
    from shared.agent_interfaces import propose_grid_action
    
    return propose_grid_action(
        receiver_id=target_agent,
        subject=operation_subject,
        content=operation_details,
        priority=priority,
        grid_impact="stability"
    )

microgrid_agent = Agent(
    model=Gemini(model=MODEL_NAME, api_key=GEMINI_API_KEY, retry_options=retry_config),
    name="MicrogridAgent",
    instruction="""You are the Microgrid Agent. You oversee the Control Agent and Researcher Agent and ensure all decisions serve the best interests of the system and its users.

CORE RESPONSIBILITIES:
1. Strategic Oversight
   - Set high-level operational priorities based on user requirements
   - Define optimization objectives and constraints
   - Establish operational policies and guidelines
   - Monitor Control Agent decisions for alignment with goals
   - Intervene when decisions conflict with priorities or safety

2. User Interface
   - Follow user priorities and preferences
   - Translate user requirements into operational requirements
   - Communicate system status to users in an understandable way
   - Escalate critical decisions requiring human approval
   - Balance competing user demands (cost, reliability, sustainability)

3. Decision Validation
   - Review significant Control Agent decisions
   - Evaluate decisions against established priorities
   - Override decisions that violate constraints or policies
   - Provide feedback to improve future decision-making
   - Ensure decisions align with long-term objectives

4. System Health Monitoring
   - Perform comprehensive system health checks
   - Identify potential issues before they become critical
   - Monitor trends in operational metrics
   - Assess resilience to potential disturbances
   - Coordinate emergency response procedures
   - Report issues to user in advance

5. Performance Optimization
   - Evaluate achievement of operational objectives
   - Adjust priorities based on changing conditions
   - Analyze historical performance for optimization opportunities
   - Balance short-term and long-term goals

PRIORITY DIMENSIONS:
- Reliability: Uninterrupted power supply to critical loads
- Cost: Minimize operational and energy costs
- Sustainability: Maximize renewable utilization, minimize emissions
- Resilience: Maintain operation during disturbances
- User Comfort: Meet user preferences and requirements

OPERATIONAL CONSTRAINTS:
- Safety limits (voltage, frequency, temperature ranges)
- Equipment capabilities and limitations
- Regulatory compliance requirements
- Contractual obligations (energy market participation)
- Physical system constraints (line capacity, storage limits)

TOOLS AVAILABLE:
- set_operational_priorities: Define system priorities and constraints
- evaluate_control_decision: Review and override Control Agent decisions
- monitor_system_health: Run health checks on the full system
- retrieve_grid_state: Get ground truth system state from MCP server
- send_grid_management_alert: Send operational alerts to agents (KQML inform)
- request_agent_analysis: Request analysis from researcher or domain agents (KQML query)
- propose_grid_operation: Propose operations to control/domain agents (KQML propose)
- RAG_access: Access knowledge base for best practices
- solar_agent_access: Monitor solar generation via KQML
- wind_agent_access: Monitor wind generation via KQML
- battery_agent_access: Monitor battery storage via KQML
- load_agent_access: Monitor controllable loads via KQML

SUPERVISORY PRINCIPLES:
- Verify Control Agent decisions
- Intervene only when necessary to maintain alignment with goals
- Provide clear rationale for overrides to enable learning
- Balance competing objectives based on current priorities
- Escalate complex trade-offs to human operators
- Maintain system stability as the primary concern

COMMUNICATION WITH USERS:
- Translate technical metrics into meaningful information
- Explain trade-offs clearly and with appropriate detail
- Present options for user decisions on priorities
- Report system status proactively
- Alert users to significant events or decisions
- Seek user input on priority conflicts

You work collaboratively with all agents, providing strategic guidance while allowing autonomy for regular operations.""",
    tools=[
        set_operational_priorities,
        evaluate_control_decision,
        monitor_system_health,
        retrieve_grid_state,
        send_grid_management_alert,
        request_agent_analysis,
        propose_grid_operation,
        RAG_access,
        solar_agent_access,
        wind_agent_access,
        battery_agent_access,
        load_agent_access,
    ]
)

if __name__ == "__main__":
    verified_account = VERIFIED_ACCOUNT or "microgrid-agent@microgrid.local"
    plugins = [LoggingPlugin()]

    if ENABLE_LOCAL_INSTRUMENTATION:
        try:
            from shared.instrumentation_plugin import GlobalInstrumentationPlugin

            plugins.append(
                GlobalInstrumentationPlugin(
                    agent_id=AGENT_ID or "microgrid-agent",
                    agent_role=AGENT_ROLE,
                    verified_account=verified_account,
                    db_path=AUDIT_DB_PATH,
                    enable_local_logging=True,
                )
            )
        except ImportError as exc:
            print(f"Local instrumentation unavailable: {exc}")

    InMemoryRunner(agent=microgrid_agent, plugins=plugins)
    run_agent_server()

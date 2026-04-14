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
from shared.instrumentation_plugin import GlobalInstrumentationPlugin
from shared.agent_interfaces import (
    RAG_access,
    solar_agent_access,
    wind_agent_access,
    battery_agent_access,
    load_agent_access
)

# --- Tools ---

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
    """Retrieve current microgrid operational state."""
    state = _read_state()
    grid_state = state.get("grid_state", tool_context.state.get("grid_state", {}))

    return {
        "status": "success",
        "grid_state": grid_state,
        "optimization_params": state.get("optimization_params", {}),
        "recent_decisions": state.get("decision_log", [])[-5:]
    }

# --- Agent Definition ---

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
- retrieve_grid_state: Get current system state and recent history
- RAG_access: Access knowledge base for best practices
- solar_agent_access: Monitor solar generation
- wind_agent_access: Monitor wind generation
- battery_agent_access: Monitor battery storage
- load_agent_access: Monitor controllable loads

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
        RAG_access,
        solar_agent_access,
        wind_agent_access,
        battery_agent_access,
        load_agent_access,
    ]
)

# --- Runner with Local Instrumentation ---

if __name__ == "__main__":
    # Prepare verified identity
    verified_account = VERIFIED_ACCOUNT or "microgrid-agent@microgrid.local"
    
    # Create plugin list
    plugins = [LoggingPlugin()]
    
    # Conditional: Add local instrumentation plugin
    if ENABLE_LOCAL_INSTRUMENTATION:
        print("=" * 70)
        print("REGISTERING LOCAL INSTRUMENTATION PLUGIN")
        print("=" * 70)
        
        # Initialize plugin with local SQLite backend
        instrumentation_plugin = GlobalInstrumentationPlugin(
            agent_id=AGENT_ID or "microgrid-agent",
            agent_role=AGENT_ROLE,
            verified_account=verified_account,
            db_path=AUDIT_DB_PATH,
            enable_local_logging=True
        )
        
        # Add to plugins
        plugins.append(instrumentation_plugin)
        
        print(f"✓ Agent ID: {AGENT_ID or 'microgrid-agent'}")
        print(f"✓ Verified Account: {verified_account}")
        print(f"✓ Audit DB: {AUDIT_DB_PATH}")
        print("\nCapturing lifecycle hooks:")
        print("  - on_agent_start: Agent initialization")
        print("  - on_tool_start: MCP ground truth inputs")
        print("  - on_tool_end: Tool outputs and side effects")
        print("  - on_model_end: KQML performatives")
        print("=" * 70)
    else:
        print("⚠ Local instrumentation disabled")
    
    # Create runner with all plugins
    runner = InMemoryRunner(agent=microgrid_agent, plugins=plugins)
    print("\n✓ MicrogridAgent runner started with lifecycle hook interception")
    print(f"  All events stored in: {AUDIT_DB_PATH}")
    # TODO: replace with FastAPI HTTP server for inter-agent communication

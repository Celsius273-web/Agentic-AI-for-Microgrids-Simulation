from typing import Any, Dict, List, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

from shared.config import MODEL_NAME, GEMINI_API_KEY, retry_config
from shared.state import _read_state, _write_state

def get_load_demand(tool_context: Any) -> Dict[str, Any]:
    """Return current total load demand in kW broken down by load type."""
    # TODO: read from smart meter or load controller
    return {"status": "stub", "total_kw": 0.0, "critical_kw": 0.0, "non_critical_kw": 0.0}

def shed_load(tool_context: Any, load_ids: List[str], reason: str) -> Dict[str, Any]:
    """
    Shed specified non-critical loads.

    Args:
        load_ids: List of load IDs to disconnect
        reason: Reason for load shedding (logged for audit trail)
    """
    # TODO: send disconnect commands to controllable load switches
    return {"status": "stub", "shed_loads": load_ids, "reason": reason}

def restore_load(tool_context: Any, load_ids: List[str]) -> Dict[str, Any]:
    """
    Restore previously shed loads.

    Args:
        load_ids: List of load IDs to reconnect
    """
    # TODO: send reconnect commands to controllable load switches
    return {"status": "stub", "restored_loads": load_ids}

load_agent = Agent(
    model=Gemini(model=MODEL_NAME, api_key=GEMINI_API_KEY, retry_options=retry_config),
    name="LoadAgent",
    instruction="""You are the Load Agent. You manage and report on controllable loads in the microgrid.

RESPONSIBILITIES:
- Report current total load demand and breakdown by criticality
- Execute load shedding commands from the Control Agent
- Restore loads when the Control Agent instructs
- Maintain a priority list of loads (critical loads are never shed)

CONSTRAINTS:
- Only act on commands from the Control Agent or Microgrid Agent
- Never shed critical loads (hospitals, safety systems, emergency lighting)
- Log all shed and restore events with timestamp and reason
- Restore loads in reverse shed order unless instructed otherwise

You do not make strategic decisions. You execute commands and report data.""",
    tools=[
        get_load_demand,
        shed_load,
        restore_load,
    ]
)

if __name__ == "__main__":
    from shared.agent_server import run_agent_server

    InMemoryRunner(agent=load_agent, plugins=[LoggingPlugin()])
    run_agent_server()

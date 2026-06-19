import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
for _p in (_root / "src", _root):
    _entry = str(_p)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import time
from typing import Any, Dict, List, Optional

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from shared.config import MODEL_NAME, GEMINI_API_KEY, retry_config, AGENT_ID, AGENT_ROLE, VERIFIED_ACCOUNT
from shared.agent_server import run_agent_server
from shared.runner_plugins import build_adk_plugins
from shared.state import _read_state, read_grid_state
from shared.control_decisions import record_control_decision as _record_control_decision


def get_grid_summary(tool_context: Any) -> Dict[str, Any]:
    """Return current microgrid state for coordination."""
    grid = read_grid_state()
    state = _read_state()
    return {
        "status": "success",
        "grid_state": grid,
        "operational_priorities": state.get("operational_priorities", {}),
    }


def record_control_decision(
    tool_context: Any,
    action: str,
    rationale: str,
    inputs_considered: Optional[Dict[str, Any]] = None,
    inputs_not_considered: Optional[List[str]] = None,
    commands_issued: Optional[List[Dict[str, Any]]] = None,
    expected_outcomes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Record a structured decision for Monitor review. Call after every operational decision.
    """
    grid = read_grid_state()
    result = _record_control_decision(
        action=action,
        rationale=rationale,
        inputs_considered=inputs_considered,
        inputs_not_considered=inputs_not_considered,
        commands_issued=commands_issued,
        grid_state_snapshot=grid,
        expected_outcomes=expected_outcomes,
    )
    if result.get("status") == "success":
        tool_context.state["last_decision_id"] = result["decision_id"]
    return result


control_agent = Agent(
    model=Gemini(model=MODEL_NAME, api_key=GEMINI_API_KEY, retry_options=retry_config),
    name="ControlAgent",
    instruction="""You are the Control Agent. You coordinate microgrid operations and balance reliability, cost, and emissions.

RESPONSIBILITIES:
- Maintain reliability and balance across the microgrid
- Issue commands and interpret responses
- Escalate to the Microgrid Agent when policy or priorities conflict

REQUIRED AFTER EVERY OPERATIONAL DECISION:
- Call record_control_decision with action, rationale, inputs_considered, and any inputs_not_considered
- Include commands_issued and expected_outcomes when applicable

The Monitor Agent reviews every recorded decision. Do not bypass record_control_decision.

CONSTRAINTS:
- Do not bypass safety limits
- Log significant decisions with clear rationale""",
    tools=[get_grid_summary, record_control_decision],
)

if __name__ == "__main__":
    plugins = build_adk_plugins(
        agent_id=AGENT_ID or "control-agent",
        agent_role=AGENT_ROLE or "control",
        verified_account=VERIFIED_ACCOUNT or "control-agent@microgrid.local",
        enable_console_audit=True,
    )
    InMemoryRunner(agent=control_agent, plugins=plugins)
    run_agent_server()

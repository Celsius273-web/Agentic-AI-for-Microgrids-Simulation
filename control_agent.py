from typing import Any, Dict, Optional

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

from shared.config import MODEL_NAME, GEMINI_API_KEY, retry_config
from shared.agent_server import run_agent_server
from shared.state import _read_state, _write_state


def get_grid_summary(tool_context: Any) -> Dict[str, Any]:
    """Return a coarse view of microgrid state for coordination."""
    state = _read_state()
    return {"status": "stub", "keys": list(state.keys())}


def relay_command(
    tool_context: Any,
    target_agent: str,
    command: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Placeholder for dispatching commands to domain agents over HTTP."""
    return {"status": "stub", "target_agent": target_agent, "command": command, "payload": payload or {}}


control_agent = Agent(
    model=Gemini(model=MODEL_NAME, api_key=GEMINI_API_KEY, retry_options=retry_config),
    name="ControlAgent",
    instruction="""You are the Control Agent. You coordinate solar, wind, battery, and load agents.

RESPONSIBILITIES:
- Maintain reliability and balance across the microgrid
- Issue commands to domain agents and interpret their responses
- Escalate to the Microgrid Agent when policy or priorities conflict

CONSTRAINTS:
- Do not bypass domain agents' safety limits
- Log significant decisions with rationale""",
    tools=[get_grid_summary, relay_command],
)

if __name__ == "__main__":
    runner = InMemoryRunner(agent=control_agent, plugins=[LoggingPlugin()])
    print("ControlAgent runner initialized.")
    run_agent_server()

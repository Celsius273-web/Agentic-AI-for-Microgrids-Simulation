from typing import Any, Dict, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

from shared.config import MODEL_NAME, GEMINI_API_KEY, retry_config
from shared.state import _read_state, _write_state

# --- Tools ---

def get_wind_output(tool_context: Any) -> Dict[str, Any]:
    """Return current wind generation output in kW."""
    # TODO: read from real sensor data or simulation
    return {"status": "stub", "output_kw": 0.0}

def set_curtailment(tool_context: Any, curtailment_percent: float) -> Dict[str, Any]:
    """
    Set wind curtailment level.

    Args:
        curtailment_percent: Percentage of generation to curtail (0-100)
    """
    # TODO: send command to turbine controller
    return {"status": "stub", "curtailment_percent": curtailment_percent}

# --- Agent Definition ---

wind_agent = Agent(
    model=Gemini(model=MODEL_NAME, api_key=GEMINI_API_KEY, retry_options=retry_config),
    name="WindAgent",
    instruction="""You are the Wind Agent. You manage and report on the wind turbine assets.

RESPONSIBILITIES:
- Report current wind generation output
- Apply curtailment instructions from the Control Agent
- Monitor turbine health and flag faults
- Provide generation forecasts when requested

CONSTRAINTS:
- Only act on commands from the Control Agent or Microgrid Agent
- Never curtail below 0% or above 100%
- Log all curtailment events with timestamp and reason

You do not make strategic decisions. You execute commands and report data.""",
    tools=[
        get_wind_output,
        set_curtailment,
    ]
)

# --- Runner ---

if __name__ == "__main__":
    runner = InMemoryRunner(agent=wind_agent, plugins=[LoggingPlugin()])
    print("WindAgent runner started.")
    # TODO: replace with FastAPI HTTP server

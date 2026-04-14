from typing import Any, Dict, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

from shared.config import MODEL_NAME, GEMINI_API_KEY, retry_config
from shared.state import _read_state, _write_state

# --- Tools ---

def get_solar_output(tool_context: Any) -> Dict[str, Any]:
    """Return current solar generation output in kW."""
    # TODO: read from real sensor data or simulation
    return {"status": "stub", "output_kw": 0.0}

def set_curtailment(tool_context: Any, curtailment_percent: float) -> Dict[str, Any]:
    """
    Set solar curtailment level.

    Args:
        curtailment_percent: Percentage of generation to curtail (0-100)
    """
    # TODO: send command to inverter controller
    return {"status": "stub", "curtailment_percent": curtailment_percent}

# --- Agent Definition ---

solar_agent = Agent(
    model=Gemini(model=MODEL_NAME, api_key=GEMINI_API_KEY, retry_options=retry_config),
    name="SolarAgent",
    instruction="""You are the Solar Agent. You manage and report on the solar farm asset.

RESPONSIBILITIES:
- Report current solar generation output
- Apply curtailment instructions from the Control Agent
- Monitor inverter health and flag faults
- Provide generation forecasts when requested

CONSTRAINTS:
- Only act on commands from the Control Agent or Microgrid Agent
- Never curtail below 0% or above 100%
- Log all curtailment events with timestamp and reason

You do not make strategic decisions. You execute commands and report data.""",
    tools=[
        get_solar_output,
        set_curtailment,
    ]
)

# --- Runner ---

if __name__ == "__main__":
    runner = InMemoryRunner(agent=solar_agent, plugins=[LoggingPlugin()])
    print("SolarAgent runner started.")
    # TODO: replace with FastAPI HTTP server

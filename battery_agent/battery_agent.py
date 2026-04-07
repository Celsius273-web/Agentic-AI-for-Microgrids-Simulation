from typing import Any, Dict, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

from shared.config import MODEL_NAME, GEMINI_API_KEY, retry_config
from shared.state import _read_state, _write_state

# --- Tools ---

def get_battery_status(tool_context: Any) -> Dict[str, Any]:
    """Return current battery state of charge and power flow."""
    # TODO: read from BMS (Battery Management System)
    return {"status": "stub", "soc_percent": 0.0, "power_kw": 0.0, "mode": "idle"}

def set_charge_rate(tool_context: Any, charge_rate_kw: float) -> Dict[str, Any]:
    """
    Set battery charge or discharge rate.

    Args:
        charge_rate_kw: Rate in kW. Positive = charging, negative = discharging.
    """
    # TODO: send command to BMS controller
    return {"status": "stub", "charge_rate_kw": charge_rate_kw}

# --- Agent Definition ---

battery_agent = Agent(
    model=Gemini(model=MODEL_NAME, api_key=GEMINI_API_KEY, retry_options=retry_config),
    name="BatteryAgent",
    instruction="""You are the Battery Agent. You manage and report on the battery energy storage system.

RESPONSIBILITIES:
- Report current state of charge (SOC) and power flow
- Execute charge and discharge commands from the Control Agent
- Monitor battery health, temperature, and cycle count
- Alert the Control Agent if SOC drops below 20% or exceeds 95%

CONSTRAINTS:
- Only act on commands from the Control Agent or Microgrid Agent
- Never discharge below 10% SOC (hard floor for battery health)
- Never charge above 95% SOC
- Log all charge/discharge commands with timestamp and reason

You do not make strategic decisions. You execute commands and report data.""",
    tools=[
        get_battery_status,
        set_charge_rate,
    ]
)

# --- Runner ---

if __name__ == "__main__":
    runner = InMemoryRunner(agent=battery_agent, plugins=[LoggingPlugin()])
    print("BatteryAgent runner started.")
    # TODO: replace with FastAPI HTTP server

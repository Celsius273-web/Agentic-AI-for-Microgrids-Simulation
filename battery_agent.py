from typing import Any, Dict, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

from shared.config import MODEL_NAME, GEMINI_API_KEY, retry_config
from shared.state import _read_state, _write_state
from shared.agent_server import run_agent_server

def get_battery_status(tool_context: Any) -> Dict[str, Any]:
    """Return current battery state of charge and power flow."""
    from shared.state import read_grid_state
    import random
    
    # Get current state or simulate realistic values
    current_state = read_grid_state()
    soc_percent = current_state.get("battery_soc", 50.0)
    
    # Simulate power flow based on SOC
    if soc_percent > 80:
        power_kw = -random.uniform(500, 1500)  # Likely discharging
        mode = "discharging"
    elif soc_percent < 20:
        power_kw = random.uniform(500, 2000)   # Likely charging
        mode = "charging"
    else:
        power_kw = random.uniform(-1000, 1000)  # Variable
        mode = "charging" if power_kw > 0 else "discharging" if power_kw < 0 else "idle"
    
    return {
        "status": "success",
        "soc_percent": soc_percent,
        "power_kw": power_kw,
        "power_mw": power_kw / 1000,
        "mode": mode,
        "capacity_kwh": 5000,  # 5 MWh battery
        "efficiency": 0.95
    }

def set_charge_rate(tool_context: Any, charge_rate_kw: float) -> Dict[str, Any]:
    """
    Set battery charge or discharge rate and update SOC.

    Args:
        charge_rate_kw: Rate in kW. Positive = charging, negative = discharging.
    """
    from shared.state import update_component_state, read_grid_state
    import time
    
    # Get current state
    current_state = read_grid_state()
    current_soc = current_state.get("battery_soc", 50.0)
    
    # Simulate SOC change (simplified - assume 1 hour operation)
    capacity_kwh = 5000  # 5 MWh battery
    soc_change = (charge_rate_kw / capacity_kwh) * 100  # Percent change
    new_soc = max(0.0, min(100.0, current_soc + soc_change))
    
    # Update grid state
    success = update_component_state("battery", soc_percent=new_soc, updated_by="battery-agent")
    
    return {
        "status": "success" if success else "error",
        "charge_rate_kw": charge_rate_kw,
        "charge_rate_mw": charge_rate_kw / 1000,
        "previous_soc": current_soc,
        "new_soc": new_soc,
        "soc_change": soc_change,
        "grid_state_updated": success,
        "timestamp": time.time()
    }

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

if __name__ == "__main__":
    InMemoryRunner(agent=battery_agent, plugins=[LoggingPlugin()])
    run_agent_server()

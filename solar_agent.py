from typing import Any, Dict, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

from shared.config import MODEL_NAME, GEMINI_API_KEY, retry_config
from shared.state import update_component_state, read_grid_state
import random
import time

# --- Tools ---

def get_solar_output(tool_context: Any) -> Dict[str, Any]:
    """Return current solar generation output in MW."""
    # Simulate realistic solar output based on time of day
    import datetime
    current_hour = datetime.datetime.now().hour
    
    # Simple solar curve: peak at noon, zero at night
    if 6 <= current_hour <= 18:  # Daylight hours
        base_output = max(0, 3.0 * (1 - abs(12 - current_hour) / 6))  # Peak 3MW at noon
        # Add some realistic variation
        output_mw = base_output * (0.8 + 0.4 * random.random())
    else:
        output_mw = 0.0
    
    # Update grid state
    success = update_component_state("solar", output_mw=output_mw, updated_by="solar-agent")
    
    return {
        "status": "success" if success else "error", 
        "output_mw": output_mw,
        "output_kw": output_mw * 1000,  # Legacy compatibility
        "grid_state_updated": success,
        "timestamp": datetime.datetime.now().isoformat()
    }

def set_curtailment(tool_context: Any, curtailment_percent: float) -> Dict[str, Any]:
    """
    Set solar curtailment level and update grid state.

    Args:
        curtailment_percent: Percentage of generation to curtail (0-100)
    """
    # Validate curtailment percentage
    curtailment_percent = max(0.0, min(100.0, curtailment_percent))
    
    # Get current output and apply curtailment
    current_state = read_grid_state()
    current_output = current_state.get("solar_mw", 0.0)
    
    # Calculate curtailed output
    curtailed_output = current_output * (1 - curtailment_percent / 100)
    
    # Update grid state with curtailed output
    success = update_component_state("solar", output_mw=curtailed_output, updated_by="solar-agent")
    
    return {
        "status": "success" if success else "error",
        "curtailment_percent": curtailment_percent,
        "original_output_mw": current_output,
        "curtailed_output_mw": curtailed_output,
        "grid_state_updated": success,
        "timestamp": time.time()
    }

def get_solar_forecast(tool_context: Any, forecast_hours: int = 24) -> Dict[str, Any]:
    """
    Provide solar generation forecast.
    
    Args:
        forecast_hours: Number of hours to forecast (default 24)
    """
    import datetime
    
    forecast = []
    current_time = datetime.datetime.now()
    
    for hour in range(forecast_hours):
        forecast_time = current_time + datetime.timedelta(hours=hour)
        forecast_hour = forecast_time.hour
        
        # Simple forecast model
        if 6 <= forecast_hour <= 18:
            base_forecast = max(0, 3.0 * (1 - abs(12 - forecast_hour) / 6))
            # Add weather uncertainty
            forecast_mw = base_forecast * (0.7 + 0.6 * random.random())
        else:
            forecast_mw = 0.0
        
        forecast.append({
            "timestamp": forecast_time.isoformat(),
            "forecast_mw": round(forecast_mw, 2),
            "confidence": random.uniform(0.7, 0.95)
        })
    
    return {
        "status": "success",
        "forecast": forecast,
        "forecast_hours": forecast_hours,
        "generated_at": current_time.isoformat()
    }

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
        get_solar_forecast,
    ]
)

# --- Runner ---

if __name__ == "__main__":
    runner = InMemoryRunner(agent=solar_agent, plugins=[LoggingPlugin()])
    print("SolarAgent runner started.")
    # TODO: replace with FastAPI HTTP server

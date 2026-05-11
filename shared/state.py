import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from shared.config import redis_client

# Redis keys for different data types
LEGACY_STATE_KEY = "microgrid:state"  # Legacy key for backward compatibility
GRID_STATE_KEY = "grid:state"         # New structured grid state for MCP server

def _read_state() -> Dict[str, Any]:
    """Read legacy microgrid state from Redis. Shared across all agent containers."""
    try:
        raw = redis_client.get(LEGACY_STATE_KEY)
        if raw:
            return json.loads(raw)
        return {}
    except Exception as e:
        print(f"Error reading legacy state from Redis: {e}")
        return {}

def _write_state(data: Dict[str, Any]) -> None:
    """Write legacy microgrid state to Redis. Immediately visible to all agent containers."""
    try:
        redis_client.set(LEGACY_STATE_KEY, json.dumps(data))
    except Exception as e:
        print(f"Error writing legacy state to Redis: {e}")

def read_grid_state() -> Dict[str, Any]:
    """
    Read structured grid state from Redis for MCP server.
    
    Returns:
        Dict containing grid state or default values if not found
    """
    try:
        raw = redis_client.get(GRID_STATE_KEY)
        if raw:
            return json.loads(raw)
        
        # Return default grid state if not found
        return {
            "solar_mw": 0.0,
            "wind_mw": 0.0,
            "battery_soc": 50.0,  # Default to 50% SOC
            "load_mw": 0.0,
            "frequency_hz": 60.0,
            "voltage_v": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_updated_by": "default_initialization"
        }
    except Exception as e:
        print(f"Error reading grid state from Redis: {e}")
        return {
            "solar_mw": 0.0,
            "wind_mw": 0.0,
            "battery_soc": 50.0,
            "load_mw": 0.0,
            "frequency_hz": 60.0,
            "voltage_v": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_updated_by": "error_fallback",
            "error": str(e)
        }

def write_grid_state(
    solar_mw: Optional[float] = None,
    wind_mw: Optional[float] = None,
    battery_soc: Optional[float] = None,
    load_mw: Optional[float] = None,
    frequency_hz: Optional[float] = None,
    voltage_v: Optional[float] = None,
    updated_by: str = "unknown_agent"
) -> bool:
    """
    Write structured grid state to Redis for MCP server access.
    Only updates provided values, preserves others.
    
    Args:
        solar_mw: Solar output in MW
        wind_mw: Wind output in MW
        battery_soc: Battery state of charge (0-100%)
        load_mw: Load demand in MW
        frequency_hz: Grid frequency in Hz
        voltage_v: Grid voltage in V
        updated_by: Agent ID that made the update
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read current state to preserve existing values
        current_state = read_grid_state()
        
        # Update only provided values
        if solar_mw is not None:
            current_state["solar_mw"] = solar_mw
        if wind_mw is not None:
            current_state["wind_mw"] = wind_mw
        if battery_soc is not None:
            current_state["battery_soc"] = max(0.0, min(100.0, battery_soc))  # Clamp to 0-100%
        if load_mw is not None:
            current_state["load_mw"] = load_mw
        if frequency_hz is not None:
            current_state["frequency_hz"] = frequency_hz
        if voltage_v is not None:
            current_state["voltage_v"] = voltage_v
        
        # Always update timestamp and source
        current_state["timestamp"] = datetime.now(timezone.utc).isoformat()
        current_state["last_updated_by"] = updated_by
        
        # Write to Redis
        redis_client.set(GRID_STATE_KEY, json.dumps(current_state))
        print(f"Grid state updated by {updated_by}: solar={current_state['solar_mw']}MW, "
              f"wind={current_state['wind_mw']}MW, battery={current_state['battery_soc']}%, "
              f"load={current_state['load_mw']}MW")
        return True
        
    except Exception as e:
        print(f"Error writing grid state to Redis: {e}")
        return False

def update_component_state(component: str, **kwargs) -> bool:
    """
    Update grid state for a specific component.
    
    Args:
        component: Component name (solar, wind, battery, load)
        **kwargs: Component-specific state values
        
    Returns:
        True if successful, False otherwise
    """
    updated_by = kwargs.pop("updated_by", f"{component}-agent")
    
    if component == "solar":
        return write_grid_state(solar_mw=kwargs.get("output_mw"), updated_by=updated_by)
    elif component == "wind":
        return write_grid_state(wind_mw=kwargs.get("output_mw"), updated_by=updated_by)
    elif component == "battery":
        return write_grid_state(
            battery_soc=kwargs.get("soc_percent"),
            updated_by=updated_by
        )
    elif component == "load":
        return write_grid_state(load_mw=kwargs.get("demand_mw"), updated_by=updated_by)
    else:
        print(f"Unknown component: {component}")
        return False

def initialize_grid_state() -> bool:
    """
    Initialize grid state with safe default values.
    
    Returns:
        True if successful, False otherwise
    """
    return write_grid_state(
        solar_mw=0.0,
        wind_mw=0.0,
        battery_soc=50.0,
        load_mw=0.0,
        frequency_hz=60.0,
        voltage_v=120.0,
        updated_by="system_initialization"
    )

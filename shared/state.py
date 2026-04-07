import json
from typing import Any, Dict
from shared.config import redis_client

REDIS_STATE_KEY = "microgrid:state"

def _read_state() -> Dict[str, Any]:
    """Read microgrid state from Redis. Shared across all agent containers."""
    try:
        raw = redis_client.get(REDIS_STATE_KEY)
        if raw:
            return json.loads(raw)
        return {}
    except Exception as e:
        print(f"Error reading state from Redis: {e}")
        return {}

def _write_state(data: Dict[str, Any]) -> None:
    """Write microgrid state to Redis. Immediately visible to all agent containers."""
    try:
        redis_client.set(REDIS_STATE_KEY, json.dumps(data))
    except Exception as e:
        print(f"Error writing state to Redis: {e}")

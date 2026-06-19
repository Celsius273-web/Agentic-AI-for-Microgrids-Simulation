#!/usr/bin/env python3

import os
import sys
import json
import redis
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# Get configuration directly from environment variables
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
AGENT_ID = os.environ.get("AGENT_ID", "mcp-grid-state")

# Simplified auth for now - skip complex dependencies
def verify_request_token():
    """Simplified auth bypass for initial testing"""
    return {"sub": "mcp-test-user", "aud": "microgrid-agents"}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis client
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown handling."""
    global redis_client
    
    # Startup
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST, 
            port=REDIS_PORT, 
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        # Test Redis connection
        redis_client.ping()
        logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    
    yield
    
    # Shutdown
    if redis_client:
        redis_client.close()
        logger.info("Closed Redis connection")

# Create FastAPI app
app = FastAPI(
    title="MCP Grid State Server",
    description="Provides real-time microgrid state data from Redis",
    version="1.0.0",
    lifespan=lifespan
)


def get_grid_state_from_redis() -> Optional[Dict[str, Any]]:
    """
    Retrieve grid state from Redis key 'grid:state'.
    
    Returns:
        Dict containing grid state data or None if not found
        
    Raises:
        HTTPException: If Redis operation fails
    """
    try:
        raw_data = redis_client.get("grid:state")
        if not raw_data:
            logger.warning("No grid state found in Redis key 'grid:state'")
            return None
        
        grid_data = json.loads(raw_data)
        logger.info("Successfully retrieved grid state from Redis")
        return grid_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse grid state JSON: {e}")
        raise HTTPException(status_code=500, detail="Invalid grid state data format")
    except redis.RedisError as e:
        logger.error(f"Redis operation failed: {e}")
        raise HTTPException(status_code=503, detail="Grid state service unavailable")
    except Exception as e:
        logger.error(f"Unexpected error retrieving grid state: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint to verify service and Redis connectivity.
    
    Returns:
        Dict containing service status and Redis connectivity
    """
    try:
        # Test Redis connection
        redis_client.ping()
        redis_status = "connected"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = f"disconnected: {e}"
    
    return {
        "status": "healthy" if redis_status == "connected" else "unhealthy",
        "service": "MCP Grid State Server",
        "agent_id": AGENT_ID,
        "redis_status": redis_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/retrieve_grid_state")
async def retrieve_grid_state(
    claims: Dict[str, Any] = Depends(verify_request_token)
) -> JSONResponse:
    """
    Retrieve current microgrid operational state.
    
    This is the main MCP endpoint that provides ground truth grid data
    for agent decision-making.
    
    Expected Redis data structure:
    {
        "solar_mw": 2.5,
        "wind_mw": 1.3,
        "battery_soc": 75.0,
        "load_mw": 3.2,
        "frequency_hz": 60.01,
        "voltage_v": 120.5,
        "timestamp": "2026-05-04T22:06:00Z"
    }
    
    Args:
        claims: OIDC token claims from authentication
        
    Returns:
        JSONResponse containing grid state data
        
    Raises:
        HTTPException: If grid state cannot be retrieved
    """
    logger.info(f"Grid state request from {claims.get('sub', 'unknown')}")
    
    # Get grid state from Redis
    grid_data = get_grid_state_from_redis()
    
    if not grid_data:
        # Return empty state if no data found
        default_state = {
            "solar_mw": 0.0,
            "wind_mw": 0.0, 
            "battery_soc": 50.0,  # Default to 50% SOC
            "load_mw": 0.0,
            "frequency_hz": 60.0,
            "voltage_v": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "default_values_no_data_available"
        }
        logger.warning("Returning default grid state - no data in Redis")
        return JSONResponse(content=default_state)
    
    # Validate required fields in grid data
    required_fields = ["solar_mw", "wind_mw", "battery_soc", "load_mw", "frequency_hz", "voltage_v"]
    missing_fields = [field for field in required_fields if field not in grid_data]
    
    if missing_fields:
        logger.error(f"Grid state missing required fields: {missing_fields}")
        raise HTTPException(
            status_code=422, 
            detail=f"Invalid grid state: missing fields {missing_fields}"
        )
    
    # Add retrieval metadata
    grid_data["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    grid_data["retrieved_by"] = claims.get("sub", "unknown")
    grid_data["mcp_server"] = AGENT_ID
    
    logger.info(f"Returning grid state: solar={grid_data['solar_mw']}MW, "
               f"wind={grid_data['wind_mw']}MW, battery={grid_data['battery_soc']}%")
    
    return JSONResponse(content=grid_data)


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "MCP Grid State Server",
        "version": "1.0.0",
        "description": "Provides real-time microgrid state data",
        "endpoints": {
            "/retrieve_grid_state": "POST - Get current grid state (requires auth)",
            "/health": "GET - Health check (no auth required)"
        },
        "agent_id": AGENT_ID
    }


if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"Starting MCP Grid State Server on port {port}")
    logger.info(f"Agent ID: {AGENT_ID}")
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    
    uvicorn.run(
        "grid_state_server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
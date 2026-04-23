import os
import redis
import json
from typing import Any, Dict
from google import genai
from google.genai import types

# All values come from environment variables set in docker-compose.yml
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY is not set. Add it to docker-compose.yml under environment:")

APP_NAME = os.environ.get("APP_NAME", "microgrid_control")
USER_ID = os.environ.get("USER_ID", "grid_operator")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash-lite")
AGENT_ID = os.environ.get("AGENT_ID")
JWT_SECRET = os.environ.get("JWT_SECRET")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")   # matches service name in docker-compose.yml
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

# Local Audit Configuration
AUDIT_DB_PATH = os.environ.get("AUDIT_DB_PATH", "audit_trail.db")
ENABLE_LOCAL_INSTRUMENTATION = os.environ.get("ENABLE_LOCAL_INSTRUMENTATION", "true").lower() == "true"

# Agent Authentication and Identity Verification
AGENT_ROLE = os.environ.get("AGENT_ROLE", "control")  # control, researcher, solar, wind, battery, load
VERIFIED_ACCOUNT = os.environ.get("VERIFIED_ACCOUNT", "unauthenticated")

# mTLS Configuration
CERTS_DIR = os.environ.get("CERTS_DIR", "/app/shared/certs")
ENABLE_MTLS = os.environ.get("ENABLE_MTLS", "true").lower() == "true"
VERIFY_PEER_CERTS = os.environ.get("VERIFY_PEER_CERTS", "true").lower() == "true"
MTLS_SERVER_PORT = int(os.environ.get("MTLS_SERVER_PORT", 8443))

# Certificate Paths (auto-constructed based on AGENT_ID)
if AGENT_ID:
    SERVER_CERT = f"{CERTS_DIR}/{AGENT_ID}-server.crt"
    SERVER_KEY = f"{CERTS_DIR}/{AGENT_ID}-server.key"
    CLIENT_CERT = f"{CERTS_DIR}/{AGENT_ID}-client.crt"
    CLIENT_KEY = f"{CERTS_DIR}/{AGENT_ID}-client.key"
else:
    SERVER_CERT = None
    SERVER_KEY = None
    CLIENT_CERT = None
    CLIENT_KEY = None

CA_CERT = f"{CERTS_DIR}/ca.crt"

# Log mTLS configuration on startup instead of in agent code or in Redis
if ENABLE_MTLS:
    print(f"mTLS enabled on port {MTLS_SERVER_PORT}")
    if AGENT_ID:
        print(f"  Server cert: {SERVER_CERT}")
        print(f"  Client cert: {CLIENT_CERT}")
    print(f"  Peer verification: {VERIFY_PEER_CERTS}")

# Shared Redis client - all containers connect to the same Redis service
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Retry config for Gemini API calls
retry_config = types.HttpRetryOptions(attempts=5, exp_base=7, initial_delay=1, http_status_codes=[429, 500, 503, 504])

# GenAI client
client = genai.Client(api_key=GEMINI_API_KEY)

print(f"Agent {AGENT_ID} started. Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
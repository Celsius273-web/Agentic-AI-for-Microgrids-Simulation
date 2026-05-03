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
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")   # matches service name in docker-compose.yml
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

# Local Audit Configuration
AUDIT_DB_PATH = os.environ.get("AUDIT_DB_PATH", "audit_trail.db")
ENABLE_LOCAL_INSTRUMENTATION = os.environ.get("ENABLE_LOCAL_INSTRUMENTATION", "true").lower() == "true"

# OIDC Authentication Configuration
OIDC_ISSUER = os.environ.get("OIDC_ISSUER")  # Google Cloud issuer URL
OIDC_AUDIENCE = os.environ.get("OIDC_AUDIENCE", "microgrid-agents")  # Service audience claim
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
TOKEN_CACHE_TTL = int(os.environ.get("TOKEN_CACHE_TTL", 300))  # 5 minutes, refresh before expiry
OIDC_KEY_CACHE_TTL = int(os.environ.get("OIDC_KEY_CACHE_TTL", 3600))  # 1 hour for public keys

# Derived OIDC configuration
if OIDC_ISSUER:
    OIDC_DISCOVERY_URL = f"{OIDC_ISSUER}/.well-known/openid_configuration"
else:
    OIDC_DISCOVERY_URL = None

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

# OIDC Configuration Validation
if not OIDC_ISSUER:
    raise EnvironmentError("OIDC_ISSUER is required. Set it to Google Cloud issuer URL (e.g., https://accounts.google.com)")

if GOOGLE_APPLICATION_CREDENTIALS and not os.path.exists(GOOGLE_APPLICATION_CREDENTIALS):
    print(f"WARNING: GOOGLE_APPLICATION_CREDENTIALS file not found: {GOOGLE_APPLICATION_CREDENTIALS}")

# Log OIDC configuration on startup (redact credential paths)
print(f"OIDC Authentication configured:")
print(f"  Issuer: {OIDC_ISSUER}")
print(f"  Audience: {OIDC_AUDIENCE}")
print(f"  Discovery URL: {OIDC_DISCOVERY_URL}")
print(f"  Service Account Creds: {'[CONFIGURED]' if GOOGLE_APPLICATION_CREDENTIALS else '[NOT SET]'}")
print(f"  Token Cache TTL: {TOKEN_CACHE_TTL}s")
print(f"  OIDC Key Cache TTL: {OIDC_KEY_CACHE_TTL}s")

print(f"Agent {AGENT_ID} started. Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
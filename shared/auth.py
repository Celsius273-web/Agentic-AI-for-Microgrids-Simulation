import os
import time
import json
import threading
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import Request, HTTPException, status

# Google Cloud imports - only used when AUTH_MODE is 'cloud'
try:
    from google.auth import default
    from google.oauth2 import service_account
    from google.oauth2.id_token import verify_oauth2_token
    from google.auth.transport.requests import Request as GoogleRequest
    from google.auth.exceptions import GoogleAuthError
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False
    # Create dummy classes to prevent import errors
    class GoogleAuthError(Exception):
        pass

from . import config

# Module-level caches with thread safety
_oidc_metadata_cache = {}
_oidc_keys_cache = {}
_token_cache = {}
_cache_lock = threading.Lock()

def load_service_account_creds():
    """
    Load service account credentials for Google Cloud authentication.
    Only used when AUTH_MODE is 'cloud'.
    
    Returns:
        service_account.Credentials: Loaded service account credentials or None for local mode
        
    Raises:
        EnvironmentError: If credentials cannot be loaded in cloud mode
    """
    if config.AUTH_MODE != "cloud":
        return None
    
    if not GOOGLE_AUTH_AVAILABLE:
        raise EnvironmentError("Google Auth library not available. Install with: pip install google-auth")
        
    try:
        if config.GOOGLE_APPLICATION_CREDENTIALS:
            creds = service_account.Credentials.from_service_account_file(
                config.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=['openid', 'email', 'profile']
            )
        else:
            # Fall back to default credentials (ADC)
            creds, _ = default(scopes=['openid', 'email', 'profile'])
        
        return creds
    except Exception as e:
        raise EnvironmentError(f"Failed to load service account credentials: {e}")

def get_oidc_discovery_metadata(issuer_url: str) -> Dict[str, Any]:
    """
    Fetch and cache OIDC discovery metadata from issuer.
    
    Args:
        issuer_url: OIDC issuer URL (e.g., https://accounts.google.com)
        
    Returns:
        Dict containing OIDC discovery metadata
        
    Raises:
        ValueError: If metadata cannot be fetched or parsed
    """
    cache_key = f"metadata_{issuer_url}"
    current_time = time.time()
    
    with _cache_lock:
        # Check cache first
        if cache_key in _oidc_metadata_cache:
            cached_data, timestamp = _oidc_metadata_cache[cache_key]
            if current_time - timestamp < config.OIDC_KEY_CACHE_TTL:
                return cached_data
        
        # Fetch fresh metadata
        discovery_url = f"{issuer_url}/.well-known/openid_configuration"
        try:
            response = requests.get(discovery_url, timeout=10)
            response.raise_for_status()
            metadata = response.json()
            
            # Cache the metadata
            _oidc_metadata_cache[cache_key] = (metadata, current_time)
            return metadata
            
        except Exception as e:
            raise ValueError(f"Failed to fetch OIDC discovery metadata from {discovery_url}: {e}")

def _get_oidc_public_keys(jwks_uri: str) -> Dict[str, Any]:
    """
    Fetch and cache OIDC public keys from JWKS endpoint.
    
    Args:
        jwks_uri: JWKS endpoint URL
        
    Returns:
        Dict containing public keys
        
    Raises:
        ValueError: If keys cannot be fetched
    """
    cache_key = f"keys_{jwks_uri}"
    current_time = time.time()
    
    with _cache_lock:
        # Check cache first
        if cache_key in _oidc_keys_cache:
            cached_keys, timestamp = _oidc_keys_cache[cache_key]
            if current_time - timestamp < config.OIDC_KEY_CACHE_TTL:
                return cached_keys
        
        # Fetch fresh keys
        try:
            response = requests.get(jwks_uri, timeout=10)
            response.raise_for_status()
            keys = response.json()
            
            # Cache the keys
            _oidc_keys_cache[cache_key] = (keys, current_time)
            return keys
            
        except Exception as e:
            raise ValueError(f"Failed to fetch OIDC public keys from {jwks_uri}: {e}")

def verify_oidc_token(token: str) -> Dict[str, Any]:
    """
    Verify OIDC token signature and claims.
    Supports both Keycloak and Google Cloud OIDC tokens.
    
    Args:
        token: ID token to verify
        
    Returns:
        Dict containing token claims
        
    Raises:
        ValueError: If token is invalid or verification fails
    """
    try:
        if config.AUTH_MODE == "cloud":
            # Use Google's library for Google Cloud tokens
            if not GOOGLE_AUTH_AVAILABLE:
                raise ValueError("Google Auth library not available for cloud mode")
            claims = verify_oauth2_token(
                token,
                GoogleRequest(),
                audience=config.OIDC_AUDIENCE
            )
        else:
            # For Keycloak or other OIDC providers, use manual verification
            claims = _verify_generic_oidc_token(token)
        
        # Validate issuer
        if claims.get("iss") != config.OIDC_ISSUER:
            raise ValueError(f"Invalid issuer: expected {config.OIDC_ISSUER}, got {claims.get('iss')}")
        
        # Validate audience (more flexible for Keycloak)
        token_aud = claims.get("aud")
        if isinstance(token_aud, list):
            if config.OIDC_AUDIENCE not in token_aud:
                raise ValueError(f"Invalid audience: expected {config.OIDC_AUDIENCE} in {token_aud}")
        else:
            if token_aud != config.OIDC_AUDIENCE:
                raise ValueError(f"Invalid audience: expected {config.OIDC_AUDIENCE}, got {token_aud}")
        
        # Add timestamp for audit trail
        claims["verified_at"] = datetime.now(timezone.utc).isoformat()
        
        return claims
        
    except GoogleAuthError as e:
        raise ValueError(f"OIDC token verification failed: {e}")
    except Exception as e:
        raise ValueError(f"Token verification error: {e}")

def _verify_generic_oidc_token(token: str) -> Dict[str, Any]:
    """
    Verify OIDC token using generic JWKS verification for non-Google providers.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Dict containing token claims
        
    Raises:
        ValueError: If token verification fails
    """
    import jwt
    from jwt.algorithms import RSAAlgorithm
    
    # Get discovery metadata and public keys
    metadata = get_oidc_discovery_metadata(config.OIDC_ISSUER)
    jwks_uri = metadata.get("jwks_uri")
    if not jwks_uri:
        raise ValueError("No jwks_uri found in OIDC discovery metadata")
    
    jwks = _get_oidc_public_keys(jwks_uri)
    
    # Decode token header to get key ID
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    
    # Find the public key
    public_key = None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            public_key = RSAAlgorithm.from_jwk(key)
            break
    
    if not public_key:
        raise ValueError(f"Public key not found for kid: {kid}")
    
    # Verify and decode token
    claims = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience=config.OIDC_AUDIENCE,
        issuer=config.OIDC_ISSUER,
        options={"verify_exp": True, "verify_iat": True}
    )
    
    return claims

def _get_keycloak_client_token() -> str:
    """
    Get client credentials token from Keycloak for service-to-service auth.
    
    Returns:
        str: Access token for Authorization header
        
    Raises:
        ValueError: If token generation fails
    """
    cache_key = "keycloak_client_token"
    current_time = time.time()
    
    with _cache_lock:
        # Check cache first (refresh at 80% TTL)
        if cache_key in _token_cache:
            cached_token, timestamp, ttl = _token_cache[cache_key]
            refresh_threshold = ttl * 0.8
            if current_time - timestamp < refresh_threshold:
                return cached_token
    
    # Get fresh token from Keycloak
    try:
        token_url = f"{config.OIDC_ISSUER}/protocol/openid-connect/token"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': config.KEYCLOAK_CLIENT_ID,
            'client_secret': config.KEYCLOAK_CLIENT_SECRET,
            'scope': 'openid email profile'
        }
        
        response = requests.post(token_url, data=data, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in', config.TOKEN_CACHE_TTL)
        
        if not access_token:
            raise ValueError("No access token in Keycloak response")
        
        # Cache the token
        with _cache_lock:
            _token_cache[cache_key] = (access_token, current_time, expires_in)
        
        return access_token
        
    except Exception as e:
        raise ValueError(f"Failed to get Keycloak client token: {e}")

def get_service_account_token() -> str:
    """
    Generate fresh access token for outbound service-to-service calls.
    Supports both Keycloak (local) and Google Cloud (cloud) authentication modes.
    Uses caching with TTL to avoid unnecessary token generation.
    
    Returns:
        str: Access token for Authorization header
        
    Raises:
        ValueError: If token generation fails
    """
    if config.AUTH_MODE == "local":
        return _get_keycloak_client_token()
    elif config.AUTH_MODE == "cloud":
        return _get_google_service_account_token()
    else:
        raise ValueError(f"Unsupported AUTH_MODE: {config.AUTH_MODE}")

def _get_google_service_account_token() -> str:
    """
    Generate Google Cloud service account token for cloud mode.
    
    Returns:
        str: Google Cloud access token
        
    Raises:
        ValueError: If token generation fails
    """
    cache_key = "google_service_account_token"
    current_time = time.time()
    
    with _cache_lock:
        # Check cache first (refresh at 80% TTL)
        if cache_key in _token_cache:
            cached_token, timestamp, ttl = _token_cache[cache_key]
            refresh_threshold = ttl * 0.8
            if current_time - timestamp < refresh_threshold:
                return cached_token
    
    # Generate fresh token
    try:
        creds = load_service_account_creds()
        if not creds:
            raise ValueError("No service account credentials available")
        
        # Refresh credentials to get access token
        if not creds.valid or creds.expired:
            creds.refresh(GoogleRequest())
        
        token = creds.token
        
        # Cache the token (use config TTL)
        with _cache_lock:
            _token_cache[cache_key] = (token, current_time, config.TOKEN_CACHE_TTL)
        
        return token
        
    except Exception as e:
        raise ValueError(f"Failed to generate Google service account token: {e}")

def inject_verified_identity(invocation_context: Dict[str, Any], token_claims: Dict[str, Any]) -> None:
    """
    Inject verified OIDC identity into invocation context for audit trail.
    
    Args:
        invocation_context: Tool invocation context to update
        token_claims: Verified OIDC token claims
    """
    if not invocation_context:
        invocation_context = {}
    
    invocation_context.update({
        "verified_account": token_claims.get("sub", "unknown"),
        "verified_email": token_claims.get("email"),
        "oidc_claims": token_claims,
        "auth_method": "oidc",
        "verification_timestamp": token_claims.get("verified_at")
    })

async def verify_request_token(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency to verify OIDC tokens on incoming requests.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dict containing verified token claims
        
    Raises:
        HTTPException: If authentication fails
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header"
        )
    
    token = auth_header.split(" ")[1]
    
    try:
        claims = verify_oidc_token(token)
        return claims
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OIDC token verification failed: {e}"
        )

# Legacy function name for compatibility
async def verify_request(request: Request) -> Dict[str, Any]:
    """Legacy wrapper for verify_request_token."""
    return await verify_request_token(request)
import os
import time
import json
import threading
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import Request, HTTPException, status
from google.auth import default
from google.oauth2 import service_account
from google.oauth2.id_token import verify_oauth2_token
from google.auth.transport.requests import Request as GoogleRequest
from google.auth.exceptions import GoogleAuthError

from . import config

# Module-level caches with thread safety
_oidc_metadata_cache = {}
_oidc_keys_cache = {}
_token_cache = {}
_cache_lock = threading.Lock()

def load_service_account_creds() -> service_account.Credentials:
    """
    Load service account credentials from GOOGLE_APPLICATION_CREDENTIALS.
    
    Returns:
        service_account.Credentials: Loaded service account credentials
        
    Raises:
        EnvironmentError: If credentials cannot be loaded
    """
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
    
    Args:
        token: ID token to verify
        
    Returns:
        Dict containing token claims
        
    Raises:
        ValueError: If token is invalid or verification fails
    """
    try:
        # Get discovery metadata for the issuer
        metadata = get_oidc_discovery_metadata(config.OIDC_ISSUER)
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise ValueError("No jwks_uri found in OIDC discovery metadata")
        
        # Verify token using Google's library
        # This handles signature verification, expiry, and standard claims
        claims = verify_oauth2_token(
            token,
            GoogleRequest(),
            audience=config.OIDC_AUDIENCE
        )
        
        # Validate issuer
        if claims.get("iss") != config.OIDC_ISSUER:
            raise ValueError(f"Invalid issuer: expected {config.OIDC_ISSUER}, got {claims.get('iss')}")
        
        # Validate audience
        if claims.get("aud") != config.OIDC_AUDIENCE:
            raise ValueError(f"Invalid audience: expected {config.OIDC_AUDIENCE}, got {claims.get('aud')}")
        
        # Add timestamp for audit trail
        claims["verified_at"] = datetime.now(timezone.utc).isoformat()
        
        return claims
        
    except GoogleAuthError as e:
        raise ValueError(f"OIDC token verification failed: {e}")
    except Exception as e:
        raise ValueError(f"Token verification error: {e}")

def get_service_account_token() -> str:
    """
    Generate fresh access token for outbound service-to-service calls.
    Uses caching with TTL to avoid unnecessary token generation.
    
    Returns:
        str: Access token for Authorization header
        
    Raises:
        ValueError: If token generation fails
    """
    cache_key = "service_account_token"
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
        
        # Refresh credentials to get access token
        if not creds.valid or creds.expired:
            creds.refresh(GoogleRequest())
        
        token = creds.token
        
        # Cache the token (use config TTL)
        with _cache_lock:
            _token_cache[cache_key] = (token, current_time, config.TOKEN_CACHE_TTL)
        
        return token
        
    except Exception as e:
        raise ValueError(f"Failed to generate service account token: {e}")

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
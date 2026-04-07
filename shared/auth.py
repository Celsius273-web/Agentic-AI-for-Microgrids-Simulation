import os
import jwt
import datetime
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET")
MODE = os.getenv("MODE", "jwt").lower()  # 'jwt' for local, 'oidc' for cloud
ALGORITHM = "HS256"
if MODE == "jwt" and JWT_SECRET and len(JWT_SECRET) < 32:
    raise EnvironmentError("JWT_SECRET must be at least 32 characters.")

def verify_token(token: str) -> Dict[str, Any]:
    """Validates a JWT. Raises ValueError on failure."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise ValueError("Token has expired")
    except InvalidTokenError:
        raise ValueError("Invalid token signature")

async def verify_request(request: Request) -> Dict[str, Any]:
    """FastAPI dependency to secure agent endpoints."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header"
        )
    token = auth_header.split(" ")[1]
    if MODE == "oidc":
        # TODO: implement google.oauth2.id_token.verify_oauth2_token
        print("WARNING: OIDC mode is a stub. Do not use in production.")
        return {"agent_id": "oidc_verified_agent", "role": "verified"}
    try:
        return verify_token(token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
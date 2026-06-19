from __future__ import annotations

import contextvars
import uuid
from typing import Any, Dict, Optional

_audit_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "audit_context",
    default=None,
)


def begin_audit_invocation(
    *,
    source: str,
    oidc_claims: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> str:
    rid = request_id or str(uuid.uuid4())
    _audit_context.set(
        {
            "request_id": rid,
            "source": source,
            "oidc_claims": oidc_claims,
        }
    )
    return rid


def get_audit_context() -> Dict[str, Any]:
    """Return current invocation audit context or empty dict."""
    ctx = _audit_context.get()
    return dict(ctx) if ctx else {}


def clear_audit_invocation() -> None:
    """Clear invocation context after a run completes."""
    _audit_context.set(None)

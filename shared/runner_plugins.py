"""Shared ADK plugin wiring for all agent entry points."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from google.adk.plugins.logging_plugin import LoggingPlugin

from shared.config import (
    AUDIT_DB_PATH,
    ENABLE_LOCAL_INSTRUMENTATION,
    VERIFIED_ACCOUNT,
)

# Chat UI agent key -> (agent_id, agent_role)
CHAT_AGENT_PROFILES: Dict[str, Tuple[str, str]] = {
    "microgrid": ("microgrid-agent", "control"),
    "researcher": ("researcher-agent", "researcher"),
    "monitor": ("monitor-agent", "monitor"),
}


def build_adk_plugins(
    agent_id: str,
    agent_role: str,
    verified_account: Optional[str] = None,
    *,
    enable_console_audit: bool = False,
) -> List[Any]:
    """
    Build the standard plugin list for InMemoryRunner.

    Always includes ADK LoggingPlugin. Adds GlobalInstrumentationPlugin when
    ENABLE_LOCAL_INSTRUMENTATION is true (writes to SQLite at AUDIT_DB_PATH).
    """
    plugins: List[Any] = [LoggingPlugin()]

    if not ENABLE_LOCAL_INSTRUMENTATION:
        return plugins

    try:
        from shared.instrumentation_plugin import GlobalInstrumentationPlugin

        plugins.append(
            GlobalInstrumentationPlugin(
                agent_id=agent_id,
                agent_role=agent_role,
                verified_account=verified_account or VERIFIED_ACCOUNT,
                db_path=AUDIT_DB_PATH,
                enable_local_logging=enable_console_audit,
            )
        )
    except ImportError as exc:
        print(f"GlobalInstrumentationPlugin unavailable: {exc}")

    return plugins


def plugins_for_chat_agent(chat_agent_key: str, oidc_claims: Optional[Dict[str, Any]] = None) -> List[Any]:
    """Plugins for chat_server runners keyed by UI agent selection."""
    if chat_agent_key not in CHAT_AGENT_PROFILES:
        raise ValueError(f"Unknown chat agent: {chat_agent_key}")
    agent_id, agent_role = CHAT_AGENT_PROFILES[chat_agent_key]
    account = None
    if oidc_claims:
        account = oidc_claims.get("sub") or oidc_claims.get("preferred_username")
    return build_adk_plugins(
        agent_id=agent_id,
        agent_role=agent_role,
        verified_account=account,
        enable_console_audit=False,
    )

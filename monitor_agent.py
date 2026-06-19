import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
for _p in (_root / "src", _root):
    _entry = str(_p)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from typing import Any, Dict, List, Optional

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from shared.config import (
    MODEL_NAME,
    GEMINI_API_KEY,
    retry_config,
    AGENT_ID,
    AGENT_ROLE,
    VERIFIED_ACCOUNT,
)
from shared.runner_plugins import build_adk_plugins
from shared.agent_interfaces import RAG_access, retrieve_grid_state
from shared.agent_server import run_agent_server
from shared.control_decisions import (
    list_control_decisions,
    list_operator_alerts,
    mark_decision_reviewed,
)
from shared.monitor_comms import deliver_kqml_inform, raise_operator_issue
from shared.monitor_data import (
    get_control_audit_trail,
    get_control_kqml_thread,
    get_monitoring_context_bundle,
    get_operational_context,
)
from shared.monitor_instruction import MONITOR_INSTRUCTION


def get_monitoring_context(
    tool_context: Any,
    decision_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Load grid state, control decision, audit trail, KQML thread, and priorities."""
    return get_monitoring_context_bundle(decision_id)


def review_unreviewed_decisions(
    tool_context: Any,
    limit: int = 5,
) -> Dict[str, Any]:
    """List control decisions pending Monitor review with context for the latest."""
    pending = list_control_decisions(limit=limit, unreviewed_only=True)
    bundles = []
    for d in pending.get("decisions", []):
        bundles.append(
            get_monitoring_context_bundle(d.get("decision_id"))
        )
    return {
        "status": "success",
        "pending_count": pending.get("count", 0),
        "pending_decisions": pending.get("decisions", []),
        "context_bundles": bundles,
    }


def fetch_control_audit_trail(
    tool_context: Any,
    limit: int = 40,
) -> Dict[str, Any]:
    """Control Agent audit events (excludes raw model_end hooks)."""
    return get_control_audit_trail(limit=limit)


def fetch_control_kqml_thread(tool_context: Any, limit: int = 50) -> Dict[str, Any]:
    """KQML timeline involving control-agent."""
    return get_control_kqml_thread(limit=limit)


def fetch_operational_context(tool_context: Any) -> Dict[str, Any]:
    """Human priorities, constraints, and microgrid decision evaluations."""
    return get_operational_context()


def fetch_grid_state(tool_context: Any) -> Dict[str, Any]:
    """Current microgrid state from MCP (with Redis fallback)."""
    return retrieve_grid_state(tool_context)


def query_knowledge_base(
    tool_context: Any,
    query: str,
    top_k: int = 3,
) -> Dict[str, Any]:
    """Search RAG documentation for standards and best practices."""
    return RAG_access(tool_context, query, top_k)


def notify_control_agent(
    tool_context: Any,
    decision_id: str,
    severity: str,
    analysis: str,
    recommendation: Optional[str] = None,
) -> Dict[str, Any]:
    """Send KQML inform to control-agent with decision review feedback."""
    content = analysis
    if recommendation:
        content += f"\n\nRecommendation: {recommendation}"
    return deliver_kqml_inform(
        receiver_id="control-agent",
        subject=f"decision-review-{decision_id}",
        content=content,
        priority=_severity_to_priority(severity),
    )


def notify_microgrid_agent(
    tool_context: Any,
    pattern_type: str,
    analysis: str,
    severity: str = "medium",
) -> Dict[str, Any]:
    """Alert microgrid-agent about systemic patterns."""
    return deliver_kqml_inform(
        receiver_id="microgrid-agent",
        subject=f"system-pattern-alert-{pattern_type}",
        content=analysis,
        priority=_severity_to_priority(severity),
        grid_impact="efficiency",
    )


def flag_operator_issue(
    tool_context: Any,
    severity: str,
    issue_type: str,
    summary: str,
    details: str,
    decision_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Raise an issue for human operators (chat UI / dashboard)."""
    return raise_operator_issue(
        severity=severity,
        issue_type=issue_type,
        summary=summary,
        details=details,
        decision_id=decision_id,
    )


def mark_control_decision_reviewed(
    tool_context: Any,
    decision_id: str,
    review_summary: str,
    issues: List[Dict[str, Any]],
    max_severity: str,
    confidence: str = "medium",
) -> Dict[str, Any]:
    """Record completed Monitor review on a control decision."""
    return mark_decision_reviewed(
        decision_id=decision_id,
        review_summary=review_summary,
        issues=issues,
        max_severity=max_severity,
        confidence=confidence,
    )


def list_open_operator_alerts(tool_context: Any, limit: int = 20) -> Dict[str, Any]:
    """List unacknowledged operator alerts."""
    return list_operator_alerts(limit=limit, open_only=True)


def _severity_to_priority(severity: str) -> str:
    s = (severity or "medium").lower()
    if s == "critical":
        return "critical"
    if s == "high":
        return "high"
    if s == "low":
        return "low"
    return "medium"


monitor_agent = Agent(
    model=Gemini(model=MODEL_NAME, api_key=GEMINI_API_KEY, retry_options=retry_config),
    name="MonitorAgent",
    instruction=MONITOR_INSTRUCTION,
    tools=[
        get_monitoring_context,
        review_unreviewed_decisions,
        fetch_control_audit_trail,
        fetch_control_kqml_thread,
        fetch_operational_context,
        fetch_grid_state,
        query_knowledge_base,
        notify_control_agent,
        notify_microgrid_agent,
        flag_operator_issue,
        mark_control_decision_reviewed,
        list_open_operator_alerts,
    ],
)

if __name__ == "__main__":
    plugins = build_adk_plugins(
        agent_id=AGENT_ID or "monitor-agent",
        agent_role=AGENT_ROLE or "monitor",
        verified_account=VERIFIED_ACCOUNT or "monitor-agent@microgrid.local",
        enable_console_audit=True,
    )
    InMemoryRunner(agent=monitor_agent, plugins=plugins)
    run_agent_server()

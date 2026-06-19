"""Structured Control Agent decisions and Monitor review state in Redis."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.config import redis_client

CONTROL_DECISIONS_KEY = "monitor:control_decisions"
OPERATOR_ALERTS_KEY = "monitor:operator_alerts"
MONITOR_ACTIVITY_KEY = "monitor:activity_log"
MAX_DECISIONS = 200
MAX_ALERTS = 100
MAX_ACTIVITY = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_control_decision(
    action: str,
    rationale: str,
    inputs_considered: Optional[Dict[str, Any]] = None,
    inputs_not_considered: Optional[List[str]] = None,
    commands_issued: Optional[List[Dict[str, Any]]] = None,
    grid_state_snapshot: Optional[Dict[str, Any]] = None,
    expected_outcomes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append a structured decision record for Monitor review."""
    decision_id = str(uuid.uuid4())
    entry = {
        "decision_id": decision_id,
        "timestamp": _now_iso(),
        "agent_id": "control-agent",
        "action": action,
        "rationale": rationale,
        "inputs_considered": inputs_considered or {},
        "inputs_not_considered": inputs_not_considered or [],
        "commands_issued": commands_issued or [],
        "grid_state_snapshot": grid_state_snapshot or {},
        "expected_outcomes": expected_outcomes or {},
        "monitor_reviewed_at": None,
        "monitor_review": None,
    }
    try:
        raw = redis_client.get(CONTROL_DECISIONS_KEY)
        decisions: List[Dict[str, Any]] = json.loads(raw) if raw else []
        decisions.append(entry)
        redis_client.set(CONTROL_DECISIONS_KEY, json.dumps(decisions[-MAX_DECISIONS:]))
        return {"status": "success", "decision_id": decision_id, "decision": entry}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def list_control_decisions(
    limit: int = 20,
    unreviewed_only: bool = False,
) -> Dict[str, Any]:
    """List recent Control Agent decisions."""
    try:
        raw = redis_client.get(CONTROL_DECISIONS_KEY)
        decisions: List[Dict[str, Any]] = json.loads(raw) if raw else []
        if unreviewed_only:
            decisions = [d for d in decisions if not d.get("monitor_reviewed_at")]
        decisions = sorted(decisions, key=lambda d: d.get("timestamp", ""), reverse=True)[:limit]
        return {
            "status": "success",
            "count": len(decisions),
            "decisions": decisions,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "decisions": []}


def get_control_decision(decision_id: str) -> Dict[str, Any]:
    """Fetch one decision by id."""
    try:
        raw = redis_client.get(CONTROL_DECISIONS_KEY)
        for d in json.loads(raw) if raw else []:
            if d.get("decision_id") == decision_id:
                return {"status": "success", "decision": d}
        return {"status": "error", "error": f"Decision not found: {decision_id}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def mark_decision_reviewed(
    decision_id: str,
    review_summary: str,
    issues: List[Dict[str, Any]],
    max_severity: str,
    confidence: str = "medium",
) -> Dict[str, Any]:
    """Store Monitor review on a decision."""
    try:
        raw = redis_client.get(CONTROL_DECISIONS_KEY)
        decisions: List[Dict[str, Any]] = json.loads(raw) if raw else []
        updated = False
        for d in decisions:
            if d.get("decision_id") == decision_id:
                d["monitor_reviewed_at"] = _now_iso()
                d["monitor_review"] = {
                    "summary": review_summary,
                    "issues": issues,
                    "max_severity": max_severity,
                    "confidence": confidence,
                    "reviewed_at": d["monitor_reviewed_at"],
                }
                updated = True
                break
        if not updated:
            return {"status": "error", "error": f"Decision not found: {decision_id}"}
        redis_client.set(CONTROL_DECISIONS_KEY, json.dumps(decisions[-MAX_DECISIONS:]))
        return {"status": "success", "decision_id": decision_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def append_operator_alert(
    severity: str,
    issue_type: str,
    summary: str,
    details: str,
    decision_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Queue an alert for human operators (chat UI / dashboard)."""
    alert = {
        "alert_id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "severity": severity,
        "issue_type": issue_type,
        "summary": summary,
        "details": details,
        "decision_id": decision_id,
        "acknowledged": False,
    }
    try:
        raw = redis_client.get(OPERATOR_ALERTS_KEY)
        alerts: List[Dict[str, Any]] = json.loads(raw) if raw else []
        alerts.insert(0, alert)
        redis_client.set(OPERATOR_ALERTS_KEY, json.dumps(alerts[:MAX_ALERTS]))
        return {"status": "success", "alert": alert}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def list_operator_alerts(limit: int = 20, open_only: bool = True) -> Dict[str, Any]:
    """List operator-facing alerts."""
    try:
        raw = redis_client.get(OPERATOR_ALERTS_KEY)
        alerts: List[Dict[str, Any]] = json.loads(raw) if raw else []
        if open_only:
            alerts = [a for a in alerts if not a.get("acknowledged")]
        return {"status": "success", "count": len(alerts[:limit]), "alerts": alerts[:limit]}
    except Exception as e:
        return {"status": "error", "error": str(e), "alerts": []}


def append_monitor_activity(event_type: str, payload: Dict[str, Any]) -> None:
    """Append a Monitor activity entry for audit visibility."""
    entry = {"timestamp": _now_iso(), "event_type": event_type, **payload}
    try:
        raw = redis_client.get(MONITOR_ACTIVITY_KEY)
        log: List[Dict[str, Any]] = json.loads(raw) if raw else []
        log.insert(0, entry)
        redis_client.set(MONITOR_ACTIVITY_KEY, json.dumps(log[:MAX_ACTIVITY]))
    except Exception:
        pass

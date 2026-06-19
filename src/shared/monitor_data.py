"""Read-only data access for the Monitor Agent (audit, KQML, context)."""

import json
from typing import Any, Dict, List, Optional

from shared.config import AUDIT_DB_PATH
from shared.control_decisions import list_control_decisions, get_control_decision
from shared.state import _read_state, read_grid_state

# Monitor reads skip empty rows after field stripping (see _sanitize_audit_event).
AUDIT_EXCLUDE_HOOKS: set = set()
AUDIT_EXCLUDE_EVENT_TYPES: set = set()
AUDIT_TRUNCATE_FIELDS = {"tool_outputs", "tool_inputs", "extra_context"}


def _truncate_value(value: Any, max_len: int = 2000) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "...[truncated]"
    if isinstance(value, dict):
        return {k: _truncate_value(v, max_len) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_value(v, max_len) for v in value[:50]]
    return value


def _sanitize_audit_event(row: Dict[str, Any]) -> Dict[str, Any]:
    """Drop raw model hooks; truncate large JSON fields."""
    if row.get("hook_name") in AUDIT_EXCLUDE_HOOKS:
        return {}
    if row.get("event_type") in AUDIT_EXCLUDE_EVENT_TYPES:
        return {}
    out = dict(row)
    if out.get("event_type") == "model_inference":
        out["kqml_raw"] = None
        if out.get("extra_context"):
            try:
                extra = json.loads(out["extra_context"]) if isinstance(out["extra_context"], str) else out["extra_context"]
                extra.pop("content", None)
                out["extra_context"] = json.dumps(extra)
            except (json.JSONDecodeError, TypeError):
                pass
    for field in AUDIT_TRUNCATE_FIELDS:
        if out.get(field):
            try:
                parsed = json.loads(out[field]) if isinstance(out[field], str) else out[field]
                out[field] = json.dumps(_truncate_value(parsed))
            except (json.JSONDecodeError, TypeError):
                out[field] = _truncate_value(str(out[field]))
    if out.get("kqml_raw"):
        out["kqml_raw"] = _truncate_value(out["kqml_raw"], 1500)
    return out


def _get_audit_db():
    from shared.local_audit_db import get_shared_audit_db
    return get_shared_audit_db(AUDIT_DB_PATH)


def get_control_audit_trail(
    limit: int = 50,
    event_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Audit events for control-agent without raw model_end hooks."""
    try:
        db = _get_audit_db()
        rows = db.query_events(agent_id="control-agent", event_type=event_type, limit=limit)
        events = [e for e in (_sanitize_audit_event(r) for r in rows) if e]
        return {
            "status": "success",
            "agent_id": "control-agent",
            "count": len(events),
            "events": events,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "events": []}


def get_control_kqml_thread(limit: int = 100) -> Dict[str, Any]:
    """KQML messages where control-agent is sender or receiver."""
    try:
        db = _get_audit_db()
        all_rows = db.query_kqml_timeline()
        thread = []
        for row in all_rows[-limit * 2 :]:
            r = dict(row)
            sender = r.get("sender_agent_id") or ""
            receiver = r.get("receiver_agent_id") or ""
            if "control" in sender or "control" in receiver:
                if r.get("raw_kqml"):
                    r["raw_kqml"] = _truncate_value(r["raw_kqml"], 1500)
                thread.append(r)
        thread = thread[-limit:]
        return {"status": "success", "count": len(thread), "kqml_thread": thread}
    except Exception as e:
        return {"status": "error", "error": str(e), "kqml_thread": []}


def get_operational_context() -> Dict[str, Any]:
    """Human priorities, constraints, and recent microgrid evaluations from Redis."""
    state = _read_state()
    return {
        "status": "success",
        "operational_priorities": state.get("operational_priorities", {}),
        "decision_evaluations": state.get("decision_evaluations", [])[-20:],
        "legacy_grid_state": state.get("grid_state", {}),
    }


def get_monitoring_context_bundle(decision_id: Optional[str] = None) -> Dict[str, Any]:
    """Package grid state, decision, audit, KQML, and priorities for one review."""
    from shared.agent_interfaces import retrieve_grid_state

    grid = retrieve_grid_state(None)
    ops = get_operational_context()
    kqml = get_control_kqml_thread(limit=30)
    audit = get_control_audit_trail(limit=30)

    decision = None
    if decision_id:
        decision = get_control_decision(decision_id)
    else:
        pending = list_control_decisions(limit=1, unreviewed_only=True)
        if pending.get("decisions"):
            decision = {"status": "success", "decision": pending["decisions"][0]}

    return {
        "status": "success",
        "grid_state": grid,
        "operational_context": ops,
        "kqml_thread": kqml,
        "audit_trail": audit,
        "decision": decision,
        "structured_grid": read_grid_state(),
    }

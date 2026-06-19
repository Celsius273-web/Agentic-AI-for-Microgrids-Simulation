"""Monitor outbound KQML and operator notifications."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from shared import config, kqml
from shared.control_decisions import append_monitor_activity, append_operator_alert

RECEIVER_SERVICE_MAP = {
    "control-agent": "control-agent",
    "microgrid-agent": "microgrid-agent",
}


def deliver_kqml_inform(
    receiver_id: str,
    subject: str,
    content: str,
    priority: str = "medium",
    grid_impact: str = "stability",
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build KQML inform for Control or Microgrid agent and record on the timeline.
    Attempts HTTPS delivery when mTLS is configured.
    """
    try:
        msg = kqml.inform(
            sender_id=config.AGENT_ID or "monitor-agent",
            receiver_id=receiver_id,
            subject=subject,
            content=content,
            conversation_id=conversation_id,
            priority=priority,
            grid_impact=grid_impact,
        )
        append_monitor_activity(
            "kqml_inform",
            {
                "receiver_id": receiver_id,
                "subject": subject,
                "conversation_id": msg.conversation_id,
            },
        )

        try:
            from shared.local_audit_db import get_shared_audit_db
            db = get_shared_audit_db(config.AUDIT_DB_PATH)
            db.insert_kqml_performative_enhanced(
                performative_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc).isoformat(),
                conversation_id=msg.conversation_id,
                sender_agent_id=msg.sender_id,
                receiver_agent_id=receiver_id,
                performative_verb="inform",
                raw_kqml=msg.to_string(),
                subject=subject,
                content=content,
                priority=priority,
                grid_impact=grid_impact,
            )
        except Exception:
            pass

        http_status = "not_attempted"
        service = RECEIVER_SERVICE_MAP.get(receiver_id)
        if service and config.ENABLE_MTLS and config.CLIENT_CERT:
            try:
                import requests
                from shared import auth

                token = auth.get_service_account_token()
                url = f"https://{service}:{config.MTLS_SERVER_PORT}/command"
                response = requests.post(
                    url,
                    json=msg.to_dict(),
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    cert=(config.CLIENT_CERT, config.CLIENT_KEY),
                    verify=config.CA_CERT,
                    timeout=15,
                )
                http_status = f"http_{response.status_code}"
            except Exception as exc:
                http_status = f"delivery_failed:{exc}"

        return {
            "status": "success",
            "message_type": "kqml_inform",
            "receiver_id": receiver_id,
            "subject": subject,
            "conversation_id": msg.conversation_id,
            "kqml_message": msg.to_string(),
            "http_delivery": http_status,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def raise_operator_issue(
    severity: str,
    issue_type: str,
    summary: str,
    details: str,
    decision_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Flag an issue for human operators (chat UI reads from Redis)."""
    subject = f"[{severity.upper()}] Issue: {issue_type}"
    result = append_operator_alert(severity, issue_type, summary, details, decision_id)
    if result.get("status") == "success":
        append_monitor_activity(
            "operator_alert",
            {"severity": severity, "issue_type": issue_type, "summary": summary},
        )
        result["operator_subject"] = subject
    return result

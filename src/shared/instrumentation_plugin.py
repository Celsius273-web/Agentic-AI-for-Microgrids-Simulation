"""
Global Instrumentation Plugin for Google ADK
============================================

Implements ADK BasePlugin callbacks and persists lifecycle events to SQLite
(audit_trail.db). Designed for shared use across Docker agents and chat_server.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from typing_extensions import override

try:
    from google.adk.plugins.base_plugin import BasePlugin
    from google.adk.agents.base_agent import BaseAgent
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.events.event import Event
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.adk.tools.base_tool import BaseTool
    from google.adk.tools.tool_context import ToolContext
    from google.genai import types
except ImportError as exc:
    raise ImportError(
        "google-adk is required. Install with: pip install google-adk"
    ) from exc

from shared.audit_context import get_audit_context
from shared.local_audit_db import get_shared_audit_db

MODEL_OUTPUT_MAX_CHARS = 4000


@dataclass
class AuditEvent:
    """Immutable audit event structure for all lifecycle hooks."""

    event_id: str
    timestamp: str
    agent_id: str
    agent_role: str
    event_type: str
    hook_name: str
    verified_account: str
    auth_timestamp: str
    oidc_claims: Optional[Dict[str, Any]] = None
    tool_name: Optional[str] = None
    tool_inputs: Optional[Dict[str, Any]] = None
    tool_outputs: Optional[Dict[str, Any]] = None
    tool_error: Optional[str] = None
    tool_execution_ms: Optional[float] = None
    mcp_operation: Optional[str] = None
    kqml_performative: Optional[str] = None
    kqml_raw: Optional[str] = None
    model_name: Optional[str] = None
    model_input_tokens: Optional[int] = None
    model_output_tokens: Optional[int] = None
    grid_state_snapshot: Optional[Dict[str, Any]] = None
    pricing_data_snapshot: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    extra_context: Dict[str, Any] = field(default_factory=dict)


class GlobalInstrumentationPlugin(BasePlugin):
    """
    ADK plugin that sinks agent lifecycle events to local SQLite.

    Registers hooks: before_run, before/after_tool, after_model, after_run, errors.
    """

    def __init__(
        self,
        agent_id: str,
        agent_role: str = "control",
        verified_account: Optional[str] = None,
        db_path: str = "audit_trail.db",
        enable_local_logging: bool = False,
    ):
        super().__init__(name="global_instrumentation")
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.default_verified_account = verified_account or "unauthenticated"
        self.enable_local_logging = enable_local_logging
        self.audit_db = get_shared_audit_db(db_path)
        self._tool_start_times: Dict[str, float] = {}

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _resolve_identity(self) -> tuple[str, Optional[Dict[str, Any]]]:
        ctx = get_audit_context()
        oidc = ctx.get("oidc_claims")
        account = self.default_verified_account
        if oidc:
            account = oidc.get("sub") or oidc.get("preferred_username") or account
        return account, oidc

    def _request_id(self, invocation_context: Optional[InvocationContext] = None) -> Optional[str]:
        ctx = get_audit_context()
        if ctx.get("request_id"):
            return ctx["request_id"]
        if invocation_context is not None:
            return getattr(invocation_context, "invocation_id", None)
        return None

    def _sink(self, event: AuditEvent, message: str) -> None:
        if self.enable_local_logging:
            print(
                f"[AUDIT:{event.event_type}] {message} | "
                f"agent={event.agent_id} request={event.request_id}"
            )
        self.audit_db.insert_event(event)

    def _build_event(
        self,
        *,
        event_type: str,
        hook_name: str,
        invocation_context: Optional[InvocationContext] = None,
        **fields: Any,
    ) -> AuditEvent:
        account, oidc = self._resolve_identity()
        extra = fields.pop("extra_context", {}) or {}
        if invocation_context is not None:
            extra.setdefault("invocation_id", getattr(invocation_context, "invocation_id", None))
            extra.setdefault("session_id", getattr(getattr(invocation_context, "session", None), "id", None))
        ctx = get_audit_context()
        if ctx.get("source"):
            extra.setdefault("source", ctx["source"])

        return AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=self._utc_now(),
            agent_id=self.agent_id,
            agent_role=self.agent_role,
            event_type=event_type,
            hook_name=hook_name,
            verified_account=account,
            auth_timestamp=self._utc_now(),
            oidc_claims=oidc,
            request_id=self._request_id(invocation_context),
            extra_context=extra,
            **fields,
        )

    @override
    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> Optional[types.Content]:
        event = self._build_event(
            event_type="invocation_start",
            hook_name="before_run_callback",
            invocation_context=invocation_context,
        )
        self._sink(event, "Invocation started")
        return None

    @override
    async def after_run_callback(self, *, invocation_context: InvocationContext) -> None:
        event = self._build_event(
            event_type="invocation_complete",
            hook_name="after_run_callback",
            invocation_context=invocation_context,
        )
        self._sink(event, "Invocation completed")

    @override
    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        tool_key = f"{tool.name}:{tool_context.function_call_id}"
        self._tool_start_times[tool_key] = time.time()
        mcp_op, mcp_data = self._extract_mcp_operation(tool.name, tool_args or {})
        event = self._build_event(
            event_type="tool_invocation",
            hook_name="before_tool_callback",
            tool_name=tool.name,
            tool_inputs=self._sanitize_for_logging(tool_args),
            mcp_operation=mcp_op,
            grid_state_snapshot=mcp_data.get("grid_state"),
            pricing_data_snapshot=mcp_data.get("pricing_data"),
            extra_context={
                "mcp_data": mcp_data,
                "callback_agent": tool_context.agent_name,
            },
        )
        self._sink(event, f"Tool start: {tool.name}")
        return None

    @override
    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> Optional[dict]:
        tool_key = f"{tool.name}:{tool_context.function_call_id}"
        started = self._tool_start_times.pop(tool_key, None)
        elapsed_ms = (time.time() - started) * 1000 if started else None
        event = self._build_event(
            event_type="tool_completion",
            hook_name="after_tool_callback",
            tool_name=tool.name,
            tool_inputs=self._sanitize_for_logging(tool_args),
            tool_outputs=self._sanitize_for_logging(self._normalize_tool_result(result)),
            tool_execution_ms=elapsed_ms,
        )
        self._sink(event, f"Tool complete: {tool.name}")
        return None

    @override
    async def on_tool_error_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        error: Exception,
    ) -> Optional[dict]:
        tool_key = f"{tool.name}:{tool_context.function_call_id}"
        started = self._tool_start_times.pop(tool_key, None)
        elapsed_ms = (time.time() - started) * 1000 if started else None
        event = self._build_event(
            event_type="tool_error",
            hook_name="on_tool_error_callback",
            tool_name=tool.name,
            tool_inputs=self._sanitize_for_logging(tool_args),
            tool_error=str(error),
            tool_execution_ms=elapsed_ms,
        )
        self._sink(event, f"Tool error: {tool.name}")
        return None

    @override
    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        text = self._truncate(self._llm_content_to_text(llm_response.content))
        usage = self._usage_dict(llm_response)
        model_output = {"content": text, "error_code": llm_response.error_code}
        kqml_messages = self._extract_kqml_messages(model_output)
        kqml_perf = kqml_messages[0]["performative"] if kqml_messages else "unclassified"
        kqml_raw = self._truncate(kqml_messages[0]["raw_kqml"]) if kqml_messages else ""

        event = self._build_event(
            event_type="model_inference",
            hook_name="after_model_callback",
            model_name=llm_response.model_version,
            model_input_tokens=usage.get("input_tokens"),
            model_output_tokens=usage.get("output_tokens"),
            kqml_performative=kqml_perf,
            kqml_raw=kqml_raw,
            extra_context={
                "callback_agent": callback_context.agent_name,
                "partial": llm_response.partial,
                "content_length": len(text),
                "kqml_count": len(kqml_messages),
            },
        )
        self._sink(event, f"Model response ({callback_context.agent_name})")

        for kqml_msg in kqml_messages:
            self._store_kqml_in_timeline(kqml_msg)

        return None

    @override
    async def on_model_error_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
        error: Exception,
    ) -> Optional[LlmResponse]:
        event = self._build_event(
            event_type="model_error",
            hook_name="on_model_error_callback",
            model_name=llm_request.model,
            tool_error=str(error),
            extra_context={"callback_agent": callback_context.agent_name},
        )
        self._sink(event, f"Model error: {error}")
        return None

    def _normalize_tool_result(self, result: Any) -> Any:
        if isinstance(result, dict):
            return result
        return {"result": result}

    def _llm_content_to_text(self, content: Optional[types.Content]) -> str:
        if content is None:
            return ""
        parts: List[str] = []
        if getattr(content, "parts", None):
            for part in content.parts:
                if getattr(part, "text", None):
                    parts.append(part.text)
        return "\n".join(parts) if parts else str(content)

    def _usage_dict(self, llm_response: LlmResponse) -> Dict[str, Optional[int]]:
        meta = llm_response.usage_metadata
        if not meta:
            return {}
        return {
            "input_tokens": getattr(meta, "prompt_token_count", None),
            "output_tokens": getattr(meta, "candidates_token_count", None),
            "total_tokens": getattr(meta, "total_token_count", None),
        }

    def _truncate(self, value: str, max_len: int = MODEL_OUTPUT_MAX_CHARS) -> str:
        if len(value) <= max_len:
            return value
        return value[:max_len] + "...[truncated]"

    def _extract_mcp_operation(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        mcp_data: Dict[str, Any] = {}
        name_lower = tool_name.lower()

        if "retrieve_grid_state" in name_lower or "fetch_grid_state" in name_lower:
            mcp_data["grid_state"] = tool_input.get("grid_state") or tool_input
            mcp_data["mcp_server"] = "mcp-grid-state"
            return "retrieve_grid_state", mcp_data

        if "record_control_decision" in name_lower:
            mcp_data["control_decision"] = {
                "action": tool_input.get("action"),
                "rationale": tool_input.get("rationale"),
            }
            return "record_control_decision", mcp_data

        if any(
            t in name_lower
            for t in (
                "notify_control",
                "notify_microgrid",
                "send_grid",
                "flag_operator",
                "mark_control_decision",
            )
        ):
            mcp_data["monitor_communication"] = tool_input
            return "monitor_communication", mcp_data

        if "rag_access" in name_lower or "query_knowledge" in name_lower:
            mcp_data["rag_query"] = tool_input.get("query") or tool_input.get("query_text")
            return "rag_query", mcp_data

        mcp_data["tool_context"] = {"input_keys": list(tool_input.keys()) if tool_input else []}
        return "other_operation", mcp_data

    def _extract_kqml_messages(self, model_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        from shared import kqml as kqml_mod

        text = model_output.get("content", "") if isinstance(model_output, dict) else str(model_output)
        kqml_messages: List[Dict[str, Any]] = []
        for match in re.findall(r"\([^)]+\)", text):
            try:
                msg = kqml_mod.parse_kqml(match)
                kqml_messages.append(
                    {
                        "performative": msg.performative,
                        "raw_kqml": match,
                        "sender_id": msg.sender_id,
                        "receiver_id": msg.receiver_id,
                        "conversation_id": msg.conversation_id,
                        "subject": msg.subject,
                        "content": msg.content,
                        "priority": msg.priority,
                        "grid_impact": msg.grid_impact,
                        "affected_components": msg.affected_components,
                    }
                )
            except Exception:
                continue

        if not kqml_messages:
            text_lower = text.lower()
            for perf in ("propose", "accept", "reject", "inform", "query", "answer", "request"):
                if perf in text_lower:
                    kqml_messages.append(
                        {
                            "performative": perf,
                            "raw_kqml": self._truncate(text),
                            "sender_id": self.agent_id,
                            "receiver_id": "unknown",
                            "conversation_id": "inferred",
                        }
                    )
                    break
        return kqml_messages

    def _store_kqml_in_timeline(self, kqml_data: Dict[str, Any]) -> None:
        try:
            self.audit_db.insert_kqml_performative_enhanced(
                performative_id=str(uuid.uuid4()),
                timestamp=self._utc_now(),
                conversation_id=kqml_data.get("conversation_id", "unknown"),
                sender_agent_id=kqml_data.get("sender_id", self.agent_id),
                receiver_agent_id=kqml_data.get("receiver_id", "unknown"),
                performative_verb=kqml_data.get("performative", "unknown"),
                raw_kqml=kqml_data.get("raw_kqml", ""),
                subject=kqml_data.get("subject"),
                content=kqml_data.get("content"),
                priority=kqml_data.get("priority"),
                grid_impact=kqml_data.get("grid_impact"),
                affected_components=kqml_data.get("affected_components"),
            )
        except Exception as exc:
            print(f"Warning: KQML timeline insert failed: {exc}")

    def _sanitize_for_logging(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                key: (
                    "[REDACTED]"
                    if any(s in key.lower() for s in ("key", "secret", "token", "password"))
                    else self._sanitize_for_logging(value)
                )
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [self._sanitize_for_logging(item) for item in data[:100]]
        return data

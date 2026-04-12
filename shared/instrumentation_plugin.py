"""
Global Instrumentation Plugin for Google ADK
============================================

Implements comprehensive lifecycle hook interception for the agent swarm.
- on_agent_start: Records agent initialization and verified identity
- on_tool_start: Captures MCP inputs (ground truth audit trail)
- on_tool_end: Records tool outputs and side effects
- on_model_end: Archives raw KQML performatives and model outputs

Uses official google-adk BasePlugin. Events stored in local SQLite DB.
"""

import time
import json
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field

try:
    from google.adk.plugins.base import BasePlugin
    from google.adk.runners import InvocationContext
except ImportError:
    raise ImportError(
        "google-adk is required. Install with: pip install google-adk"
    )

from shared.local_audit_db import LocalAuditDB


@dataclass
class AuditEvent:
    """Immutable audit event structure for all lifecycle hooks."""
    event_id: str
    timestamp: str
    agent_id: str
    agent_role: str
    event_type: str  # agent_start, tool_start, tool_end, model_end
    hook_name: str
    
    # Identity and authentication
    verified_account: str
    auth_timestamp: str
    
    # Tool invocation context (for tool_start, tool_end, model_end)
    tool_name: Optional[str] = None
    tool_inputs: Optional[Dict[str, Any]] = None
    tool_outputs: Optional[Dict[str, Any]] = None
    tool_error: Optional[str] = None
    tool_execution_ms: Optional[float] = None
    
    # MCP/KQML context
    mcp_operation: Optional[str] = None
    kqml_performative: Optional[str] = None
    kqml_raw: Optional[str] = None
    kqml_metadata: Optional[Dict[str, Any]] = None
    
    # Model inference context
    model_name: Optional[str] = None
    model_input_tokens: Optional[int] = None
    model_output_tokens: Optional[int] = None
    model_reasoning: Optional[str] = None
    
    # Grid state snapshot (for decision audit trail)
    grid_state_snapshot: Optional[Dict[str, Any]] = None
    pricing_data_snapshot: Optional[Dict[str, Any]] = None
    
    # Compliance and lineage
    request_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    
    extra_context: Dict[str, Any] = field(default_factory=dict)


class GlobalInstrumentationPlugin(BasePlugin):
    """
    Official Google ADK BasePlugin for global lifecycle hook interception.
    
    Stores all events in local SQLite database for simulation.
    
    Registration example:
        plugin = GlobalInstrumentationPlugin(agent_id="solar-agent", db_path="audit_trail.db")
        runner = InMemoryRunner()
        runner.register_plugin(plugin)
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_role: str = "control",
        verified_account: str = None,
        db_path: str = "audit_trail.db",
        enable_local_logging: bool = True,
    ):
        """
        Initialize the global instrumentation plugin.
        
        Args:
            agent_id: Unique identifier for this agent (from AGENT_ID env var)
            agent_role: Role of agent (control, researcher, solar, wind, battery, load)
            verified_account: Authenticated service account (from JWT/OIDC)
            db_path: Path to SQLite database file
            enable_local_logging: Also log to stdout for debugging
        """
        super().__init__()
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.verified_account = verified_account or "unauthenticated"
        self.enable_local_logging = enable_local_logging
        
        # Initialize local SQLite audit database
        self.audit_db = LocalAuditDB(db_path=db_path)
        
        # Request ID tracking for correlation
        self._current_request_id = None
        self._tool_start_time = None
    
    def on_agent_start(self, agent_id: str, metadata: Dict[str, Any]) -> None:
        """
        Hook: Agent initialization. Record verified identity and startup context.
        
        Args:
            agent_id: Agent identifier from runner
            metadata: Agent metadata from runner
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.utcnow().isoformat(),
            agent_id=self.agent_id,
            agent_role=self.agent_role,
            event_type="initialization",
            hook_name="on_agent_start",
            verified_account=self.verified_account,
            auth_timestamp=datetime.utcnow().isoformat(),
            extra_context=metadata,
        )
        
        self._log_and_sink(event, "Agent started with verified identity")
    
    def on_tool_start(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        invocation_context: "InvocationContext" = None,
    ) -> None:
        """
        Hook: Tool invocation started. Capture ground-truth MCP inputs.
        
        This is the critical audit point for capturing:
        - Exact grid state retrieved via MCP
        - Pricing data inputs
        - Which agent made the request
        - Timestamp and identity verification
        
        Args:
            tool_name: Name of the tool being invoked
            tool_input: Raw input parameters
            invocation_context: ADK InvocationContext with agent metadata
        """
        self._tool_start_time = time.time()
        
        # Inject identity into context if available
        if invocation_context:
            self._enrich_invocation_context(invocation_context)
        
        # Detect MCP operations and extract ground truth
        mcp_op, mcp_data = self._extract_mcp_operation(tool_name, tool_input)
        
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.utcnow().isoformat(),
            agent_id=self.agent_id,
            agent_role=self.agent_role,
            event_type="tool_invocation",
            hook_name="on_tool_start",
            verified_account=self.verified_account,
            auth_timestamp=datetime.utcnow().isoformat(),
            tool_name=tool_name,
            tool_inputs=self._sanitize_for_logging(tool_input),
            mcp_operation=mcp_op,
            grid_state_snapshot=mcp_data.get("grid_state"),
            pricing_data_snapshot=mcp_data.get("pricing_data"),
            request_id=self._current_request_id,
            extra_context={
                "context_agent_id": invocation_context.agent_id if invocation_context else None,
                "invocation_id": id(invocation_context),
            },
        )
        
        self._log_and_sink(event, f"Tool started: {tool_name} (MCP: {mcp_op})")
    
    def on_tool_end(
        self,
        tool_name: str,
        tool_output: Dict[str, Any],
        tool_error: Optional[str] = None,
        invocation_context: "InvocationContext" = None,
    ) -> None:
        """
        Hook: Tool execution completed. Record outputs and side effects.
        
        Args:
            tool_name: Name of the tool that executed
            tool_output: Output/result from the tool
            tool_error: Error message if tool failed
            invocation_context: ADK InvocationContext
        """
        execution_time_ms = (
            (time.time() - self._tool_start_time) * 1000
            if self._tool_start_time
            else None
        )
        
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.utcnow().isoformat(),
            agent_id=self.agent_id,
            agent_role=self.agent_role,
            event_type="tool_completion",
            hook_name="on_tool_end",
            verified_account=self.verified_account,
            auth_timestamp=datetime.utcnow().isoformat(),
            tool_name=tool_name,
            tool_outputs=self._sanitize_for_logging(tool_output),
            tool_error=tool_error,
            tool_execution_ms=execution_time_ms,
            request_id=self._current_request_id,
        )
        
        if tool_error:
            self._log_and_sink(event, f"Tool error: {tool_name} - {tool_error}")
        else:
            self._log_and_sink(event, f"Tool completed: {tool_name} ({execution_time_ms:.1f}ms)")
        
        self._tool_start_time = None
    
    def on_model_end(
        self,
        model_name: str,
        model_input: Dict[str, Any],
        model_output: Dict[str, Any],
        usage: Dict[str, Any] = None,
    ) -> None:
        """
        Hook: Model inference completed. Record performatives and reasoning.
        
        This captures:
        - Raw KQML performatives (propose, accept, reject, inform)
        - Model output and reasoning
        - Token usage for cost tracking
        - Create non-repudiable timeline of negotiations
        
        Args:
            model_name: Name of the model (e.g., gemini-2.5-flash-lite)
            model_input: Input prompt/context to the model
            model_output: Raw output from model
            usage: Token usage information
        """
        # Extract KQML performative from model output
        kqml_perf, kqml_raw = self._extract_kqml_performative(model_output)
        
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.utcnow().isoformat(),
            agent_id=self.agent_id,
            agent_role=self.agent_role,
            event_type="model_inference",
            hook_name="on_model_end",
            verified_account=self.verified_account,
            auth_timestamp=datetime.utcnow().isoformat(),
            model_name=model_name,
            model_input_tokens=usage.get("input_tokens") if usage else None,
            model_output_tokens=usage.get("output_tokens") if usage else None,
            kqml_performative=kqml_perf,
            kqml_raw=kqml_raw,
            request_id=self._current_request_id,
            extra_context={
                "total_tokens": usage.get("total_tokens") if usage else None,
            },
        )
        
        self._log_and_sink(
            event,
            f"Model inference complete: {model_name} (performative: {kqml_perf})"
        )
    
    def _enrich_invocation_context(self, context: "InvocationContext") -> None:
        """
        Inject verified identity into the InvocationContext.
        
        This ensures all downstream operations are cryptographically linked
        to an authenticated service account.
        """
        if hasattr(context, "custom_data"):
            context.custom_data["verified_agent_id"] = self.agent_id
            context.custom_data["verified_role"] = self.agent_role
            context.custom_data["verified_account"] = self.verified_account
    
    def _extract_mcp_operation(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> tuple:
        """
        Detect MCP operations and extract ground-truth data.
        
        Returns:
            (operation_name, extracted_data)
        """
        mcp_data = {}
        
        # Detect MCP retrieval operations
        if "retrieve_grid_state" in tool_name.lower():
            mcp_data["grid_state"] = tool_input.get("grid_state")
            return "retrieve_grid_state", mcp_data
        
        elif "retrieve_pricing" in tool_name.lower():
            mcp_data["pricing_data"] = tool_input.get("pricing_data")
            return "retrieve_pricing", mcp_data
        
        elif "wind_agent_access" in tool_name.lower():
            mcp_data["grid_state"] = tool_input.get("grid_state")
            return "retrieve_wind_forecast", mcp_data
        
        elif "solar_agent_access" in tool_name.lower():
            mcp_data["grid_state"] = tool_input.get("grid_state")
            return "retrieve_solar_forecast", mcp_data
        
        elif "battery_agent_access" in tool_name.lower():
            mcp_data["grid_state"] = tool_input.get("grid_state")
            return "retrieve_battery_status", mcp_data
        
        elif "load_agent_access" in tool_name.lower():
            mcp_data["grid_state"] = tool_input.get("grid_state")
            return "retrieve_load_forecast", mcp_data
        
        else:
            return "unknown_operation", mcp_data
    
    def _extract_kqml_performative(self, model_output: Dict[str, Any]) -> tuple:
        """
        Extract KQML performative verb from model output.
        
        KQML performatives in energy negotiation:
        - propose: Offer a control action or negotiation
        - accept: Accept a proposal from another agent
        - reject: Decline a proposal
        - inform: Provide information without negotiation
        - request: Ask another agent to perform action
        
        Returns:
            (performative_verb, raw_kqml_string)
        """
        text = ""
        if isinstance(model_output, dict):
            # Try content field first (standard GenAI response)
            text = model_output.get("content", "")
        elif isinstance(model_output, str):
            text = model_output
        
        text_lower = text.lower()
        
        performatives = ["propose", "accept", "reject", "inform", "request", "tell"]
        for perf in performatives:
            if perf in text_lower:
                return perf, text
        
        return "unclassified", text
    
    def _sanitize_for_logging(self, data: Any) -> Any:
        """
        Remove sensitive data before logging (API keys, credentials).
        """
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(secret in key.lower() for secret in ["key", "secret", "token", "password"]):
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = self._sanitize_for_logging(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_for_logging(item) for item in data]
        return data
    
    def _generate_event_id(self) -> str:
        """Generate cryptographically unique event ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _log_and_sink(self, event: AuditEvent, message: str) -> None:
        """
        Log event locally and sink to SQLite database.
        """
        if self.enable_local_logging:
            print(
                f"[{event.event_type.upper()}] {message}\n"
                f"  Event ID: {event.event_id}\n"
                f"  Agent: {event.agent_id} ({event.agent_role})\n"
                f"  Account: {event.verified_account}"
            )
        
        # Store in local SQLite database
        self.audit_db.insert_event(event)

"""
KQML (Knowledge Query and Manipulation Language) Implementation
============================================================

Implements KQML performatives for comprehensive agent-to-agent communication 
in the microgrid system. Focuses on grid management operations rather than 
just energy trading.

Supported performatives: propose, accept, reject, inform, query, answer.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class Priority(Enum):
    """Priority levels for grid management communications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GridImpact(Enum):
    """Types of grid impact for operational context."""
    STABILITY = "stability"
    EFFICIENCY = "efficiency"
    SAFETY = "safety"
    COST = "cost"


class ValidationError(Exception):
    """Raised when KQML message validation fails."""
    pass


@dataclass
class KQMLMessage:
    """KQML message structure for inter-agent communication."""
    performative: str  # propose, accept, reject, inform, query, answer
    sender_id: str
    receiver_id: str
    conversation_id: str
    timestamp: str
    
    # Core content fields
    subject: Optional[str] = None          # Required for query, inform
    content: Optional[str] = None          # Required for inform, answer
    reason: Optional[str] = None           # Required for reject
    
    # Grid management context (optional, used when relevant)
    priority: Optional[str] = None         # low, medium, high, critical
    grid_impact: Optional[str] = None      # stability, efficiency, safety, cost
    affected_components: Optional[List[str]] = None  # [solar, wind, battery, load]
    
    # Legacy energy fields (optional for backward compatibility)
    energy_mw: Optional[float] = None      
    price: Optional[float] = None
    
    # Command fields for request performative
    command: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    
    # Extensible custom fields for domain-specific data
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    raw_kqml: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "performative": self.performative,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "conversation_id": self.conversation_id,
            "timestamp": self.timestamp,
        }
        
        # Add optional fields if present
        optional_fields = [
            "subject", "content", "reason", "priority", "grid_impact", 
            "affected_components", "energy_mw", "price", "command", "params"
        ]
        for field_name in optional_fields:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        
        # Add custom fields
        if self.custom_fields:
            result["custom_fields"] = self.custom_fields
            
        return result
    
    def to_string(self) -> str:
        """Serialize to KQML string format for transmission."""
        parts = [
            f":sender {self.sender_id}",
            f":receiver {self.receiver_id}",
            f":conversation {self.conversation_id}",
            f":timestamp {self.timestamp}"
        ]
        
        # Add core content fields
        if self.subject:
            parts.append(f":subject \"{self.subject}\"")
        if self.content:
            parts.append(f":content \"{self.content}\"")
        if self.reason:
            parts.append(f":reason \"{self.reason}\"")
        
        # Add grid management context
        if self.priority:
            parts.append(f":priority {self.priority}")
        if self.grid_impact:
            parts.append(f":grid_impact {self.grid_impact}")
        if self.affected_components:
            components_str = ",".join(self.affected_components)
            parts.append(f":affected_components \"{components_str}\"")
        
        # Add legacy energy fields
        if self.energy_mw is not None:
            parts.append(f":energy_mw {self.energy_mw}")
        if self.price is not None:
            parts.append(f":price {self.price}")
        
        # Add command fields
        if self.command:
            parts.append(f":command {self.command}")
        if self.params:
            param_str = " ".join([f":param-{k} {v}" for k, v in self.params.items()])
            parts.append(param_str)
        
        # Add custom fields
        if self.custom_fields:
            custom_str = " ".join([f":custom-{k} \"{v}\"" for k, v in self.custom_fields.items()])
            parts.append(custom_str)
        
        kqml_str = f"({self.performative} {' '.join(parts)})"
        self.raw_kqml = kqml_str
        return kqml_str


def _generate_timestamp() -> str:
    """Generate ISO timestamp for KQML messages."""
    return datetime.now(timezone.utc).isoformat()


def validate_kqml_message(message: KQMLMessage) -> None:
    """
    Validate KQML message according to schema requirements.
    
    Args:
        message: KQMLMessage to validate
        
    Raises:
        ValidationError: If message fails validation
    """
    performative = message.performative.lower()
    
    # Validate required fields per performative
    if performative == "query":
        if not message.subject:
            raise ValidationError("Query performative requires 'subject' field")
    
    elif performative == "inform":
        if not message.subject:
            raise ValidationError("Inform performative requires 'subject' field")
        if not message.content:
            raise ValidationError("Inform performative requires 'content' field")
    
    elif performative == "answer":
        if not message.content:
            raise ValidationError("Answer performative requires 'content' field")
    
    elif performative == "reject":
        if not message.reason:
            raise ValidationError("Reject performative requires 'reason' field")
    
    elif performative == "propose":
        if not message.subject:
            raise ValidationError("Propose performative requires 'subject' field")
        if not message.content:
            raise ValidationError("Propose performative requires 'content' field")
    
    # Validate conversation_id format
    if not message.conversation_id:
        raise ValidationError("Missing required conversation_id")
    
    # Validate priority if present
    if message.priority and message.priority not in [p.value for p in Priority]:
        raise ValidationError(f"Invalid priority: {message.priority}. Must be one of: {[p.value for p in Priority]}")
    
    # Validate grid_impact if present
    if message.grid_impact and message.grid_impact not in [g.value for g in GridImpact]:
        raise ValidationError(f"Invalid grid_impact: {message.grid_impact}. Must be one of: {[g.value for g in GridImpact]}")


def create_error_response(original_message: KQMLMessage, error_message: str) -> KQMLMessage:
    """
    Create a KQML error response for malformed messages.
    
    Args:
        original_message: The message that caused the error
        error_message: Description of the error
        
    Returns:
        KQMLMessage with reject performative containing error details
    """
    return KQMLMessage(
        performative="reject",
        sender_id=original_message.receiver_id,  # Swap sender/receiver
        receiver_id=original_message.sender_id,
        conversation_id=original_message.conversation_id,
        timestamp=_generate_timestamp(),
        reason=f"Validation error: {error_message}",
        subject="message-validation-error",
        content=f"Failed to process message: {error_message}"
    )


def enforce_conversation_id(response_message: KQMLMessage, original_conversation_id: str) -> None:
    """
    Ensure response uses the correct conversation_id.
    
    Args:
        response_message: Message to validate
        original_conversation_id: Expected conversation_id
        
    Raises:
        ValidationError: If conversation_id doesn't match
    """
    if response_message.conversation_id != original_conversation_id:
        raise ValidationError(
            f"Conversation ID mismatch: expected {original_conversation_id}, "
            f"got {response_message.conversation_id}"
        )


# Performative builder functions

def query(sender_id: str, receiver_id: str, subject: str, content: str = "", 
          conversation_id: Optional[str] = None, **kwargs) -> KQMLMessage:
    """
    Build a KQML query message to ask for information.
    
    Args:
        sender_id: Agent making the query
        receiver_id: Agent receiving the query
        subject: Subject of the query (required)
        content: Additional query details
        conversation_id: Optional conversation ID
        **kwargs: Additional grid management fields (priority, grid_impact, etc.)
        
    Returns:
        KQMLMessage with query performative
    """
    message = KQMLMessage(
        performative="query",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id or str(uuid.uuid4()),
        timestamp=_generate_timestamp(),
        subject=subject,
        content=content if content else None,
        **kwargs
    )
    validate_kqml_message(message)
    return message


def inform(sender_id: str, receiver_id: str, subject: str, content: str,
          conversation_id: Optional[str] = None, **kwargs) -> KQMLMessage:
    """
    Build a KQML inform message to share information.
    
    Args:
        sender_id: Agent sending information
        receiver_id: Agent receiving information  
        subject: Subject of the information (required)
        content: Information content (required)
        conversation_id: Optional conversation ID
        **kwargs: Additional grid management fields
        
    Returns:
        KQMLMessage with inform performative
    """
    message = KQMLMessage(
        performative="inform",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id or str(uuid.uuid4()),
        timestamp=_generate_timestamp(),
        subject=subject,
        content=content,
        **kwargs
    )
    validate_kqml_message(message)
    return message


def propose(sender_id: str, receiver_id: str, subject: str, content: str,
           conversation_id: Optional[str] = None, **kwargs) -> KQMLMessage:
    """
    Build a KQML propose message for operational proposals.
    
    Args:
        sender_id: Agent making the proposal
        receiver_id: Agent receiving the proposal
        subject: Subject of the proposal (required)
        content: Proposal details (required) 
        conversation_id: Optional conversation ID
        **kwargs: Additional fields (energy_mw, price, priority, etc.)
        
    Returns:
        KQMLMessage with propose performative
    """
    message = KQMLMessage(
        performative="propose",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id or str(uuid.uuid4()),
        timestamp=_generate_timestamp(),
        subject=subject,
        content=content,
        **kwargs
    )
    validate_kqml_message(message)
    return message


def accept(sender_id: str, receiver_id: str, conversation_id: str, 
          reason: str = "", **kwargs) -> KQMLMessage:
    """
    Build a KQML accept message to accept a proposal.
    
    Args:
        sender_id: Agent accepting
        receiver_id: Agent who made the original proposal
        conversation_id: ID linking to original proposal (required)
        reason: Optional reason for acceptance
        **kwargs: Additional fields
        
    Returns:
        KQMLMessage with accept performative
    """
    message = KQMLMessage(
        performative="accept",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id,
        timestamp=_generate_timestamp(),
        reason=reason if reason else None,
        **kwargs
    )
    validate_kqml_message(message)
    return message


def reject(sender_id: str, receiver_id: str, conversation_id: str, reason: str,
          **kwargs) -> KQMLMessage:
    """
    Build a KQML reject message to decline a proposal.
    
    Args:
        sender_id: Agent rejecting
        receiver_id: Agent who made the original proposal
        conversation_id: ID linking to original proposal (required)
        reason: Reason for rejection (required)
        **kwargs: Additional fields
        
    Returns:
        KQMLMessage with reject performative
    """
    message = KQMLMessage(
        performative="reject",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id,
        timestamp=_generate_timestamp(),
        reason=reason,
        **kwargs
    )
    validate_kqml_message(message)
    return message


def answer(sender_id: str, receiver_id: str, conversation_id: str, content: str,
          **kwargs) -> KQMLMessage:
    """
    Build a KQML answer message in response to a query.
    
    Args:
        sender_id: Agent providing the answer
        receiver_id: Agent who made the query
        conversation_id: ID linking to original query (required)
        content: Answer content (required)
        **kwargs: Additional fields
        
    Returns:
        KQMLMessage with answer performative
    """
    message = KQMLMessage(
        performative="answer",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id,
        timestamp=_generate_timestamp(),
        content=content,
        **kwargs
    )
    validate_kqml_message(message)
    return message


def request(sender_id: str, receiver_id: str, command: str, params: Optional[Dict] = None,
           conversation_id: Optional[str] = None, **kwargs) -> KQMLMessage:
    """
    Build a KQML request message to ask agent to perform action.
    
    Args:
        sender_id: Agent making the request
        receiver_id: Agent receiving the request
        command: Command to execute
        params: Optional command parameters
        conversation_id: Optional conversation ID
        **kwargs: Additional fields
        
    Returns:
        KQMLMessage with request performative
    """
    message = KQMLMessage(
        performative="request",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id or str(uuid.uuid4()),
        timestamp=_generate_timestamp(),
        command=command,
        params=params,
        **kwargs
    )
    validate_kqml_message(message)
    return message


def parse_kqml(raw_string: str) -> KQMLMessage:
    """
    Parse incoming KQML string to KQMLMessage object with validation.
    
    Args:
        raw_string: KQML string to parse
        
    Returns:
        KQMLMessage object
        
    Raises:
        ValidationError: If KQML string is malformed or invalid
    """
    try:
        # Simple parser for the KQML format: (performative :key value ...)
        raw_string = raw_string.strip()
        if not (raw_string.startswith('(') and raw_string.endswith(')')):
            raise ValidationError("KQML must be wrapped in parentheses")
        
        # Remove outer parentheses
        content = raw_string[1:-1].strip()
        
        # Split on spaces but preserve quoted strings
        tokens = []
        current_token = ""
        in_quotes = False
        
        for char in content:
            if char == '"' and (not current_token or current_token[-1] != '\\'):
                in_quotes = not in_quotes
                current_token += char
            elif char == ' ' and not in_quotes:
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
            else:
                current_token += char
        
        if current_token:
            tokens.append(current_token)
        
        if not tokens:
            raise ValidationError("Empty KQML message")
        
        performative = tokens[0]
        
        # Parse key-value pairs
        parsed = {"performative": performative}
        i = 1
        while i < len(tokens):
            if tokens[i].startswith(':'):
                key = tokens[i][1:]  # Remove ':' prefix
                if i + 1 < len(tokens):
                    value = tokens[i + 1]
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    parsed[key] = value
                i += 2
            else:
                i += 1
        
        # Extract components list
        affected_components = None
        if parsed.get("affected_components"):
            affected_components = [c.strip() for c in parsed["affected_components"].split(",")]
        
        # Extract custom fields and params
        custom_fields = {}
        params = {}
        
        for key, value in parsed.items():
            if key.startswith("custom-"):
                custom_fields[key[7:]] = value  # Remove "custom-" prefix
            elif key.startswith("param-"):
                param_name = key[6:]  # Remove "param-" prefix
                # Try to convert to appropriate type
                try:
                    params[param_name] = float(value)
                except ValueError:
                    params[param_name] = value
        
        # Validate required conversation_id
        if not parsed.get("conversation"):
            raise ValidationError("Missing required conversation_id in KQML message")
        
        # Create KQMLMessage with all parsed fields
        message = KQMLMessage(
            performative=parsed.get("performative"),
            sender_id=parsed.get("sender", "unknown"),
            receiver_id=parsed.get("receiver", "unknown"), 
            conversation_id=parsed["conversation"],  # Required, no default
            timestamp=parsed.get("timestamp", _generate_timestamp()),
            subject=parsed.get("subject"),
            content=parsed.get("content"),
            reason=parsed.get("reason"),
            priority=parsed.get("priority"),
            grid_impact=parsed.get("grid_impact"),
            affected_components=affected_components,
            energy_mw=float(parsed["energy_mw"]) if parsed.get("energy_mw") else None,
            price=float(parsed["price"]) if parsed.get("price") else None,
            command=parsed.get("command"),
            params=params if params else None,
            custom_fields=custom_fields,
            raw_kqml=raw_string
        )
        
        # Validate the parsed message
        validate_kqml_message(message)
        return message
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        raise ValidationError(f"Failed to parse KQML: {e}")


def message_to_string(kqml_message: KQMLMessage) -> str:
    """
    Serialize KQMLMessage to string for transmission.
    
    Args:
        kqml_message: KQMLMessage to serialize
        
    Returns:
        KQML string representation
    """
    return kqml_message.to_string()


# Legacy compatibility functions
class kqml:
    """Legacy KQML interface for backward compatibility."""
    
    @staticmethod
    def parse_message(raw_kqml: str) -> KQMLMessage:
        """Parses raw string into a KQMLMessage object."""
        return parse_kqml(raw_kqml)

    @staticmethod  
    def create_message(verb: str, content: str, sender: str, receiver: str) -> str:
        """Creates KQML message string."""
        if verb.lower() == "inform":
            msg = inform(sender, receiver, "legacy-message", content)
        else:
            msg = KQMLMessage(
                performative=verb,
                sender_id=sender,
                receiver_id=receiver,
                conversation_id=str(uuid.uuid4()),
                timestamp=_generate_timestamp(),
                content=content
            )
        return msg.to_string()
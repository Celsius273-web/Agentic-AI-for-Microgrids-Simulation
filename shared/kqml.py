"""
KQML (Knowledge Query and Manipulation Language) Implementation
============================================================

Implements KQML performatives for agent-to-agent communication in the microgrid system.
Supports energy negotiation performatives: propose, accept, reject, inform, request, answer.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class KQMLMessage:
    """KQML message structure for inter-agent communication."""
    performative: str  # propose, accept, reject, inform, request, answer
    sender_id: str
    receiver_id: str
    conversation_id: str
    timestamp: str
    
    # Optional fields for energy negotiations
    energy_mwh: Optional[float] = None
    price_per_mwh: Optional[float] = None
    reason: Optional[str] = None
    content: Optional[str] = None
    command: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    
    # Raw KQML for audit trail
    raw_kqml: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "performative": self.performative,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "conversation_id": self.conversation_id,
            "timestamp": self.timestamp,
            "energy_mwh": self.energy_mwh,
            "price_per_mwh": self.price_per_mwh,
            "reason": self.reason,
            "content": self.content,
            "command": self.command,
            "params": self.params
        }
    
    def to_string(self) -> str:
        """Serialize to KQML string format for transmission."""
        parts = [
            f":sender {self.sender_id}",
            f":receiver {self.receiver_id}",
            f":conversation {self.conversation_id}",
            f":timestamp {self.timestamp}"
        ]
        
        if self.energy_mwh is not None:
            parts.append(f":energy {self.energy_mwh}")
        if self.price_per_mwh is not None:
            parts.append(f":price {self.price_per_mwh}")
        if self.reason:
            parts.append(f":reason \"{self.reason}\"")
        if self.content:
            parts.append(f":content \"{self.content}\"")
        if self.command:
            parts.append(f":command {self.command}")
        if self.params:
            # Simple param serialization - could be enhanced
            param_str = " ".join([f":param-{k} {v}" for k, v in self.params.items()])
            parts.append(param_str)
        
        kqml_str = f"({self.performative} {' '.join(parts)})"
        self.raw_kqml = kqml_str
        return kqml_str


def _generate_timestamp() -> str:
    """Generate ISO timestamp for KQML messages."""
    return datetime.now(timezone.utc).isoformat()


def propose(sender_id: str, receiver_id: str, energy_mwh: float, price_per_mwh: float, 
           conversation_id: Optional[str] = None) -> KQMLMessage:
    """
    Build a KQML propose message for energy negotiation.
    
    Args:
        sender_id: Agent making the proposal
        receiver_id: Agent receiving the proposal
        energy_mwh: Energy amount in MWh
        price_per_mwh: Price in $/MWh
        conversation_id: Optional conversation ID (auto-generated if not provided)
        
    Returns:
        KQMLMessage with propose performative
    """
    return KQMLMessage(
        performative="propose",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id or str(uuid.uuid4()),
        timestamp=_generate_timestamp(),
        energy_mwh=energy_mwh,
        price_per_mwh=price_per_mwh
    )


def accept(sender_id: str, receiver_id: str, conversation_id: str, 
          reason: str = "") -> KQMLMessage:
    """
    Build a KQML accept message to accept a proposal.
    
    Args:
        sender_id: Agent accepting the proposal
        receiver_id: Agent who made the original proposal
        conversation_id: ID linking to original proposal
        reason: Optional reason for acceptance
        
    Returns:
        KQMLMessage with accept performative
    """
    return KQMLMessage(
        performative="accept",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id,
        timestamp=_generate_timestamp(),
        reason=reason if reason else None
    )


def reject(sender_id: str, receiver_id: str, conversation_id: str, reason: str) -> KQMLMessage:
    """
    Build a KQML reject message to decline a proposal.
    
    Args:
        sender_id: Agent rejecting the proposal
        receiver_id: Agent who made the original proposal
        conversation_id: ID linking to original proposal
        reason: Required reason for rejection
        
    Returns:
        KQMLMessage with reject performative
    """
    return KQMLMessage(
        performative="reject",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id,
        timestamp=_generate_timestamp(),
        reason=reason
    )


def inform(sender_id: str, receiver_id: str, content: str, 
          conversation_id: Optional[str] = None) -> KQMLMessage:
    """
    Build a KQML inform message to broadcast information.
    
    Args:
        sender_id: Agent sending information
        receiver_id: Agent receiving information
        content: Information content
        conversation_id: Optional conversation ID
        
    Returns:
        KQMLMessage with inform performative
    """
    return KQMLMessage(
        performative="inform",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id or str(uuid.uuid4()),
        timestamp=_generate_timestamp(),
        content=content
    )


def request(sender_id: str, receiver_id: str, command: str, params: Optional[Dict] = None,
           conversation_id: Optional[str] = None) -> KQMLMessage:
    """
    Build a KQML request message to ask agent to perform action.
    
    Args:
        sender_id: Agent making the request
        receiver_id: Agent receiving the request
        command: Command to execute (e.g., "get_output", "set_curtailment")
        params: Optional command parameters
        conversation_id: Optional conversation ID
        
    Returns:
        KQMLMessage with request performative
    """
    return KQMLMessage(
        performative="request",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id or str(uuid.uuid4()),
        timestamp=_generate_timestamp(),
        command=command,
        params=params
    )


def answer(sender_id: str, receiver_id: str, conversation_id: str, content: str) -> KQMLMessage:
    """
    Build a KQML answer message in response to a request/query.
    
    Args:
        sender_id: Agent providing the answer
        receiver_id: Agent who made the request
        conversation_id: ID linking to original request
        content: Answer content
        
    Returns:
        KQMLMessage with answer performative
    """
    return KQMLMessage(
        performative="answer",
        sender_id=sender_id,
        receiver_id=receiver_id,
        conversation_id=conversation_id,
        timestamp=_generate_timestamp(),
        content=content
    )


def parse_kqml(raw_string: str) -> KQMLMessage:
    """
    Parse incoming KQML string to KQMLMessage object.
    
    Args:
        raw_string: KQML string to parse
        
    Returns:
        KQMLMessage object
        
    Raises:
        ValueError: If KQML string is malformed
    """
    try:
        # Simple parser for the KQML format: (performative :key value ...)
        raw_string = raw_string.strip()
        if not (raw_string.startswith('(') and raw_string.endswith(')')):
            raise ValueError("KQML must be wrapped in parentheses")
        
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
            raise ValueError("Empty KQML message")
        
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
        
        # Convert parsed data to KQMLMessage
        return KQMLMessage(
            performative=parsed.get("performative"),
            sender_id=parsed.get("sender", "unknown"),
            receiver_id=parsed.get("receiver", "unknown"),
            conversation_id=parsed.get("conversation", str(uuid.uuid4())),
            timestamp=parsed.get("timestamp", _generate_timestamp()),
            energy_mwh=float(parsed["energy"]) if parsed.get("energy") else None,
            price_per_mwh=float(parsed["price"]) if parsed.get("price") else None,
            reason=parsed.get("reason"),
            content=parsed.get("content"),
            command=parsed.get("command"),
            params=_parse_params(parsed),  # Extract param-* fields
            raw_kqml=raw_string
        )
        
    except Exception as e:
        raise ValueError(f"Failed to parse KQML: {e}")


def _parse_params(parsed_data: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Extract parameters from parsed KQML data."""
    params = {}
    for key, value in parsed_data.items():
        if key.startswith("param-"):
            param_name = key[6:]  # Remove "param-" prefix
            # Try to convert to appropriate type
            try:
                # Try float first
                params[param_name] = float(value)
            except ValueError:
                # Keep as string
                params[param_name] = value
    
    return params if params else None


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
        msg = KQMLMessage(
            performative=verb,
            sender_id=sender,
            receiver_id=receiver,
            conversation_id=str(uuid.uuid4()),
            timestamp=_generate_timestamp(),
            content=content
        )
        return msg.to_string()
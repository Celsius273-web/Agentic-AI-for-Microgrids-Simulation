"""
Local SQLite Audit Database
============================

Stores all lifecycle events locally in audit_trail.db
No cloud dependencies - fully local simulation.
"""

import sqlite3
import json
import logging
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import asdict

_audit_db_registry: Dict[str, "LocalAuditDB"] = {}
_registry_lock = threading.Lock()


class LocalAuditDB:
    """SQLite-backed audit trail for local simulation."""
    
    def __init__(self, db_path: str = "audit_trail.db"):
        """
        Initialize local audit database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.logger = logging.getLogger(__name__)
        self._write_lock = threading.Lock()

        self._init_schema()
        print(f"✓ Local audit database initialized: {db_path}")
    
    def _init_schema(self):
        """Create audit tables if they don't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                event_type TEXT NOT NULL,
                hook_name TEXT NOT NULL,
                verified_account TEXT NOT NULL,
                auth_timestamp TEXT NOT NULL,
                oidc_claims TEXT,  -- Full OIDC token claims as JSON
                tool_name TEXT,
                tool_inputs TEXT,
                tool_outputs TEXT,
                tool_error TEXT,
                tool_execution_ms REAL,
                mcp_operation TEXT,
                kqml_performative TEXT,
                kqml_raw TEXT,
                model_name TEXT,
                model_input_tokens INTEGER,
                model_output_tokens INTEGER,
                grid_state_snapshot TEXT,
                pricing_data_snapshot TEXT,
                request_id TEXT,
                parent_event_id TEXT,
                extra_context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add oidc_claims column if it doesn't exist (for existing databases)
        try:
            self.conn.execute("ALTER TABLE audit_events ADD COLUMN oidc_claims TEXT")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS kqml_timeline (
                performative_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                sender_agent_id TEXT NOT NULL,
                receiver_agent_id TEXT NOT NULL,
                performative_verb TEXT NOT NULL,
                raw_kqml TEXT NOT NULL,
                
                -- Core content fields
                subject TEXT,
                content TEXT,
                reason TEXT,
                
                -- Grid management context
                priority TEXT,
                grid_impact TEXT,
                affected_components TEXT,  -- JSON array as string
                
                -- Legacy energy fields
                energy_mw REAL,
                price REAL,
                
                -- Command fields
                command TEXT,
                params TEXT,  -- JSON object as string
                
                -- Custom fields as JSON
                custom_fields TEXT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add new columns to existing kqml_timeline table if they don't exist
        new_columns = [
            ("conversation_id", "TEXT"),
            ("receiver_agent_id", "TEXT"),
            ("subject", "TEXT"),
            ("content", "TEXT"),
            ("reason", "TEXT"),
            ("priority", "TEXT"),
            ("grid_impact", "TEXT"),
            ("affected_components", "TEXT"),
            ("energy_mw", "REAL"),
            ("price", "REAL"),
            ("command", "TEXT"),
            ("params", "TEXT"),
            ("custom_fields", "TEXT")
        ]
        
        for column_name, column_type in new_columns:
            try:
                self.conn.execute(f"ALTER TABLE kqml_timeline ADD COLUMN {column_name} {column_type}")
            except sqlite3.OperationalError:
                # Column already exists
                pass
        
        # Rename old columns if they exist
        try:
            # Check if old column exists
            cursor = self.conn.execute("PRAGMA table_info(kqml_timeline)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if "performer_verb" in columns and "performative_verb" not in columns:
                self.conn.execute("ALTER TABLE kqml_timeline RENAME COLUMN performer_verb TO performative_verb")
            if "energy_mwh" in columns and "energy_mw" not in columns:
                self.conn.execute("ALTER TABLE kqml_timeline RENAME COLUMN energy_mwh TO energy_mw")
            if "price_per_mwh" in columns and "price" not in columns:
                self.conn.execute("ALTER TABLE kqml_timeline RENAME COLUMN price_per_mwh TO price")
                
        except sqlite3.OperationalError:
            # Columns don't exist or already renamed
            pass
        
        # Create indexes for fast queries
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_id ON audit_events(agent_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_verified_account ON audit_events(verified_account)")
        
        # Enhanced KQML timeline indexes
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_kqml_timestamp ON kqml_timeline(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_kqml_conversation ON kqml_timeline(conversation_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_kqml_sender ON kqml_timeline(sender_agent_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_kqml_receiver ON kqml_timeline(receiver_agent_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_kqml_performative ON kqml_timeline(performative_verb)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_kqml_subject ON kqml_timeline(subject)")
        
        self.conn.commit()
    
    def insert_event(self, event: Any) -> bool:
        """
        Insert an audit event into the database.
        
        Args:
            event: AuditEvent dataclass instance
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._write_lock:
                self.conn.execute("""
                INSERT INTO audit_events VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                event.event_id,
                event.timestamp,
                event.agent_id,
                event.agent_role,
                event.event_type,
                event.hook_name,
                event.verified_account,
                event.auth_timestamp,
                json.dumps(event.oidc_claims) if event.oidc_claims else None,
                event.tool_name,
                json.dumps(event.tool_inputs) if event.tool_inputs else None,
                json.dumps(event.tool_outputs) if event.tool_outputs else None,
                event.tool_error,
                event.tool_execution_ms,
                event.mcp_operation,
                event.kqml_performative,
                event.kqml_raw,
                event.model_name,
                event.model_input_tokens,
                event.model_output_tokens,
                json.dumps(event.grid_state_snapshot) if event.grid_state_snapshot else None,
                json.dumps(event.pricing_data_snapshot) if event.pricing_data_snapshot else None,
                event.request_id,
                event.parent_event_id,
                json.dumps(event.extra_context) if event.extra_context else None,
                datetime.now(timezone.utc).isoformat(),
            ))
                self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error inserting event: {e}")
            return False
    
    def insert_kqml_performative(
        self,
        performative_id: str,
        timestamp: str,
        sender_agent_id: str,
        performative_verb: str,
        raw_kqml: str,
        energy_mwh: Optional[float] = None,
        price_per_mwh: Optional[float] = None,
    ) -> bool:
        """
        Insert KQML performative for energy negotiation timeline.
        
        Args:
            performative_id: Unique ID for this performative
            timestamp: ISO timestamp
            sender_agent_id: Agent that issued performative
            performative_verb: propose, accept, reject, inform, request
            raw_kqml: Raw KQML message
            energy_mwh: Megawatts (optional)
            price_per_mwh: Price (optional)
            
        Returns:
            True if successful
        """
        try:
            with self._write_lock:
                self.conn.execute("""
                INSERT INTO kqml_timeline (
                    performative_id, timestamp, sender_agent_id, performative_verb, 
                    raw_kqml, energy_mw, price, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                performative_id,
                timestamp,
                sender_agent_id,
                performative_verb,
                raw_kqml,
                energy_mwh,  # Map to energy_mw
                price_per_mwh,  # Map to price
                datetime.now(timezone.utc).isoformat(),
            ))
                self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error inserting KQML performative: {e}")
            return False
    
    def insert_kqml_performative_enhanced(
        self,
        performative_id: str,
        timestamp: str,
        conversation_id: str,
        sender_agent_id: str,
        receiver_agent_id: str,
        performative_verb: str,
        raw_kqml: str,
        subject: Optional[str] = None,
        content: Optional[str] = None,
        reason: Optional[str] = None,
        priority: Optional[str] = None,
        grid_impact: Optional[str] = None,
        affected_components: Optional[List[str]] = None,
        energy_mw: Optional[float] = None,
        price: Optional[float] = None,
        command: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Insert enhanced KQML performative for comprehensive grid management timeline.
        
        Args:
            performative_id: Unique ID for this performative
            timestamp: ISO timestamp
            conversation_id: Conversation ID linking related messages
            sender_agent_id: Agent that issued performative
            receiver_agent_id: Agent receiving the performative
            performative_verb: propose, accept, reject, inform, query, answer, request
            raw_kqml: Raw KQML message
            subject: Subject of the message
            content: Message content
            reason: Reason (for reject messages)
            priority: Priority level (low, medium, high, critical)
            grid_impact: Grid impact type (stability, efficiency, safety, cost)
            affected_components: List of affected components
            energy_mw: Energy in MW (legacy)
            price: Price (legacy)
            command: Command name (for request messages)
            params: Command parameters
            custom_fields: Custom fields dictionary
            
        Returns:
            True if successful
        """
        try:
            affected_components_json = json.dumps(affected_components) if affected_components else None
            params_json = json.dumps(params) if params else None
            custom_fields_json = json.dumps(custom_fields) if custom_fields else None

            with self._write_lock:
                self.conn.execute("""
                INSERT INTO kqml_timeline (
                    performative_id, timestamp, conversation_id, sender_agent_id, 
                    receiver_agent_id, performative_verb, raw_kqml, subject, content, 
                    reason, priority, grid_impact, affected_components, energy_mw, 
                    price, command, params, custom_fields, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                performative_id,
                timestamp,
                conversation_id,
                sender_agent_id,
                receiver_agent_id,
                performative_verb,
                raw_kqml,
                subject,
                content,
                reason,
                priority,
                grid_impact,
                affected_components_json,
                energy_mw,
                price,
                command,
                params_json,
                custom_fields_json,
                datetime.now(timezone.utc).isoformat()
            ))
                self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to insert enhanced KQML performative: {e}")
            return False

    def insert_kqml_from_message(self, kqml_message) -> bool:
        """
        Insert KQML performative from a KQMLMessage object.
        
        Args:
            kqml_message: KQMLMessage instance
            
        Returns:
            True if successful
        """
        import uuid
        performative_id = str(uuid.uuid4())
        
        return self.insert_kqml_performative_enhanced(
            performative_id=performative_id,
            timestamp=kqml_message.timestamp,
            conversation_id=kqml_message.conversation_id,
            sender_agent_id=kqml_message.sender_id,
            receiver_agent_id=kqml_message.receiver_id,
            performative_verb=kqml_message.performative,
            raw_kqml=kqml_message.raw_kqml or kqml_message.to_string(),
            subject=kqml_message.subject,
            content=kqml_message.content,
            reason=kqml_message.reason,
            priority=kqml_message.priority,
            grid_impact=kqml_message.grid_impact,
            affected_components=kqml_message.affected_components,
            energy_mw=kqml_message.energy_mw,
            price=kqml_message.price,
            command=kqml_message.command,
            params=kqml_message.params,
            custom_fields=kqml_message.custom_fields,
        )
    
    def query_events(
        self,
        agent_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """
        Query audit events.
        
        Args:
            agent_id: Filter by agent
            event_type: Filter by event type
            limit: Max results
            
        Returns:
            List of event dictionaries
        """
        query = "SELECT * FROM audit_events WHERE 1=1"
        params = []
        
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def query_kqml_timeline(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> list:
        """
        Query KQML performative timeline.
        
        Args:
            start_time: ISO timestamp start
            end_time: ISO timestamp end
            agent_id: Filter by sender agent
            
        Returns:
            List of performative dictionaries
        """
        query = "SELECT * FROM kqml_timeline WHERE 1=1"
        params = []
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        if agent_id:
            query += " AND sender_agent_id = ?"
            params.append(agent_id)
        
        query += " ORDER BY timestamp ASC"
        
        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_agent_summary(self) -> Dict[str, Any]:
        """Get summary statistics by agent."""
        cursor = self.conn.execute("""
            SELECT 
                agent_id,
                COUNT(*) as total_events,
                COUNT(DISTINCT request_id) as unique_requests,
                MIN(timestamp) as first_event,
                MAX(timestamp) as latest_event
            FROM audit_events
            WHERE verified_account != 'unauthenticated'
            GROUP BY agent_id
            ORDER BY latest_event DESC
        """)
        
        rows = cursor.fetchall()
        return {dict(row)['agent_id']: dict(row) for row in rows}
    
    def get_kqml_negotiations(self) -> list:
        """Get all energy negotiations with chronological order."""
        cursor = self.conn.execute("""
            SELECT * FROM kqml_timeline
            ORDER BY timestamp ASC
        """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def __del__(self):
        """Ensure connection is closed on cleanup."""
        self.close()


def get_shared_audit_db(db_path: str = "audit_trail.db") -> LocalAuditDB:
    """Return a process-wide LocalAuditDB instance per db_path (safe for concurrent writers)."""
    resolved = str(Path(db_path).resolve())
    with _registry_lock:
        if resolved not in _audit_db_registry:
            _audit_db_registry[resolved] = LocalAuditDB(resolved)
        return _audit_db_registry[resolved]

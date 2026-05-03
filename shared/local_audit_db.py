"""
Local SQLite Audit Database
============================

Stores all lifecycle events locally in audit_trail.db
No cloud dependencies - fully local simulation.
"""

import sqlite3
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import asdict


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
                sender_agent_id TEXT NOT NULL,
                performer_verb TEXT NOT NULL,
                raw_kqml TEXT NOT NULL,
                energy_mwh REAL,
                price_per_mwh REAL,
                response_performative_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for fast queries
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_id ON audit_events(agent_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_verified_account ON audit_events(verified_account)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_kqml_perfs_time ON kqml_timeline(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_kqml_sender ON kqml_timeline(sender_agent_id)")
        
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
                datetime.utcnow().isoformat(),
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
            self.conn.execute("""
                INSERT INTO kqml_timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                performative_id,
                timestamp,
                sender_agent_id,
                performative_verb,
                raw_kqml,
                energy_mwh,
                price_per_mwh,
                None,  # response_performative_id (filled later)
                datetime.utcnow().isoformat(),
            ))
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error inserting KQML performative: {e}")
            return False
    
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

# Local-Only Instrumentation Setup

## Overview

Global lifecycle hook instrumentation with local SQLite database backend. No cloud dependencies.

**Captures:**
- ✅ `on_agent_start`: Agent initialization with verified identity
- ✅ `on_tool_start`: MCP ground truth inputs (grid state, pricing)
- ✅ `on_tool_end`: Tool outputs and execution time
- ✅ `on_model_end`: KQML performatives (propose, accept, reject, inform)

All events stored in `audit_trail.db` (queryable with SQL).

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export AGENT_ID=microgrid-agent
export AGENT_ROLE=control
export AUDIT_DB_PATH=audit_trail.db
export ENABLE_LOCAL_INSTRUMENTATION=true
export VERIFIED_ACCOUNT=microgrid-agent@microgrid.local
```

### 3. Run Agent
```bash
python microgrid_agent/microgrid_agent.py
```

**Output:**
```
======================================================================
REGISTERING LOCAL INSTRUMENTATION PLUGIN
======================================================================
✓ Agent ID: microgrid-agent
✓ Verified Account: microgrid-agent@microgrid.local
✓ Audit DB: audit_trail.db

Capturing lifecycle hooks:
  - on_agent_start: Agent initialization
  - on_tool_start: MCP ground truth inputs
  - on_tool_end: Tool outputs and side effects
  - on_model_end: KQML performatives
======================================================================

✓ MicrogridAgent runner started with lifecycle hook interception
  All events stored in: audit_trail.db
```

---

## Querying the Audit Trail

### Connect to Database
```bash
sqlite3 audit_trail.db
```

### Query All Events
```sql
SELECT timestamp, agent_id, event_type, tool_name, kqml_performative
FROM audit_events
ORDER BY timestamp DESC
LIMIT 20;
```

### Query by Agent
```sql
SELECT timestamp, event_type, hook_name, tool_name, verified_account
FROM audit_events
WHERE agent_id = 'solar-agent'
ORDER BY timestamp DESC;
```

### Query Tool Invocations (MCP Ground Truth)
```sql
SELECT 
  timestamp,
  tool_name,
  mcp_operation,
  json_extract(grid_state_snapshot, '$') as grid_state,
  json_extract(pricing_data_snapshot, '$') as pricing
FROM audit_events
WHERE event_type = 'tool_invocation'
ORDER BY timestamp DESC
LIMIT 10;
```

### Query KQML Performatives (Energy Negotiation)
```sql
SELECT 
  timestamp,
  sender_agent_id,
  performative_verb,
  energy_mwh,
  price_per_mwh
FROM kqml_timeline
ORDER BY timestamp ASC;
```

### Get Agent Summary
```sql
SELECT 
  agent_id,
  COUNT(*) as total_events,
  MIN(timestamp) as first_event,
  MAX(timestamp) as latest_event
FROM audit_events
WHERE verified_account != 'unauthenticated'
GROUP BY agent_id;
```

### Find Errors
```sql
SELECT timestamp, agent_id, tool_name, tool_error
FROM audit_events
WHERE tool_error IS NOT NULL
ORDER BY timestamp DESC;
```

---

## Integration Pattern for All Agents

Copy this pattern to other agent files (solar_agent.py, wind_agent.py, etc.):

### Imports
```python
from shared.config import (
    AGENT_ID, AGENT_ROLE, AUDIT_DB_PATH, 
    ENABLE_LOCAL_INSTRUMENTATION, VERIFIED_ACCOUNT
)
from shared.instrumentation_plugin import GlobalInstrumentationPlugin
```

### Runner Setup
```python
if __name__ == "__main__":
    plugins = [LoggingPlugin()]
    
    if ENABLE_LOCAL_INSTRUMENTATION:
        plugin = GlobalInstrumentationPlugin(
            agent_id=AGENT_ID or "solar-agent",
            agent_role=AGENT_ROLE or "solar",
            verified_account=VERIFIED_ACCOUNT,
            db_path=AUDIT_DB_PATH,
        )
        plugins.append(plugin)
    
    runner = InMemoryRunner(agent=solar_agent, plugins=plugins)
```

---

## Database Schema

### audit_events Table
```
event_id (TEXT PRIMARY KEY)      - Unique event UUID
timestamp (TEXT)                 - ISO 8601 timestamp
agent_id (TEXT)                  - Agent identifier
agent_role (TEXT)                - Agent role (control, solar, wind, etc.)
event_type (TEXT)                - initialization, tool_invocation, tool_completion, model_inference
hook_name (TEXT)                 - on_agent_start, on_tool_start, on_tool_end, on_model_end
verified_account (TEXT)          - Verified service account (signed)
tool_name (TEXT)                 - Name of tool invoked
tool_inputs (TEXT-JSON)          - Ground truth input parameters
tool_outputs (TEXT-JSON)         - Tool output results
tool_error (TEXT)                - Error message if failed
mcp_operation (TEXT)             - Detected MCP operation
kqml_performative (TEXT)         - KQML verb (propose, accept, reject, inform)
kqml_raw (TEXT)                  - Raw KQML message
grid_state_snapshot (TEXT-JSON)  - Complete grid state at decision time
pricing_data_snapshot (TEXT-JSON)- Pricing data at decision time
created_at (TIMESTAMP)           - Record creation timestamp
```

### kqml_timeline Table
```
performative_id (TEXT PRIMARY KEY) - Unique ID for performative
timestamp (TEXT)                   - ISO 8601 timestamp
sender_agent_id (TEXT)             - Agent issuing performative
performative_verb (TEXT)           - propose, accept, reject, inform, request
raw_kqml (TEXT)                    - Raw KQML message
energy_mwh (REAL)                  - Megawatts offered/accepted
price_per_mwh (REAL)               - Price per MWh
response_performative_id (TEXT)    - ID of response performative (if any)
created_at (TIMESTAMP)             - Record creation timestamp
```

---

## Example Queries

### Non-Repudiable Energy Negotiation Timeline
```sql
SELECT 
  timestamp,
  sender_agent_id,
  performative_verb,
  'Energy:' || energy_mwh || 'MWh @ $' || price_per_mwh || '/MWh' as proposal,
  response_performative_id
FROM kqml_timeline
WHERE timestamp BETWEEN '2025-04-07 10:00:00' AND '2025-04-07 15:00:00'
ORDER BY timestamp ASC;
```

### Trace Decision Path (with ground truth)
```sql
SELECT 
  a.timestamp,
  a.agent_id,
  a.event_type,
  a.tool_name,
  a.kqml_performative,
  json_extract(a.grid_state_snapshot, '$.solar_output') as solar_mw,
  json_extract(a.grid_state_snapshot, '$.battery_soc') as battery_pct
FROM audit_events a
WHERE a.agent_id = 'battery-agent'
  AND a.event_type IN ('tool_invocation', 'model_inference')
  AND a.timestamp > CURRENT_TIMESTAMP - INTERVAL '1 hour'
ORDER BY a.timestamp DESC;
```

### Model Token Cost Analysis
```sql
SELECT 
  agent_id,
  DATE(timestamp) as date,
  COUNT(*) as inferences,
  SUM(model_input_tokens) as total_input,
  SUM(model_output_tokens) as total_output,
  SUM(model_input_tokens + model_output_tokens) as total_tokens
FROM audit_events
WHERE event_type = 'model_inference'
GROUP BY agent_id, date
ORDER BY date DESC, total_tokens DESC;
```

---

## Disabling Instrumentation

Set environment variable to disable:
```bash
export ENABLE_LOCAL_INSTRUMENTATION=false
```

Agent will run without recording to database.

---

## Troubleshooting

### Database Locked Error
```
sqlite3.OperationalError: database is locked
```
Close all other connections to `audit_trail.db` and retry.

### No Events in Database
Check:
1. `ENABLE_LOCAL_INSTRUMENTATION=true` is set
2. Agent actually runs tools that trigger hooks
3. Database file exists and is writable

### Restore Database
To start fresh:
```bash
rm audit_trail.db
python microgrid_agent/microgrid_agent.py
```

---

## Files Modified

| File | Change |
|------|--------|
| `shared/local_audit_db.py` | **NEW**: SQLite backend with schema & query methods |
| `shared/instrumentation_plugin.py` | **NEW**: Google ADK BasePlugin with lifecycle hooks |
| `shared/config.py` | Added `AUDIT_DB_PATH`, `ENABLE_LOCAL_INSTRUMENTATION` |
| `requirements.txt` | Removed `google-cloud-*` packages |
| `microgrid_agent/microgrid_agent.py` | Updated runner to register plugin |

---

## Architecture

```
Agent Execution
    ↓
Google ADK Lifecycle Hooks
    ↓
GlobalInstrumentationPlugin
    ├─ on_agent_start
    ├─ on_tool_start → Extract MCP ground truth
    ├─ on_tool_end
    └─ on_model_end → Extract KQML performatives
    ↓
LocalAuditDB (SQLite)
    ├─ audit_events table
    ├─ kqml_timeline table
    └─ Indexes for fast queries
    ↓
audit_trail.db (queryable)
```

---

**Everything stays local. No internet required. Full audit trail in database.**

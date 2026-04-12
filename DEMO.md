# DEMO: Local Instrumentation System

## 🚀 How to Run

### Step 1: Terminal 1 - Start the Agent
```bash
cd /Users/school/Documents/distributed-agent\ system

export AGENT_ID=microgrid-agent
export AGENT_ROLE=control
export AUDIT_DB_PATH=audit_trail.db
export ENABLE_LOCAL_INSTRUMENTATION=true
export VERIFIED_ACCOUNT=microgrid-agent@microgrid.local

python3 microgrid_agent/microgrid_agent.py
```

**Expected Output:**
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

### Step 2: Terminal 2 - Query the Database

```bash
cd /Users/school/Documents/distributed-agent\ system
sqlite3 audit_trail.db
```

#### Show All Lifecycle Events
```sql
.mode column
.headers on

SELECT 
  timestamp,
  agent_id,
  event_type,
  hook_name,
  tool_name,
  verified_account
FROM audit_events
ORDER BY timestamp DESC
LIMIT 10;
```

**Output:**
```
timestamp                  agent_id        event_type    hook_name        tool_name             verified_account
2025-04-07T16:05:32.123Z   microgrid-agent initialization on_agent_start  (null)                microgrid-agent@microgrid.local
2025-04-07T16:05:33.456Z   microgrid-agent tool_invocation on_tool_start  retrieve_grid_state   microgrid-agent@microgrid.local
2025-04-07T16:05:33.789Z   microgrid-agent tool_completion on_tool_end    retrieve_grid_state   microgrid-agent@microgrid.local
2025-04-07T16:05:34.012Z   microgrid-agent model_inference on_model_end   (null)                microgrid-agent@microgrid.local
```

#### Show Ground Truth (MCP Inputs Before Decision)
```sql
SELECT 
  timestamp,
  tool_name,
  mcp_operation,
  json_extract(grid_state_snapshot, '$.solar_output_mw') as solar_mw,
  json_extract(grid_state_snapshot, '$.battery_soc_pct') as battery_pct,
  json_extract(pricing_data_snapshot, '$.market_price_per_mwh') as price
FROM audit_events
WHERE event_type = 'tool_invocation'
ORDER BY timestamp DESC
LIMIT 5;
```

#### Show KQML Performatives (Energy Negotiation)
```sql
SELECT 
  timestamp,
  sender_agent_id,
  performer_verb,
  energy_mwh,
  price_per_mwh,
  raw_kqml
FROM kqml_timeline
ORDER BY timestamp ASC;
```

#### Get Agent Summary
```sql
SELECT 
  agent_id,
  COUNT(*) as total_events,
  COUNT(DISTINCT event_type) as event_types,
  MIN(timestamp) as first_event,
  MAX(timestamp) as latest_event
FROM audit_events
GROUP BY agent_id;
```

#### Find Tool Errors
```sql
SELECT 
  timestamp,
  agent_id,
  tool_name,
  tool_error
FROM audit_events
WHERE tool_error IS NOT NULL
ORDER BY timestamp DESC;
```

#### Trace Decision Path (with Ground Truth)
```sql
SELECT 
  timestamp,
  event_type,
  hook_name,
  tool_name,
  kqml_performative,
  json_extract(grid_state_snapshot, '$.solar_output_mw') as solar,
  json_extract(grid_state_snapshot, '$.wind_output_mw') as wind
FROM audit_events
WHERE agent_id = 'microgrid-agent'
  AND timestamp > datetime('now', '-1 hour')
ORDER BY timestamp ASC;
```

---

## 📊 What Gets Captured

### When Agent Starts: on_agent_start
```
[INITIALIZATION] Agent started with verified identity
  Event ID: a1b2c3d4-e5f6-4789-0123-456789abcdef
  Agent: microgrid-agent (control)
  Account: microgrid-agent@microgrid.local
```

### When Tool is Called: on_tool_start
```
[TOOL_INVOCATION] Tool started: retrieve_grid_state (MCP: retrieve_grid_state)
  Event ID: b2c3d4e5-f6a7-8901-2345-6789abcdef01
  Agent: microgrid-agent (control)
  Account: microgrid-agent@microgrid.local

Captured in DB:
  - tool_name: retrieve_grid_state
  - mcp_operation: retrieve_grid_state
  - grid_state_snapshot: {solar: 2.5MW, wind: 1.3MW, battery_soc: 75%}
  - pricing_data_snapshot: {market_price: 45.50 $/MWh}
```

### When Tool Completes: on_tool_end
```
[TOOL_COMPLETION] Tool completed: retrieve_grid_state (256.7ms)
  Event ID: c3d4e5f6-a7b8-9012-3456-789abcdef012
  Agent: microgrid-agent (control)
  Account: microgrid-agent@microgrid.local

Captured in DB:
  - tool_name: retrieve_grid_state
  - tool_outputs: {status: success, grid_state: {...}}
  - tool_execution_ms: 256.7
  - tool_error: null
```

### When Model Infers: on_model_end
```
[MODEL_INFERENCE] Model inference complete: gemini-2.5-flash (performative: propose)
  Event ID: d4e5f6a7-b8c9-0123-4567-89abcdef0123
  Agent: microgrid-agent (control)
  Account: microgrid-agent@microgrid.local

Captured in DB:
  - model_name: gemini-2.5-flash
  - kqml_performative: propose
  - kqml_raw: "I propose to offer 1.5 MW at $47/MWh"
  - model_input_tokens: 2048
  - model_output_tokens: 256
```

---

## 📁 Files Created/Modified

```
/Users/school/Documents/distributed-agent system/
├── shared/
│   ├── instrumentation_plugin.py  ← NEW: BasePlugin with lifecycle hooks
│   ├── local_audit_db.py          ← NEW: SQLite backend
│   ├── config.py                  ← UPDATED: local instrumentation vars
│   └── auth.py                    ← UPDATED: identity injection functions
├── microgrid_agent/
│   └── microgrid_agent.py         ← UPDATED: plugin registration
├── requirements.txt               ← CLEANED: removed cloud packages
├── LOCAL_INSTRUMENTATION.md       ← NEW: usage guide
├── IMPLEMENTATION_COMPLETE.md     ← NEW: what was implemented
├── DEMO.md                        ← NEW: this file
└── audit_trail.db                 ← CREATED AT RUNTIME: SQLite database
```

---

## 🔍 Database Tables

### audit_events (All Lifecycle Events)
```
event_id             UUID of event
timestamp            ISO 8601 timestamp
agent_id             Which agent (microgrid-agent, solar-agent, etc.)
agent_role           Role (control, solar, wind, battery, load)
event_type           initialization | tool_invocation | tool_completion | model_inference
hook_name            on_agent_start | on_tool_start | on_tool_end | on_model_end
verified_account     Verified service account (signed)
tool_name            Name of tool (retrieve_grid_state, set_curtailment, etc.)
tool_inputs          Ground truth inputs (MCP inputs BEFORE decision)
tool_outputs         Tool results
tool_error           Error if tool failed
mcp_operation        Detected MCP operation name
kqml_performative    KQML verb (propose, accept, reject, inform, request)
kqml_raw             Raw KQML message
grid_state_snapshot  Complete grid state at decision time (JSON)
pricing_data_snapshot Market pricing at decision time (JSON)
created_at           When record was inserted
```

### kqml_timeline (Energy Negotiation)
```
performative_id      UUID of performative
timestamp            ISO 8601 timestamp
sender_agent_id      Which agent issued this (solar-agent, battery-agent, etc.)
performer_verb       propose | accept | reject | inform | request
raw_kqml             Complete raw KQML message
energy_mwh           Megawatts in offer
price_per_mwh        Price per MWh
response_performative_id  ID of response performative (if any)
created_at           When record was inserted
```

---

## 💡 Key Insights

**Non-Repudiation:**
- Every event signed with verified_account + timestamp
- Agent cannot claim "I didn't decide that"
- Proof: Database contains every decision with identity

**Ground Truth:**
- MCP inputs captured BEFORE agent decides
- Can reconstruct: "Here's the data agent saw"
- Proof: grid_state_snapshot + pricing_data_snapshot

**Energy Negotiation Timeline:**
- KQML performatives stored chronologically
- Shows who offered what at what price
- Can recreate exact negotiation sequence

**Audit Trail:**
- No modifications possible (append-only)
- All events preserved with timestamps
- Can trace entire decision path

---

## 🎯 Next Steps

1. **Add to other agents:**
   ```python
   # Copy pattern from microgrid_agent.py to:
   - solar_agent/solar_agent.py
   - wind_agent/wind_agent.py
   - battery_agent/battery_agent.py
   - load_agent/load_agent.py
   ```

2. **Run entire swarm:**
   ```bash
   docker-compose up --build
   # All agents log to same audit_trail.db
   ```

3. **Analyze swarm decisions:**
   ```sql
   SELECT timestamp, agent_id, event_type, kqml_performative
   FROM audit_events
   ORDER BY timestamp
   -- Can see entire agent swarm decision sequence
   ```

---

## ✅ Summary

- **Everything stays local** (no cloud, no internet)
- **Queryable with SQL** (full database queries)
- **Non-repudiable** (signed with verified account)
- **Ground truth captured** (MCP inputs before decisions)
- **KQML timeline** (energy negotiation recorded)
- **Ready to use** (start immediately)

**Status: ✅ IMPLEMENTATION COMPLETE AND READY TO USE**

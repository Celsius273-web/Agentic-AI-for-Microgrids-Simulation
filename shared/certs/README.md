# mTLS Certificate Management

Mutual TLS (mTLS) certificate infrastructure for the Microgrid Agent System. Provides agent authentication and encrypted communication on the Docker network.

## Quick Start

Generate all certificates for configured agents:

```bash
cd shared/certs
chmod +x generate_certs.sh
./generate_certs.sh generate
```

This creates:
- `ca.crt` and `ca.key` (Root Certificate Authority)
- `{agent-name}-server.crt` and `{agent-name}-server.key` (HTTPS endpoints)
- `{agent-name}-client.crt` and `{agent-name}-client.key` (Outbound requests)
- `.cert_manifest.txt` (Audit trail with fingerprints)

## Adding New Agents

The system is designed for unlimited agent expansion. No code changes required.

### Step 1: Update agents.conf

Add agent name to `shared/certs/agents.conf`:

```
# Current agents
microgrid-agent
control-agent
researcher-agent

# New agents
solar-agent
wind-agent
```

### Step 2: Regenerate Certificates

```bash
./generate_certs.sh generate
```

The script:
- Detects new agents from agents.conf
- Generates certs for new agents (skips existing)
- Verifies all certs against CA
- Updates manifest with fingerprints

### Step 3: Update docker-compose.yml

For each new agent, add certificate volume mount:

```yaml
  solar-agent:
    build: .
    volumes:
      - ./shared/certs:/app/shared/certs:ro
    environment:
      - AGENT_ID=solar-agent
      - CERTS_DIR=/app/shared/certs
      - ENABLE_MTLS=true
```

### Step 4: Update config.py

Agent loads certs from environment:

```python
CERTS_DIR = os.environ.get("CERTS_DIR", "/app/shared/certs")
AGENT_ID = os.environ.get("AGENT_ID")

# Paths are auto-constructed
SERVER_CERT = f"{CERTS_DIR}/{AGENT_ID}-server.crt"
SERVER_KEY = f"{CERTS_DIR}/{AGENT_ID}-server.key"
CLIENT_CERT = f"{CERTS_DIR}/{AGENT_ID}-client.crt"
CLIENT_KEY = f"{CERTS_DIR}/{AGENT_ID}-client.key"
CA_CERT = f"{CERTS_DIR}/ca.crt"
```

### Step 5: Add FastAPI HTTPS Endpoint

Agent creates HTTPS server:

```python
from fastapi import FastAPI
import uvicorn
import ssl

app = FastAPI()

@app.post("/command")
async def command(request: CommandRequest) -> CommandResponse:
    # Handle agent command
    pass

if __name__ == "__main__":
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(SERVER_CERT, SERVER_KEY)
    ssl_context.load_verify_locations(CA_CERT)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8443,
        ssl_context=ssl_context
    )
```

No modifications to certificate generation. The system automatically recognizes new agents.

## Certificate Structure

Each agent gets four files:

```
shared/certs/
├── ca.crt                          # Root CA (shared by all agents)
├── ca.key                          # CA private key (keep secure)
├── microgrid-agent-server.crt      # Server identity (HTTPS endpoint)
├── microgrid-agent-server.key      # Server private key
├── microgrid-agent-client.crt      # Client identity (outbound calls)
├── microgrid-agent-client.key      # Client private key
├── control-agent-server.crt
├── control-agent-server.key
├── control-agent-client.crt
├── control-agent-client.key
└── ...
```

### CA Certificate (ca.crt)

- Root authority for entire agent network
- Shared by all agents
- Public (distributed in code)
- Used to verify peer certificates

### Server Certificate ({agent}-server.crt/key)

- Presented when agent accepts HTTPS connections
- Verifies agent identity to incoming requests
- Subject CN: `{agent}.agents.microgrid`
- SANs: `{agent}`, localhost, 127.0.0.1

### Client Certificate ({agent}-client.crt/key)

- Presented when agent calls another agent
- Verifies caller identity to server
- Same CN as server (can be different if needed)
- Used in mTLS handshake with peer

## Certificate Validation

Verify all certs are valid:

```bash
./generate_certs.sh validate
```

This checks:
- All certs signed by CA
- All certs within validity period
- All SANs correctly configured

Check individual cert:

```bash
openssl x509 -in microgrid-agent-server.crt -noout -text
```

View certificate chain:

```bash
openssl verify -CAfile ca.crt microgrid-agent-server.crt
```

## Certificate Fingerprints

Each certificate has a SHA256 fingerprint for audit trail.

View CA fingerprint:

```bash
openssl x509 -in ca.crt -noout -fingerprint -sha256
```

View manifest with all fingerprints:

```bash
cat .cert_manifest.txt
```

Fingerprints are logged on agent startup for verification:

```
[mtls] Server cert fingerprint: 12:34:56:78:...
[mtls] Client cert fingerprint: 87:65:43:21:...
```

## Certificate Lifetime

- Validity: 365 days (configurable in script)
- Generated: Timestamp in manifest
- Renewal: Delete and regenerate (see Reset Certificates below)

When certificates expire:
1. Agent startup fails with SSL error
2. mTLS handshake fails for peer communication
3. Regenerate: `./generate_certs.sh generate`
4. Restart agents

## Reset Certificates

Delete all certificates and regenerate from scratch:

```bash
./generate_certs.sh reset
```

Prompts for confirmation (type 'yes' to proceed).

Use cases:
- Compromise of private key
- Certificate corruption
- Complete system reinstall
- Testing certificate rotation

## File Permissions

The script sets correct permissions automatically:

- `ca.key`: 400 (owner read-only)
- `ca.crt`: 444 (world-readable)
- `{agent}-server.key`: 400 (owner read-only)
- `{agent}-server.crt`: 444 (world-readable)
- `{agent}-client.key`: 400 (owner read-only)
- `{agent}-client.crt`: 444 (world-readable)

Private keys must not be world-readable. The script enforces this.

## Testing mTLS Locally

On your Mac with Docker running, test mTLS handshake:

### 1. Generate Certificates

```bash
cd shared/certs
./generate_certs.sh generate
```

### 2. Start Docker Containers

```bash
docker compose up --build
```

### 3. Test HTTPS Connection (Inside Container)

```bash
docker exec microgrid-agent bash -c "
  curl --cacert /app/shared/certs/ca.crt \
       --cert /app/shared/certs/microgrid-agent-client.crt \
       --key /app/shared/certs/microgrid-agent-client.key \
       https://localhost:8443/health
"
```

Expected result:
- Success (200): Server verified, client cert presented
- SSL error: Certificate problem (check CA, SANs, validity)
- Connection refused: Server not running or wrong port

### 4. Test Agent-to-Agent Call

In `agent_interfaces.py`, make actual call:

```python
import requests
import os

def control_agent_access(command: str, params=None):
    url = "https://control-agent:8443/command"
    
    cert = (
        "/app/shared/certs/microgrid-agent-client.crt",
        "/app/shared/certs/microgrid-agent-client.key"
    )
    verify = "/app/shared/certs/ca.crt"
    
    response = requests.post(url, json={
        "command": command,
        "params": params or {}
    }, cert=cert, verify=verify)
    
    return response.json()
```

## Troubleshooting

### "SSL: CERTIFICATE_VERIFY_FAILED"

Cause: Server cert not signed by CA, or wrong CA cert used.

Solution:
- Verify server cert: `openssl verify -CAfile ca.crt {agent}-server.crt`
- Check CA fingerprint matches on both client and server
- Regenerate: `./generate_certs.sh reset && ./generate_certs.sh generate`

### "SSL: SSLV3_ALERT_HANDSHAKE_FAILURE"

Cause: Client cert not accepted by server.

Solution:
- Check server is using correct CA cert for verification
- Verify client cert: `openssl verify -CAfile ca.crt {agent}-client.crt`
- Check cert SANs: `openssl x509 -in {agent}-server.crt -noout -text | grep DNS`

### "SSL: CERTIFICATE_REQUIRED"

Cause: Server requires client cert, but none provided.

Solution:
- Pass `--cert` and `--key` to curl/requests
- Check server SSL config: `VERIFY_PEER_CERTS=true`

### "SSL: UNEXPECTED_EOF_WHILE_READING"

Cause: Non-HTTPS endpoint accessed with HTTPS client.

Solution:
- Verify agent is listening on correct port (8443 for HTTPS, not 8000)
- Check agent startup logs: "SSL context initialized"

### "Name mismatch: expected {agent-name}, got ..."

Cause: Hostname doesn't match certificate SAN.

Solution:
- Check SAN in cert: `openssl x509 -in {agent}-server.crt -noout -text | grep DNS`
- Use correct hostname: `{agent-name}` inside Docker, `localhost` from Mac

## Security Considerations

1. Private Keys: Keep ca.key, {agent}-server.key, {agent}-client.key private. Never commit to version control.

2. Certificate Distribution: ca.crt is public. Agents need it to verify peers. Public certs ({agent}-server.crt, {agent}-client.crt) can be exposed.

3. Docker Volumes: Mount certs as read-only (`:ro` flag) inside containers.

4. Renewal: Plan to regenerate certificates before expiry (365 days). Automate with scheduled task.

5. Compromise: If private key exposed, regenerate all certificates immediately.

## Certificate Manifest

The script maintains a manifest file (`.cert_manifest.txt`) with:

- CA generation date and fingerprint
- Each agent's cert fingerprints and validity period
- Timestamps for audit trail

Review manifest:

```bash
cat .cert_manifest.txt
```

This provides a non-repudiable record of certificate lifecycle.

## Integration with Instrumentation Plugin

The instrumentation plugin logs certificate fingerprints for every mTLS handshake:

```sql
SELECT timestamp, agent_id, cert_fingerprint, verified_account
FROM audit_events
WHERE event_type = 'mtls_handshake'
ORDER BY timestamp DESC;
```

This creates a complete audit trail of which agents communicated and when.

## Scaling Beyond Three Agents

The system scales to any number of agents with zero code changes:

1. Add agent name to agents.conf
2. Run `./generate_certs.sh generate`
3. Update docker-compose.yml
4. Implement FastAPI endpoint in agent

Same certificate infrastructure supports 3 agents or 300 agents.

## FAQ

Q: Do I need separate client and server certs?

A: Not required, but recommended. Allows fine-grained control: server key compromise doesn't affect outbound auth, and vice versa. For simplicity, can use same cert for both.

Q: Can I use the same cert for all agents?

A: Not recommended. Each agent should have unique identity. SANs and CN help prevent MITM attacks.

Q: How do I update certs in production without downtime?

A: Generate new certs with longer validity period, distribute to all agents, agents can load new certs on restart, then gradually restart agents.

Q: What if I lose ca.key?

A: Cannot verify new agent certs or rotate existing certs. All certs become effectively permanent. Keep backups.

Q: Can I use real certificates from Let's Encrypt?

A: Yes, in cloud deployment. For local Docker network, self-signed is sufficient and simpler.

## References

- OpenSSL Documentation: https://www.openssl.org/docs/
- RFC 5280: X.509 Certificate Standard
- NIST SP 800-32: PKI Guidelines

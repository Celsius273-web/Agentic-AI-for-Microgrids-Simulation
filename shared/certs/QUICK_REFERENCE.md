# Certificate Operations Quick Reference

## One-Time Setup

```bash
cd shared/certs
chmod +x generate_certs.sh
./generate_certs.sh generate
```

Generates CA and certs for all agents in agents.conf.

## Daily Operations

### View Certificate Info

```bash
# CA certificate
openssl x509 -in ca.crt -noout -text

# Specific agent cert
openssl x509 -in microgrid-agent-server.crt -noout -text

# Check validity
openssl x509 -in microgrid-agent-server.crt -noout -dates
```

### Verify Cert is Signed by CA

```bash
openssl verify -CAfile ca.crt microgrid-agent-server.crt
```

Expected: "microgrid-agent-server.crt: OK"

### View Certificate Fingerprints

```bash
# CA
openssl x509 -in ca.crt -noout -fingerprint -sha256

# Agent server cert
openssl x509 -in microgrid-agent-server.crt -noout -fingerprint -sha256

# Agent client cert
openssl x509 -in microgrid-agent-client.crt -noout -fingerprint -sha256

# All in manifest
cat .cert_manifest.txt
```

### View Subject Alternative Names (SANs)

```bash
openssl x509 -in microgrid-agent-server.crt -noout -text | grep -A 5 "Subject Alternative Name"
```

## Adding a New Agent

### 1. Edit agents.conf

```
microgrid-agent
control-agent
researcher-agent
solar-agent          # <-- Add here
```

### 2. Generate Certificates

```bash
./generate_certs.sh generate
```

New certs created. Existing certs skipped.

### 3. Update docker-compose.yml

```yaml
solar-agent:
  volumes:
    - ./shared/certs:/app/shared/certs:ro
  environment:
    - AGENT_ID=solar-agent
    - CERTS_DIR=/app/shared/certs
    - ENABLE_MTLS=true
```

### 4. Agent Code

In agent Python file:

```python
from shared.config import CERTS_DIR, AGENT_ID

SERVER_CERT = f"{CERTS_DIR}/{AGENT_ID}-server.crt"
SERVER_KEY = f"{CERTS_DIR}/{AGENT_ID}-server.key"
CLIENT_CERT = f"{CERTS_DIR}/{AGENT_ID}-client.crt"
CLIENT_KEY = f"{CERTS_DIR}/{AGENT_ID}-client.key"
CA_CERT = f"{CERTS_DIR}/ca.crt"
```

## Regenerate Everything

```bash
./generate_certs.sh reset  # Confirm with 'yes'
./generate_certs.sh generate
```

Use if: Key compromised, certs corrupted, or complete reinstall needed.

## Validate All Certs

```bash
./generate_certs.sh validate
```

Returns: All certs valid, or error list.

## List All Certs

```bash
./generate_certs.sh list
```

Shows file sizes and manifest.

## File Locations

All files in: `shared/certs/`

```
ca.crt                              # Public
ca.key                              # Private - KEEP SECRET
{agent}-server.crt                  # Public
{agent}-server.key                  # Private
{agent}-client.crt                  # Public
{agent}-client.key                  # Private
.cert_manifest.txt                  # Audit log
agents.conf                         # Config
generate_certs.sh                   # Script
README.md                           # Full docs
```

## Test mTLS Connection

Default (host-based, runtime image):

```bash
curl --cacert shared/certs/ca.crt \
     --cert shared/certs/microgrid-agent-client.crt \
     --key shared/certs/microgrid-agent-client.key \
     https://localhost:8444/health
```

Optional in-container debug mode only:

```bash
docker compose -f docker-compose.yml -f docker-compose.debug.yml up --build
docker exec microgrid-agent curl --cacert /app/shared/certs/ca.crt \
     --cert /app/shared/certs/microgrid-agent-client.crt \
     --key /app/shared/certs/microgrid-agent-client.key \
     https://control-agent:8443/health
```

Success: 200 response
Failure: SSL error (see README troubleshooting)

## Backup Certs

```bash
tar czf certs_backup_$(date +%Y%m%d).tar.gz shared/certs/
```

Keep backups secure. Contains private keys.

## Permissions Check

```bash
ls -l shared/certs/*.key
ls -l shared/certs/*.crt
```

Private keys should be: `-r--------` (400)
Public certs should be: `-r--r--r--` (444)

## Environment Variables

Set in docker-compose.yml for each agent:

```
AGENT_ID=microgrid-agent
CERTS_DIR=/app/shared/certs
ENABLE_MTLS=true
VERIFY_PEER_CERTS=true
```

## Security Checklist

- [ ] Private keys (.key files) never committed to git
- [ ] .gitignore includes *.key
- [ ] ca.key backed up securely
- [ ] Certs mounted read-only (`:ro`) in Docker
- [ ] Certs/keys are never copied into Docker image layers
- [ ] Certificate manifest reviewed (.cert_manifest.txt)
- [ ] Fingerprints logged on agent startup
- [ ] All certs validated with `./generate_certs.sh validate`

## Troubleshooting One-Liners

```bash
# Verify cert chain
openssl verify -CAfile ca.crt microgrid-agent-server.crt -show_chain

# Check cert expiration
openssl x509 -in microgrid-agent-server.crt -noout -enddate

# Compare cert fingerprints
diff <(openssl x509 -in ca.crt -noout -fingerprint -sha256) \
     <(cat .cert_manifest.txt | grep "Fingerprint")

# Extract CN from cert
openssl x509 -in microgrid-agent-server.crt -noout -subject | grep -o CN=.*

# List all SANs
openssl x509 -in microgrid-agent-server.crt -noout -text | grep DNS
```

## Agent Scaling

Same process for 3 agents or 300 agents:

1. Add names to agents.conf
2. Run `./generate_certs.sh generate`
3. Update docker-compose.yml
4. Implement FastAPI HTTPS in agent

Zero code changes to certificate generation.

## Next Steps

After certificates generated:

1. Update config.py to load cert paths
2. Update agent_interfaces.py for mTLS calls
3. Add FastAPI HTTPS server to each agent
4. Update docker-compose.yml volumes
5. Test with `./generate_certs.sh validate`
6. Deploy with `docker compose up`

See Phase 1 plan for full integration steps.

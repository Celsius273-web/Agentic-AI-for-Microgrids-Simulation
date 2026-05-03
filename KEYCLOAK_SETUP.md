# Keycloak Setup for Local Development

This guide explains how to set up and use Keycloak for local OIDC authentication in the microgrid system.

## Quick Start

### 1. Start with Keycloak (Local Mode)
```bash
# Set environment variables for local authentication
export AUTH_MODE=local
export OIDC_ISSUER=http://keycloak:8080/realms/microgrid
export OIDC_AUDIENCE=microgrid-agents

# Start the system
docker-compose up keycloak redis microgrid-agent
```

### 2. Configure Keycloak Realm

1. **Access Keycloak Admin Console**
   - URL: http://localhost:8080
   - Username: `admin`
   - Password: `admin123`

2. **Create Microgrid Realm**
   - Click "Create Realm" 
   - Name: `microgrid`
   - Enable: Yes

3. **Create Client for Agent Communication**
   - In microgrid realm, go to Clients → Create
   - Client ID: `microgrid-agents`
   - Client authentication: ON
   - Service accounts roles: ON
   - Valid redirect URIs: `*` (for development)

4. **Get Client Secret**
   - Go to microgrid-agents client → Credentials tab
   - Copy the Client Secret

5. **Update Environment Variables**
```bash
export KEYCLOAK_CLIENT_SECRET=your-copied-secret
```

### 3. Switch to Google Cloud (Cloud Mode)
```bash
# Set environment variables for Google Cloud
export AUTH_MODE=cloud
export OIDC_ISSUER=https://accounts.google.com
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Restart the system
docker-compose restart
```

## Environment Variables Reference

### Required for All Modes
```bash
AUTH_MODE=local|cloud                    # Authentication mode
OIDC_AUDIENCE=microgrid-agents          # OIDC audience claim
```

### Local Mode (Keycloak)
```bash
AUTH_MODE=local
OIDC_ISSUER=http://keycloak:8080/realms/microgrid
KEYCLOAK_REALM=microgrid
KEYCLOAK_CLIENT_ID=microgrid-agents
KEYCLOAK_CLIENT_SECRET=your-client-secret
```

### Cloud Mode (Google Cloud)
```bash
AUTH_MODE=cloud
OIDC_ISSUER=https://accounts.google.com
GOOGLE_APPLICATION_CREDENTIALS=/app/creds/service-account.json
```

## Docker Compose Configuration

The system now includes Keycloak as a service:

```yaml
keycloak:
  image: quay.io/keycloak/keycloak:latest
  container_name: microgrid-keycloak
  environment:
    - KEYCLOAK_ADMIN=admin
    - KEYCLOAK_ADMIN_PASSWORD=admin123
  ports:
    - "8080:8080"
  networks:
    - microgrid-net
  command: start-dev
```

## Authentication Flow

### Local Mode (Keycloak)
1. Agent starts and connects to Keycloak
2. Uses client credentials flow to get access token
3. Includes token in `Authorization: Bearer <token>` header for inter-agent calls
4. Receiving agent validates token against Keycloak JWKS endpoint

### Cloud Mode (Google Cloud)  
1. Agent loads service account credentials
2. Generates Google Cloud access token
3. Includes token in `Authorization: Bearer <token>` header
4. Receiving agent validates token against Google's JWKS endpoint

## Switching Between Modes

You can switch authentication modes without code changes:

```bash
# Switch to local Keycloak
export AUTH_MODE=local
docker-compose restart

# Switch to Google Cloud  
export AUTH_MODE=cloud
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/creds.json
docker-compose restart
```

## Troubleshooting

### Keycloak Connection Issues
```bash
# Check Keycloak is running
docker-compose logs keycloak

# Check Keycloak is reachable from agents
docker exec -it microgrid-agent curl http://keycloak:8080/realms/microgrid/.well-known/openid_configuration
```

### Authentication Failures
```bash
# Check agent logs for auth errors
docker-compose logs microgrid-agent | grep -i auth

# Verify client secret is correct
# Check Keycloak admin console → microgrid-agents client → Credentials
```

### Token Validation Issues
```bash
# Test token generation manually
docker exec -it microgrid-agent python3 -c "
from shared import auth
token = auth.get_service_account_token()
print(f'Token: {token[:50]}...')
"
```

## Security Considerations

### Development (Keycloak)
- ✅ Uses OIDC standard protocols
- ✅ Tokens are signed and validated
- ⚠️ Admin password is hardcoded (change for production)
- ⚠️ HTTP only (add HTTPS for production)

### Production Recommendations
1. **Use HTTPS for Keycloak**
2. **Change default admin credentials**
3. **Use proper redirect URIs (not `*`)**
4. **Enable token rotation**
5. **Set up proper realm and client roles**

## Benefits of This Approach

1. **Easy Development**: Local Keycloak for testing
2. **Production Ready**: Switch to Google Cloud seamlessly  
3. **Standard Protocols**: Uses OIDC/OAuth2 throughout
4. **No Code Changes**: Switch via environment variables only
5. **Audit Trail**: All authentication events logged with verified identity
#!/bin/bash

################################################################################
# MICROGRID mTLS CERTIFICATE GENERATOR
#
# Generates CA and agent certificates for Docker-based agent network.
# Supports any number of agents via agents.conf configuration file.
#
# Usage:
#   ./generate_certs.sh               (uses agents.conf in same directory)
#   ./generate_certs.sh --reset       (delete all existing certs and regenerate)
#   ./generate_certs.sh --list        (show all generated certificates)
#   ./generate_certs.sh --validate    (verify all certs are valid)
#
# Requirements:
#   - OpenSSL 1.1.1+
#   - Bash 4.0+
#   - agents.conf file in the same directory
#
# Exit codes:
#   0 - Success
#   1 - Missing dependencies or file errors
#   2 - Configuration error
#   3 - Certificate generation error
#
################################################################################

set -euo pipefail

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script directory and files
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
AGENTS_CONF="${SCRIPT_DIR}/agents.conf"
CERT_LOG="${SCRIPT_DIR}/.cert_manifest.txt"
CA_CONF="${SCRIPT_DIR}/ca.conf"
CSR_CONF_TEMPLATE="${SCRIPT_DIR}/agent-csr.conf.template"

# Certificate parameters
CERT_VALIDITY_DAYS=365
KEY_SIZE=2048
ALGORITHM="rsa:${KEY_SIZE}"
CA_CN="microgrid-ca.local"
CA_O="Microgrid Authority"
CA_C="US"
CA_ST="CA"
CA_L="Local"

################################################################################
# LOGGING AND UTILITIES
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

print_header() {
    echo ""
    echo -e "${BLUE}================================================================================${NC}"
    echo -e "${BLUE}$*${NC}"
    echo -e "${BLUE}================================================================================${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${BLUE}>>> $*${NC}"
}

# Check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get current timestamp
get_timestamp() {
    date -u +"%Y-%m-%d %H:%M:%S UTC"
}

################################################################################
# VALIDATION FUNCTIONS
################################################################################

validate_dependencies() {
    print_section "Validating dependencies"
    
    local missing=0
    
    if ! command_exists openssl; then
        log_error "OpenSSL not found. Install with: brew install openssl"
        ((missing++))
    else
        local openssl_version=$(openssl version | awk '{print $2}')
        log_info "OpenSSL version: $openssl_version"
    fi
    
    if ! command_exists bash; then
        log_error "Bash not found (this is unexpected)"
        ((missing++))
    fi
    
    if [ $missing -gt 0 ]; then
        log_error "Missing $missing dependencies"
        return 1
    fi
    
    log_success "All dependencies found"
    return 0
}

validate_agent_name() {
    local agent_name="$1"
    
    if [[ ! "$agent_name" =~ ^[a-z][a-z0-9_-]*$ ]]; then
        log_error "Invalid agent name: '$agent_name'. Must start with letter, contain only lowercase letters, numbers, hyphens, underscores."
        return 1
    fi
    
    return 0
}

validate_config_file() {
    print_section "Validating configuration"
    
    if [ ! -f "$AGENTS_CONF" ]; then
        log_error "Configuration file not found: $AGENTS_CONF"
        log_info "Create agents.conf with agent names, one per line"
        return 2
    fi
    
    if [ ! -s "$AGENTS_CONF" ]; then
        log_error "Configuration file is empty: $AGENTS_CONF"
        return 2
    fi
    
    log_info "Reading agents from: $AGENTS_CONF"
    
    # Count valid agents
    local agent_count=0
    local invalid_count=0
    
    while IFS= read -r agent || [ -n "$agent" ]; do
        agent=$(echo "$agent" | xargs)  # Trim whitespace
        
        # Skip empty lines and comments
        [[ -z "$agent" || "$agent" =~ ^# ]] && continue
        
        if validate_agent_name "$agent"; then
            ((agent_count++))
        else
            ((invalid_count++))
        fi
    done < "$AGENTS_CONF"
    
    if [ $invalid_count -gt 0 ]; then
        log_error "Found $invalid_count invalid agent names in configuration"
        return 2
    fi
    
    if [ $agent_count -eq 0 ]; then
        log_error "No valid agents found in $AGENTS_CONF"
        return 2
    fi
    
    log_success "Configuration valid: $agent_count agents"
    return 0
}

read_agent_list() {
    local agents=()
    
    while IFS= read -r agent || [ -n "$agent" ]; do
        agent=$(echo "$agent" | xargs)  # Trim whitespace
        [[ -z "$agent" || "$agent" =~ ^# ]] && continue
        agents+=("$agent")
    done < "$AGENTS_CONF"
    
    printf '%s\n' "${agents[@]}"
}

################################################################################
# OPENSSL CONFIGURATION GENERATION
################################################################################

create_ca_config() {
    print_section "Creating CA configuration"
    
    cat > "$CA_CONF" << 'EOF'
[ ca ]
default_ca = CA_default

[ CA_default ]
dir              = .
certs            = $dir
crl_dir          = $dir
new_certs_dir    = $dir
database         = $dir/.index.txt
serial           = $dir/.serial.txt
RANDFILE         = $dir/.rand
private_key      = $dir/ca.key
certificate      = $dir/ca.crt
crl              = $dir/ca.crl
crl_extensions   = crl_ext
default_crl_days = 30
name_opt         = ca_default
cert_opt         = ca_default
default_md       = sha256
preserve         = no
policy           = policy_strict

[ policy_strict ]
countryName             = match
stateOrProvinceName      = match
organizationName         = match
organizationalUnitName   = optional
commonName               = supplied

[ req ]
default_bits        = 2048
default_md           = sha256
default_keyfile      = private.key
distinguished_name   = req_distinguished_name
string_mask          = utf8only
x509_extensions      = v3_ca
req_extensions       = v3_req

[ req_distinguished_name ]
countryName                      = Country Name
stateOrProvinceName              = State or Province Name
organizationName                 = Organization Name
organizationalUnitName           = Organizational Unit Name
commonName                       = Common Name

[ v3_ca ]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints = critical,CA:true
keyUsage = critical,keyCertSign,cRLSign

[ v3_req ]
subjectKeyIdentifier = hash
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth,clientAuth

[ agent_server ]
basicConstraints = critical,CA:false
nsCertType = server
nsComment = "Agent Server Certificate"
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer:always
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth

[ agent_client ]
basicConstraints = critical,CA:false
nsCertType = client
nsComment = "Agent Client Certificate"
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = clientAuth
EOF
    
    log_success "CA configuration created"
}

create_agent_csr_config() {
    local agent_name="$1"
    local agent_cn="${agent_name}.agents.microgrid"
    local agent_service="${agent_name}"
    
    cat > "${SCRIPT_DIR}/${agent_name}-csr.conf" << EOF
[ req ]
default_bits       = 2048
default_md         = sha256
distinguished_name = req_distinguished_name
req_extensions     = v3_req
prompt             = no

[ req_distinguished_name ]
C  = ${CA_C}
ST = ${CA_ST}
L  = ${CA_L}
O  = ${CA_O}
OU = Agents
CN = ${agent_cn}

[ v3_req ]
subjectKeyIdentifier = hash
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ${agent_name}
DNS.2 = ${agent_service}
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF
}

################################################################################
# CERTIFICATE GENERATION
################################################################################

generate_ca_cert() {
    print_section "Generating CA certificate"
    
    if [ -f "$SCRIPT_DIR/ca.crt" ] && [ -f "$SCRIPT_DIR/ca.key" ]; then
        log_warn "CA certificates already exist. Skipping CA generation."
        log_info "Use --reset flag to regenerate all certificates"
        return 0
    fi
    touch "$SCRIPT_DIR/.index.txt"
    echo "1000" > "$SCRIPT_DIR/.serial.txt"

    log_info "Generating CA private key (${KEY_SIZE} bits)..."
    openssl genrsa -out "$SCRIPT_DIR/ca.key" "$KEY_SIZE" 2>/dev/null
    
    log_info "Generating CA certificate (${CERT_VALIDITY_DAYS} days)..."
    openssl req -new -x509 \
        -key "$SCRIPT_DIR/ca.key" \
        -out "$SCRIPT_DIR/ca.crt" \
        -days "$CERT_VALIDITY_DAYS" \
        -subj "/C=${CA_C}/ST=${CA_ST}/L=${CA_L}/O=${CA_O}/CN=${CA_CN}" \
        -extensions v3_ca -config "$CA_CONF" \
        2>/dev/null
    
    chmod 400 "$SCRIPT_DIR/ca.key"
    chmod 444 "$SCRIPT_DIR/ca.crt"
    
    local ca_fingerprint=$(openssl x509 -in "$SCRIPT_DIR/ca.crt" -noout -fingerprint -sha256 | cut -d= -f2)
    log_success "CA certificate generated"
    log_info "CA Fingerprint (SHA256): $ca_fingerprint"
    
    {
        echo "=========================================="
        echo "CA CERTIFICATE METADATA"
        echo "=========================================="
        echo "Generated: $(get_timestamp)"
        echo "Validity: $CERT_VALIDITY_DAYS days"
        echo "Key Size: $KEY_SIZE bits"
        echo "Algorithm: RSA"
        echo "CN: $CA_CN"
        echo "Fingerprint: $ca_fingerprint"
        echo ""
    } >> "$CERT_LOG"
}

generate_agent_certs() {
    local agent_name="$1"
    local agent_cn="${agent_name}.agents.microgrid"
    
    print_section "Generating certificates for: $agent_name"
    
    # Create agent CSR config
    create_agent_csr_config "$agent_name"
    
    # Generate server certificate
    log_info "Generating server key..."
    openssl genrsa -out "${SCRIPT_DIR}/${agent_name}-server.key" "$KEY_SIZE" 2>/dev/null
    
    log_info "Generating server CSR..."
    openssl req -new \
        -key "${SCRIPT_DIR}/${agent_name}-server.key" \
        -out "${SCRIPT_DIR}/${agent_name}-server.csr" \
        -config "${SCRIPT_DIR}/${agent_name}-csr.conf"
    
    log_info "Signing server certificate..."
    openssl x509 -req \
        -in "${SCRIPT_DIR}/${agent_name}-server.csr" \
        -CA "$SCRIPT_DIR/ca.crt" \
        -CAkey "$SCRIPT_DIR/ca.key" \
        -CAcreateserial \
        -out "${SCRIPT_DIR}/${agent_name}-server.crt" \
        -days "$CERT_VALIDITY_DAYS" \
        -copy_extensions copy \
        -extensions agent_server \
        -extfile "$CA_CONF"
    
    # Generate client certificate (same CN as server for simplicity)
    log_info "Generating client key..."
    openssl genrsa -out "${SCRIPT_DIR}/${agent_name}-client.key" "$KEY_SIZE" 2>/dev/null
    
    log_info "Generating client CSR..."
    openssl req -new \
        -key "${SCRIPT_DIR}/${agent_name}-client.key" \
        -out "${SCRIPT_DIR}/${agent_name}-client.csr" \
        -config "${SCRIPT_DIR}/${agent_name}-csr.conf"
    
    log_info "Signing client certificate..."
    openssl x509 -req \
        -in "${SCRIPT_DIR}/${agent_name}-client.csr" \
        -CA "$SCRIPT_DIR/ca.crt" \
        -CAkey "$SCRIPT_DIR/ca.key" \
        -CAcreateserial \
        -out "${SCRIPT_DIR}/${agent_name}-client.crt" \
        -days "$CERT_VALIDITY_DAYS" \
        -extensions agent_client \
        -extfile "$CA_CONF"
    
    # Clean up CSR files
    rm -f "${SCRIPT_DIR}/${agent_name}-server.csr" "${SCRIPT_DIR}/${agent_name}-client.csr" "${SCRIPT_DIR}/${agent_name}-csr.conf"
    
    # Set permissions
    chmod 400 "${SCRIPT_DIR}/${agent_name}-server.key" "${SCRIPT_DIR}/${agent_name}-client.key"
    chmod 444 "${SCRIPT_DIR}/${agent_name}-server.crt" "${SCRIPT_DIR}/${agent_name}-client.crt"
    
    # Get fingerprints
    local server_fp=$(openssl x509 -in "${SCRIPT_DIR}/${agent_name}-server.crt" -noout -fingerprint -sha256 | cut -d= -f2)
    local client_fp=$(openssl x509 -in "${SCRIPT_DIR}/${agent_name}-client.crt" -noout -fingerprint -sha256 | cut -d= -f2)
    
    log_success "Certificates generated for: $agent_name"
    log_info "Server Fingerprint: $server_fp"
    log_info "Client Fingerprint: $client_fp"
    
    {
        echo "Agent: $agent_name"
        echo "Generated: $(get_timestamp)"
        echo "Server Certificate CN: $agent_cn"
        echo "Server Fingerprint: $server_fp"
        echo "Client Fingerprint: $client_fp"
        echo "Validity: $CERT_VALIDITY_DAYS days"
        echo ""
    } >> "$CERT_LOG"
}

################################################################################
# VERIFICATION FUNCTIONS
################################################################################

verify_cert() {
    local cert_file="$1"
    local ca_cert="$2"
    
    if [ ! -f "$cert_file" ]; then
        return 1
    fi
    
    openssl verify -CAfile "$ca_cert" "$cert_file" >/dev/null 2>&1
}

verify_all_certs() {
    print_section "Verifying all certificates"
    
    if [ ! -f "$SCRIPT_DIR/ca.crt" ]; then
        log_error "CA certificate not found"
        return 1
    fi
    
    local errors=0
    
    while IFS= read -r agent || [ -n "$agent" ]; do
        agent=$(echo "$agent" | xargs)
        [[ -z "$agent" || "$agent" =~ ^# ]] && continue
        
        log_info "Verifying $agent..."
        
        if ! verify_cert "${SCRIPT_DIR}/${agent}-server.crt" "$SCRIPT_DIR/ca.crt"; then
            log_error "Server certificate verification failed for $agent"
            ((errors++))
        else
            log_success "Server certificate valid"
        fi
        
        if ! verify_cert "${SCRIPT_DIR}/${agent}-client.crt" "$SCRIPT_DIR/ca.crt"; then
            log_error "Client certificate verification failed for $agent"
            ((errors++))
        else
            log_success "Client certificate valid"
        fi
    done < "$AGENTS_CONF"
    
    if [ $errors -eq 0 ]; then
        log_success "All certificates verified successfully"
        return 0
    else
        log_error "Certificate verification found $errors errors"
        return 1
    fi
}

################################################################################
# DISPLAY FUNCTIONS
################################################################################

list_certs() {
    print_section "Listing generated certificates"
    
    if [ ! -f "$SCRIPT_DIR/ca.crt" ]; then
        log_error "No certificates found"
        return 1
    fi
    
    echo "CA Certificate:"
    echo "  ca.crt ($(stat -f%z "$SCRIPT_DIR/ca.crt" 2>/dev/null || stat -c%s "$SCRIPT_DIR/ca.crt") bytes)"
    echo "  ca.key (private, 400)"
    echo ""
    
    while IFS= read -r agent || [ -n "$agent" ]; do
        agent=$(echo "$agent" | xargs)
        [[ -z "$agent" || "$agent" =~ ^# ]] && continue
        
        if [ -f "${SCRIPT_DIR}/${agent}-server.crt" ]; then
            echo "Agent: $agent"
            echo "  ${agent}-server.crt ($(stat -f%z "${SCRIPT_DIR}/${agent}-server.crt" 2>/dev/null || stat -c%s "${SCRIPT_DIR}/${agent}-server.crt") bytes)"
            echo "  ${agent}-server.key (private, 400)"
            echo "  ${agent}-client.crt ($(stat -f%z "${SCRIPT_DIR}/${agent}-client.crt" 2>/dev/null || stat -c%s "${SCRIPT_DIR}/${agent}-client.crt") bytes)"
            echo "  ${agent}-client.key (private, 400)"
            echo ""
        fi
    done < "$AGENTS_CONF"
    
    if [ -f "$CERT_LOG" ]; then
        echo "Certificate manifest: $CERT_LOG"
    fi
}

print_cert_info() {
    local cert_file="$1"
    
    if [ ! -f "$cert_file" ]; then
        log_error "Certificate not found: $cert_file"
        return 1
    fi
    
    echo ""
    echo "Certificate: $(basename "$cert_file")"
    openssl x509 -in "$cert_file" -noout -text | grep -E "Subject:|Issuer:|Not Before|Not After|Public-Key|DNS:" | sed 's/^/  /'
}

show_cert_info() {
    print_section "Certificate Information"
    
    print_cert_info "$SCRIPT_DIR/ca.crt"
    
    while IFS= read -r agent || [ -n "$agent" ]; do
        agent=$(echo "$agent" | xargs)
        [[ -z "$agent" || "$agent" =~ ^# ]] && continue
        
        print_cert_info "${SCRIPT_DIR}/${agent}-server.crt"
        print_cert_info "${SCRIPT_DIR}/${agent}-client.crt"
    done < "$AGENTS_CONF"
}

################################################################################
# CLEANUP FUNCTIONS
################################################################################

reset_all_certs() {
    print_header "RESETTING ALL CERTIFICATES"
    log_warn "This will delete all generated certificates"
    read -p "Are you sure? Type 'yes' to confirm: " -r
    echo
    
    if [[ ! $REPLY =~ ^yes$ ]]; then
        log_info "Reset cancelled"
        return 0
    fi
    
    log_info "Deleting certificates..."
    rm -f "$SCRIPT_DIR"/ca.{crt,key,srl}
    rm -f "$SCRIPT_DIR"/*-server.{crt,key}
    rm -f "$SCRIPT_DIR"/*-client.{crt,key}
    rm -f "$SCRIPT_DIR"/*.conf
    rm -f "$CERT_LOG" "$SCRIPT_DIR"/.index.txt "$SCRIPT_DIR"/.serial.txt "$SCRIPT_DIR"/.rand
    
    log_success "All certificates deleted"
}

################################################################################
# MAIN EXECUTION
################################################################################

main() {
    local command="${1:-generate}"
    
    print_header "MICROGRID mTLS CERTIFICATE GENERATOR"
    log_info "Script directory: $SCRIPT_DIR"
    
    case "$command" in
        generate)
            validate_dependencies || exit 1
            validate_config_file || exit $?
            
            create_ca_config
            generate_ca_cert
            
            while IFS= read -r agent || [ -n "$agent" ]; do
                agent=$(echo "$agent" | xargs)
                [[ -z "$agent" || "$agent" =~ ^# ]] && continue
                generate_agent_certs "$agent" || exit 3
            done < "$AGENTS_CONF"
            
            verify_all_certs || exit 3
            list_certs
            show_cert_info
            
            print_header "GENERATION COMPLETE"
            log_success "All certificates ready for deployment"
            log_info "Manifest saved to: $CERT_LOG"
            ;;
        
        validate)
            validate_config_file || exit $?
            verify_all_certs || exit 3
            ;;
        
        list)
            list_certs
            show_cert_info
            ;;
        
        reset)
            reset_all_certs
            ;;
        
        --help|-h)
            cat << 'HELP'
Usage: generate_certs.sh [command]

Commands:
  generate    Generate CA and agent certificates (default)
  validate    Verify all certificates are valid
  list        List all generated certificates with fingerprints
  reset       Delete all certificates and regenerate
  --help      Show this help message

Configuration:
  - Create agents.conf with one agent name per line
  - Agent names must be lowercase, alphanumeric with hyphens/underscores
  - Comments start with #

Example agents.conf:
  # Microgrid agents
  microgrid-agent
  control-agent
  researcher-agent

Exit codes:
  0 - Success
  1 - Dependency or file error
  2 - Configuration error
  3 - Certificate generation error

HELP
            exit 0
            ;;
        
        *)
            log_error "Unknown command: $command"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
}

main "$@"
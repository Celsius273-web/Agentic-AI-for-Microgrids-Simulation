"""
mTLS Client Helper

Provides reusable functions for making mTLS-authenticated requests to other agents.
Handles certificate loading, verification, error handling, and logging.
"""

import os
import ssl
import requests
import logging
from typing import Dict, Any, Optional, Tuple
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

logger = logging.getLogger(__name__)


class mTLSAdapter(HTTPAdapter):
    """HTTPAdapter that uses client certificates for mTLS."""
    
    def __init__(
        self,
        cert: Tuple[str, str],
        verify: str,
        cert_reqs: str = 'CERT_REQUIRED',
        **kwargs
    ):
        self.cert = cert
        self.verify = verify
        self.cert_reqs = cert_reqs
        super().__init__(**kwargs)
    
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context(
            cert_reqs=self.cert_reqs,
            ca_certs=self.verify
        )
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)


def create_mtls_session(
    client_cert: str,
    client_key: str,
    ca_cert: str,
    verify_peer: bool = True
) -> requests.Session:
    """
    Create a requests Session with mTLS enabled.
    
    Args:
        client_cert: Path to client certificate file
        client_key: Path to client private key file
        ca_cert: Path to CA certificate for verification
        verify_peer: Require valid peer certificate
        
    Returns:
        Configured requests.Session
        
    Raises:
        FileNotFoundError: If cert files don't exist
    """
    for path in [client_cert, client_key, ca_cert]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Certificate file not found: {path}")
    
    session = requests.Session()
    
    adapter = mTLSAdapter(
        cert=(client_cert, client_key),
        verify=ca_cert,
        cert_reqs='CERT_REQUIRED' if verify_peer else 'CERT_NONE'
    )
    session.mount('https://', adapter)
    
    logger.info(f"mTLS session created with certs: {client_cert}")
    
    return session


def make_mtls_request(
    url: str,
    method: str = "POST",
    client_cert: str = None,
    client_key: str = None,
    ca_cert: str = None,
    headers: Dict[str, str] = None,
    json_data: Dict[str, Any] = None,
    verify_peer: bool = True,
    timeout: int = 30
) -> requests.Response:
    """
    Make an mTLS-authenticated request to another agent.
    
    Args:
        url: Target URL (must be https://)
        method: HTTP method (GET, POST, etc.)
        client_cert: Path to client certificate
        client_key: Path to client private key
        ca_cert: Path to CA certificate
        headers: Additional headers (Authorization, etc.)
        json_data: JSON body for POST/PUT
        verify_peer: Require valid peer certificate
        timeout: Request timeout in seconds
        
    Returns:
        requests.Response object
        
    Raises:
        requests.exceptions.SSLError: Certificate verification failed
        requests.exceptions.ConnectionError: Cannot reach server
        requests.exceptions.Timeout: Request timed out
    """
    if not url.startswith("https://"):
        raise ValueError(f"mTLS requires HTTPS: {url}")
    
    try:
        session = create_mtls_session(
            client_cert=client_cert,
            client_key=client_key,
            ca_cert=ca_cert,
            verify_peer=verify_peer
        )
        
        response = session.request(
            method=method,
            url=url,
            headers=headers or {},
            json=json_data,
            timeout=timeout,
            verify=ca_cert
        )
        
        logger.info(f"{method} {url} -> {response.status_code}")
        
        return response
    
    except requests.exceptions.SSLError as e:
        logger.error(f"mTLS handshake failed for {url}: {e}")
        raise
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot connect to {url}: {e}")
        raise
    
    except requests.exceptions.Timeout:
        logger.error(f"Request to {url} timed out")
        raise


def agent_call(
    agent_name: str,
    port: int = 8443,
    endpoint: str = "/command",
    command: str = None,
    params: Dict[str, Any] = None,
    jwt_token: str = None,
    certs_dir: str = None,
    verify_peer: bool = True
) -> Dict[str, Any]:
    """
    High-level function to call another agent via mTLS.
    
    Usage:
        response = agent_call(
            agent_name="control-agent",
            command="get_status",
            params={"unit": "MW"},
            jwt_token=auth_token
        )
    
    Args:
        agent_name: Name of target agent
        port: HTTPS port (default 8443)
        endpoint: API endpoint (default /command)
        command: Command to execute
        params: Command parameters
        jwt_token: JWT Bearer token for authentication
        certs_dir: Directory with certificates (default /app/shared/certs)
        verify_peer: Require valid peer certificate
        
    Returns:
        Response JSON as dict
        
    Raises:
        requests.exceptions.RequestException: If call fails
    """
    if not certs_dir:
        certs_dir = os.environ.get("CERTS_DIR", "/app/shared/certs")
    
    my_agent_id = os.environ.get("AGENT_ID")
    if not my_agent_id:
        raise ValueError("AGENT_ID environment variable not set")
    
    client_cert = f"{certs_dir}/{my_agent_id}-client.crt"
    client_key = f"{certs_dir}/{my_agent_id}-client.key"
    ca_cert = f"{certs_dir}/ca.crt"
    
    url = f"https://{agent_name}:{port}{endpoint}"
    
    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    
    body = {}
    if command:
        body["command"] = command
    if params:
        body["params"] = params
    
    response = make_mtls_request(
        url=url,
        method="POST",
        client_cert=client_cert,
        client_key=client_key,
        ca_cert=ca_cert,
        headers=headers,
        json_data=body if body else None,
        verify_peer=verify_peer
    )
    
    response.raise_for_status()
    
    return response.json()
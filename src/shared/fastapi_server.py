import ssl
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def create_ssl_context(
    cert_file: str = None,
    key_file: str = None,
    ca_file: str = None,
    verify_peer: bool = True
) -> ssl.SSLContext:
    """ Create SSL context with mTLS enabled.
    Args:
        cert_file: Path to server certificate
        key_file: Path to server private key
        ca_file: Path to CA certificate for client verification
        verify_peer: Require valid client certificates
        
    Returns: Configured SSLContext for uvicorn
    """
    if not cert_file or not key_file:
        raise ValueError("cert_file and key_file are required")
    
    if not Path(cert_file).exists():
        raise FileNotFoundError(f"Server cert not found: {cert_file}")
    if not Path(key_file).exists():
        raise FileNotFoundError(f"Server key not found: {key_file}")
    
    if verify_peer and ca_file:
        if not Path(ca_file).exists():
            raise FileNotFoundError(f"CA cert not found: {ca_file}")
    
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(cert_file, key_file)
    
    if verify_peer and ca_file:
        context.load_verify_locations(ca_file)
        context.verify_mode = ssl.CERT_REQUIRED
        logger.info("mTLS enabled: Requiring valid client certificates")
    else:
        context.verify_mode = ssl.CERT_NONE
        logger.info("mTLS disabled: Accepting all clients")
    
    logger.info(f"SSL context initialized: cert={cert_file}")
    
    return context


def get_ssl_config(
    cert_file: str = None,
    key_file: str = None,
    ca_file: str = None,
    verify_peer: bool = True
) -> dict:
    """
    Get SSL configuration dict for uvicorn.
    
    Usage:
        from config import SERVER_CERT, SERVER_KEY, CA_CERT, VERIFY_PEER_CERTS
        ssl_config = get_ssl_config(SERVER_CERT, SERVER_KEY, CA_CERT, VERIFY_PEER_CERTS)
        uvicorn.run(app, **ssl_config)
    
    Args:
        cert_file: Path to server certificate
        key_file: Path to server private key
        ca_file: Path to CA certificate
        verify_peer: Require valid client certificates
        
    Returns:
        Dict with ssl_keyfile, ssl_certfile, ssl_keyfile_password
    """
    if not cert_file or not key_file:
        raise ValueError("cert_file and key_file required")
    
    # Validate files exist
    if not Path(cert_file).exists():
        raise FileNotFoundError(f"Certificate not found: {cert_file}")
    if not Path(key_file).exists():
        raise FileNotFoundError(f"Key not found: {key_file}")
    
    return {
        "ssl_keyfile": key_file,
        "ssl_certfile": cert_file,
        "ssl_keyfile_password": None,
    }


def log_cert_info(cert_file: str, key_file: str, ca_file: str = None):
    """Log certificate information on startup."""
    try:
        import subprocess
        result = subprocess.run(
            ["openssl", "x509", "-in", cert_file, "-noout", "-fingerprint", "-sha256"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            fingerprint = result.stdout.strip().split("=")[1]
            logger.info(f"Server certificate fingerprint: {fingerprint}")
    except Exception as e:
        logger.debug(f"Could not extract cert fingerprint: {e}")
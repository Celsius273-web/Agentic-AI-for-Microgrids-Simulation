#!/usr/bin/env python3
"""
Simple script to start the demo server on an available port.
"""

import socket
from demo_chat_simple import run_demo_server

def find_free_port(start_port=8000):
    """Find the first available port starting from start_port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    raise RuntimeError("No free ports found")

if __name__ == "__main__":
    try:
        port = find_free_port(8001)
        print(f"Starting demo server on port {port}")
        run_demo_server(port)
    except Exception as e:
        print(f"Failed to start server: {e}")
        print("Try manually: python3 demo_chat_simple.py")
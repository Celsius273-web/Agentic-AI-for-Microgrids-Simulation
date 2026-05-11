# MCP Grid State Server Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY ./mcp_servers/grid_state/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code and shared modules
COPY ./mcp_servers/grid_state/grid_state_server.py .
COPY ./shared ./shared

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash mcp && \
    chown -R mcp:mcp /app
USER mcp

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the server
CMD ["python", "grid_state_server.py"]
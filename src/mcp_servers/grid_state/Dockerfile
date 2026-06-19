# MCP Grid State Server Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY ./src/mcp_servers/grid_state/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src/mcp_servers/grid_state/grid_state_server.py .
COPY ./src/shared ./shared

RUN useradd --create-home --shell /bin/bash mcp && \
    chown -R mcp:mcp /app
USER mcp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "grid_state_server.py"]

FROM python:3.11-slim AS base

WORKDIR /app

# Install dependencies in a reusable base stage.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code once in base.
COPY . .


FROM base AS runtime

# Run as non-root in runtime image.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["sh", "-c", "python ${AGENT_FILE}"]


FROM runtime AS debug

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl openssl \
    && rm -rf /var/lib/apt/lists/*
USER appuser
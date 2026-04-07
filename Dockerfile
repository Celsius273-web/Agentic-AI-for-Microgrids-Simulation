# Shared Dockerfile - used by all agent containers
# Each agent folder mounts its own agent.py and the shared/ folder

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules and the specific agent code
COPY shared/ ./shared/
COPY agent.py .

EXPOSE 8000

CMD ["python", "agent.py"]

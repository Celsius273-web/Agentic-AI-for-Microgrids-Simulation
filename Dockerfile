FROM python:3.11-slim

WORKDIR /app

# STEP 1: Copy ONLY the requirements file first
COPY requirements.txt .

# STEP 2: Install libraries (This layer is now cached!)
# Docker will SKIP this step next time unless requirements.txt changes
RUN pip install --no-cache-dir -r requirements.txt


COPY shared/ ./shared/
COPY . .

CMD python ${AGENT_FILE}
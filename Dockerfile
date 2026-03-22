FROM python:3.12-slim

# Node.js is required by the claude-code CLI subprocess
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Pin claude-code CLI version — bump intentionally, never use @latest in production
RUN npm install -g @anthropic-ai/claude-code@2.1.63

WORKDIR /code

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /code
USER appuser

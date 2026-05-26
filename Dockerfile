FROM python:3.12-slim

# Security: run as non-root user
RUN groupadd -r agent && useradd -r -g agent -m agent

WORKDIR /app

# Install dependencies first (cache layer)
# Build context is the parent projects/ directory
COPY 04-agent-tool-calls-retries/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project 06 source as the token_cost_dashboard package
COPY 06-token-cost-budget-dashboard/src ./token_cost_dashboard

# Copy project 04 source
COPY 04-agent-tool-calls-retries/ .

# Create data/traces dirs owned by agent user
RUN mkdir -p /app/data /app/traces && chown -R agent:agent /app

USER agent

EXPOSE 8000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]

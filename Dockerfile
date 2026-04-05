FROM python:3.12-slim

WORKDIR /app

# Install system deps (curl is required by the docker-compose healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user — never run app containers as root in production
RUN addgroup --system appuser && adduser --system --ingroup appuser appuser

# Install Python deps first (better layer caching — only re-runs on requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY scripts/ ./scripts/
COPY pyproject.toml .

# Create data directory with correct ownership
RUN mkdir -p data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]

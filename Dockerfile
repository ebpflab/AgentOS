# AgentOS Dockerfile — multi-stage build

# Stage 1: Build React web UI
FROM node:20-alpine AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install
COPY web/ .
RUN npm run build

# Stage 2: Python backend + static UI
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application code
COPY src/ src/
COPY configs/ configs/
COPY migrations/ migrations/
COPY alembic.ini .

# Copy built web UI
COPY --from=web-build /web/dist /app/web/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "agentos", "start", "--host", "0.0.0.0", "--port", "8000"]

# Multi-stage build for optimized production image
# Stage 1: Builder
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements first for better caching
COPY requirements_minimal.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Build arguments
ARG BUILD_DATE
ARG VERSION

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Ensure scripts are executable
RUN chmod +x docker-entrypoint.sh run.sh run.py

# Create necessary directories
RUN mkdir -p /app/logs /app/output && \
    chown -R appuser:appuser /app/logs /app/output

# Set build metadata
LABEL build_date=$BUILD_DATE
LABEL version=$VERSION
LABEL service="email-agent"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/appuser/.local/bin:$PATH \
    SERVICE_NAME=email-agent \
    IS_CONTAINER=true \
    LOG_FORMAT=json

# Switch to non-root user
USER appuser

# Expose health check port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Entry point
ENTRYPOINT ["./docker-entrypoint.sh"]

# Default command - production entry point
CMD ["python", "main.py", "run"]
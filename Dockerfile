# ==============================================================================
# GridWise Production Dockerfile - BUP CSE Fest 2026
# Conforms to contest specifications (Section 02 & 03)
# ==============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

# Install minimal OS dependencies for network & build support
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated non-root application user and group (UID/GID 1001)
RUN groupadd -r -g 1001 appgroup && \
    useradd -r -u 1001 -g appgroup -d /app -s /sbin/nologin appuser

WORKDIR /app

# Install Python dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code with ownership assigned to non-root user
COPY --chown=appuser:appgroup app /app/app
COPY --chown=appuser:appgroup pytest.ini /app/
COPY --chown=appuser:appgroup tests /app/tests

# Switch to non-root user for enhanced security
USER appuser

# Expose API service port
EXPOSE 8000

# Built-in container health check
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Bind uvicorn to 0.0.0.0:8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

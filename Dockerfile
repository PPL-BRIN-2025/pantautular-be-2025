FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies and create non-root user
RUN apt-get update && apt-get --no-install-recommends install -y \
    bash \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser appuser

# Copy version file and set label
COPY VERSION .
LABEL org.opencontainers.image.version="$(cat VERSION)"
LABEL org.opencontainers.image.title="Pantau Tular Backend"
LABEL org.opencontainers.image.description="Django-based backend for the Pantau Tular application"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entrypoint and startup scripts
COPY entrypoint.sh .
COPY start.sh .
RUN chmod +x entrypoint.sh start.sh

# Copy project files selectively
COPY manage.py .
COPY VERSION .
COPY requirements.txt .
COPY pantau_tular/ pantau_tular/
COPY pt_backend/ pt_backend/
COPY hello/ hello/
COPY authentication/ authentication/
COPY admin_feature/ admin_feature/
COPY curator_feature/ curator_feature/
# COPY templates/ templates/
# COPY staticfiles/ staticfiles/  

# Create staticfiles directory and set proper ownership
RUN mkdir -p staticfiles && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Add health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f "http://localhost:${PORT:-8000}/health/" || exit 1

# Set entrypoint
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]

# Run application using start script
CMD ["/bin/bash", "/app/start.sh"] 

# Dockerfile for opsechat application
# This container runs the Flask application with email and chat features

FROM python:3.12-slim

# Install runtime dependencies needed by health checks.
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create an unprivileged runtime user.
RUN useradd --create-home --home-dir /home/opsechat --shell /usr/sbin/nologin opsechat

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
# Install dependencies with SSL verification (required for production)
# The fallback with --trusted-host is ONLY for CI/test environments with broken SSL chains
# In production deployments, this fallback should NEVER be triggered - if it is, investigate SSL issues
# Recommendation: For production, use pre-built wheels or a private PyPI mirror with proper certificates
RUN pip install --no-cache-dir -r requirements.txt || \
    (echo "ERROR: SSL verification failed. This fallback is for testing only." && \
     echo "For production, fix SSL certificates or use a private PyPI mirror." && \
     echo "Attempting installation with --trusted-host (NOT RECOMMENDED FOR PRODUCTION)..." && \
     pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt)

# Copy application source
COPY src/python/ ./src/python/
COPY src/web/ ./src/web/
COPY VERSION ./

# Keep Python source importable without extra environment setup.
ENV PYTHONPATH=/app/src/python

RUN chown -R opsechat:opsechat /app

# Expose Flask port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TOR_CONTROL_PORT=9051
ENV PYTHONDONTWRITEBYTECODE=1

USER opsechat

# Healthcheck: verify the Flask /health endpoint is responding.
# Flask binds immediately on startup (Tor setup runs in a background thread),
# so a 20 s start_period is sufficient.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=10 \
  CMD curl --fail --silent http://127.0.0.1:5000/health || exit 1

# Run the application
CMD ["python", "/app/src/python/runserver.py"]

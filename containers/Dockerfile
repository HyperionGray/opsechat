# Dockerfile for opsechat application
# This container runs the Flask application with email and chat features

FROM python:3.12-slim

# Install Tor and required system dependencies
RUN apt-get update && apt-get install -y \
    tor \
    curl \
    && rm -rf /var/lib/apt/lists/*

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

# Copy application code
# Key modules listed explicitly so tests can verify their presence;
# the wildcard ensures new helpers are also included.
COPY runserver.py app_factory.py utils.py monitoring.py rate_limiter.py ./
COPY email_system.py email_transport.py email_routes.py email_security_tools.py email_security_routes.py ./
COPY simple_chat_routes.py chat_routes.py review_routes.py landing_routes.py ./
COPY http_mail_routes.py http_mail_system.py burner_routes.py ./
COPY domain_manager.py domain_rotation_cli.py state_manager.py security_routes.py ./
COPY performance_utils.py ./
COPY *.py ./
COPY MANIFEST.in .
COPY VERSION .

# Copy static files and templates
COPY static/ static/
COPY templates/ templates/

# Expose Flask port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TOR_CONTROL_PORT=9051

# Health check -- matches the /health endpoint in monitoring.py
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:5000/health || exit 1

# Run the application
CMD ["python", "runserver.py"]

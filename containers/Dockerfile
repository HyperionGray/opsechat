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
# Key modules are listed explicitly so the build fails fast if one is missing;
# the trailing wildcard picks up any new helpers added later.
COPY runserver.py app_factory.py utils.py rate_limiter.py monitoring.py \
     email_system.py email_transport.py email_routes.py email_security_tools.py \
     email_security_routes.py http_mail_routes.py http_mail_system.py \
     simple_chat_routes.py chat_routes.py review_routes.py \
     burner_routes.py security_routes.py landing_routes.py \
     domain_manager.py domain_rotation_cli.py state_manager.py \
     performance_utils.py review_performance.py \
     amazon_q_integration.py aws_integration.py \
     ./
# Catch any remaining .py helpers not listed above
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

# Healthcheck: verify the Flask /health endpoint is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:5000/health || exit 1

# Run the application
CMD ["python", "runserver.py"]

# Dockerfile for opsechat application
# This container runs the Flask application with email and chat features

FROM python:3.12-slim

# Install runtime dependencies needed by health checks.
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a stable shared group for reading the Tor control cookie.
RUN groupadd --gid 2000 tor-cookie

# Create an unprivileged runtime user.
RUN useradd --create-home --home-dir /home/opsechat --shell /usr/sbin/nologin opsechat \
    && usermod --append --groups tor-cookie opsechat

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
COPY app_factory.py ./
COPY burner_routes.py ./
COPY chat_routes.py ./
COPY domain_manager.py ./
COPY email_routes.py ./
COPY email_security_routes.py ./
COPY email_security_tools.py ./
COPY email_system.py ./
COPY email_transport.py ./
COPY http_mail_routes.py ./
COPY http_mail_system.py ./
COPY landing_routes.py ./
COPY monitoring.py ./
COPY mvp_routes.py ./
COPY openpgp_room_policy.py ./
COPY closed_roster_room.py ./
COPY rate_limiter.py ./
COPY review_routes.py ./
COPY runserver.py ./
COPY runserver_refactored.py ./
COPY security_routes.py ./
COPY simple_chat_routes.py ./
COPY state_manager.py ./
COPY tor_transport.py ./
COPY utils.py ./
COPY MANIFEST.in .
COPY VERSION .

# Copy static files and templates
COPY static/ static/
COPY templates/ templates/

RUN chown -R opsechat:opsechat /app

# Expose Flask port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TOR_CONTROL_PORT=9051
ENV PYTHONDONTWRITEBYTECODE=1

USER opsechat

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=10 \
  CMD curl --fail --silent http://127.0.0.1:5000/health || exit 1

# Run the application
CMD ["python", "runserver_refactored.py"]

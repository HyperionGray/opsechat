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
COPY runserver.py .
COPY email_system.py .
COPY email_security_tools.py .
COPY email_transport.py .
COPY domain_manager.py .
COPY review_routes.py .
COPY setup.py .
COPY MANIFEST.in .

# Copy static files and templates
COPY static/ static/
COPY templates/ templates/

# Expose Flask port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TOR_CONTROL_PORT=9051

# Run the application
CMD ["python", "runserver.py"]

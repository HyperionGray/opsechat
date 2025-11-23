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
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt || \
    pip install --no-cache-dir -r requirements.txt

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

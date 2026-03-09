# syntax=docker/dockerfile:1.4

# Use Python 3.12 as required by the application
FROM python:3.12-slim

# Install system dependencies for building packages and curl for health checks
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (only used as a build backend for mihcsme-py, not as a package manager)
COPY --from=ghcr.io/astral-sh/uv:0.6.0 /uv /bin/uv

WORKDIR /app

# Copy and install all requirements
# Build context is the examples/marimo/ directory
COPY --link requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --link marimo_omero_app.py .

EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8080/health || exit 1

# Create a non-root user and switch to it
RUN useradd -m app_user
USER app_user

# Run the marimo app
# --no-sandbox: skip marimo's inline dependency sandbox and use the pre-installed packages
CMD ["marimo", "run", "marimo_omero_app.py", "--no-sandbox", "--host", "0.0.0.0", "-p", "8080"]

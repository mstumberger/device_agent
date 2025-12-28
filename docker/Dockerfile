FROM python:3.13-slim

LABEL maintainer="CyberGrid"
LABEL description="CyberGrid Device Agent - IoT power measurement simulator"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ /app/src/
# Note: config.yaml and device.json provided via volume mounts in docker-compose.yml

# Add src to PYTHONPATH for module imports
ENV PYTHONPATH=/app/src

# Create a non-root user for running the application
RUN useradd -m -u 1000 cybergrid && \
    chown -R cybergrid:cybergrid /app

USER cybergrid

# Set the entrypoint
ENTRYPOINT ["python", "-m", "cybergrid.main"]

# Default command
CMD ["run"]
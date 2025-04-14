FROM python:3.9-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy just requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final stage
FROM python:3.9-slim

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY *.py /app/

# Define environment variables
ENV PYTHONUNBUFFERED=1

# Run as non-root user for better security
RUN adduser --disabled-password --gecos "" muppet
USER muppet

# Expose the WebSocket port
EXPOSE 8765

CMD ["python", "server.py"]
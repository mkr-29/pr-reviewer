FROM python:3.12-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TZ=Asia/Kolkata

# Install system dependencies (tzdata for accurate timezone scheduling, ca-certificates for TLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and tests
COPY app/ ./app/
COPY tests/ ./tests/
COPY main.py pytest.ini ./

# Create data directory for persistent state
RUN mkdir -p /app/data

# Default command runs the daemon (Daily 8:00 PM scheduler)
CMD ["python3", "main.py"]

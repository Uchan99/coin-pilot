FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
# Copy shared libs like config or scripts if needed
COPY scripts/ ./scripts/

# Set env
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Command
CMD ["python", "src/collector/main.py"]

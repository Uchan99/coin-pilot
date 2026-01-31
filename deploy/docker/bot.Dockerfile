FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements-bot.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-bot.txt

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Set env
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Command
CMD ["python", "src/bot/main.py"]

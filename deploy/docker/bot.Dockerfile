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

# Non-root 실행을 위한 전용 사용자 생성
RUN addgroup --system app && adduser --system --ingroup app app

# Copy source code
COPY --chown=app:app src/ ./src/
COPY --chown=app:app scripts/ ./scripts/
COPY --chown=app:app config/ ./config/

# Set env
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER app

# Command
CMD ["python", "src/bot/main.py"]

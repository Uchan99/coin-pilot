FROM python:3.12-slim

WORKDIR /app

# 최소 런타임 패키지만 설치해 공격면과 이미지 크기를 줄입니다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-discord-bot.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-discord-bot.txt

RUN addgroup --system app && adduser --system --ingroup app app

COPY --chown=app:app src/ ./src/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER app

CMD ["python", "src/discord_bot/main.py"]


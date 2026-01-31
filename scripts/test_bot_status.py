#!/usr/bin/env python
"""
Bot Brain 테스트용 스크립트
Redis에 테스트 데이터를 삽입하여 대시보드 Bot Brain 섹션이 정상 작동하는지 확인합니다.

Usage:
    kubectl port-forward -n coin-pilot-ns service/redis 6379:6379 &
    python scripts/test_bot_status.py
"""
import redis
import json
import os
from datetime import datetime, timezone

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# 테스트할 심볼 목록 (봇에서 사용하는 형식과 일치해야 함)
TEST_SYMBOLS = ["KRW-BTC", "KRW-ETH"]

def insert_test_status():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        print(f"[+] Redis connected: {REDIS_HOST}:{REDIS_PORT}")
    except redis.ConnectionError as e:
        print(f"[!] Redis connection failed: {e}")
        print("[*] Did you run: kubectl port-forward -n coin-pilot-ns service/redis 6379:6379 ?")
        return False

    for symbol in TEST_SYMBOLS:
        status_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "current_price": 95000000 if "BTC" in symbol else 3500000,
            "indicators": {
                "rsi": 45.2,
                "bb_upper": 96000000 if "BTC" in symbol else 3600000,
                "bb_lower": 94000000 if "BTC" in symbol else 3400000,
                "ma_200": 93000000 if "BTC" in symbol else 3300000
            },
            "position": {
                "has_position": False,
                "avg_price": None,
                "quantity": None
            },
            "action": "HOLD",
            "reason": f"[TEST] RSI(45.2) > 30, 과매도 아님. 대기 중..."
        }

        key = f"bot:status:{symbol}"
        r.set(key, json.dumps(status_data), ex=300)  # TTL 5분
        print(f"[+] Inserted: {key}")

    # 확인
    print("\n[*] Verifying inserted keys:")
    for key in r.keys("bot:status:*"):
        data = r.get(key)
        parsed = json.loads(data)
        print(f"  - {key}: action={parsed['action']}, reason={parsed['reason'][:30]}...")

    return True

if __name__ == "__main__":
    print("=== Bot Brain Test Data Inserter ===\n")
    success = insert_test_status()
    if success:
        print("\n[+] Done! Now check the dashboard at http://localhost:8501")
        print("[*] Note: Data will expire in 5 minutes (TTL=300)")
    else:
        print("\n[!] Failed to insert test data")

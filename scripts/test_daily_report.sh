#!/bin/bash
# Daily Report 수동 테스트 스크립트

echo "🧪 DailyReporter 수동 실행 테스트"
echo "======================================"

# .env 파일 로드 (환경변수 export)
if [ -f .env ]; then
    echo "[-] Loading .env file..."
    set -a  # 자동으로 export
    source .env
    set +a
else
    echo "[!] Warning: .env file not found"
fi

# Python 스크립트로 DailyReporter 직접 호출
python3 << 'EOF'
import asyncio
import sys
import os

# 프로젝트 루트를 Python Path에 추가
sys.path.insert(0, os.getcwd())

async def test_daily_reporter():
    from src.agents.daily_reporter import DailyReporter
    from src.common.db import get_db_session
    
    print("[Test] DailyReporter 초기화...")
    reporter = DailyReporter(get_db_session)
    
    print("[Test] Daily Report 생성 및 전송 시작...")
    await reporter.generate_and_send()
    
    print("[Test] ✅ 완료! Discord를 확인해주세요.")

# 비동기 함수 실행
asyncio.run(test_daily_reporter())
EOF

echo ""
echo "✅ 테스트 완료. Discord 채널을 확인해주세요!"


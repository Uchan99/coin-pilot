import os
import httpx
import asyncio
from typing import Dict, Any
from datetime import datetime, timezone

class NotificationManager:
    """
    n8n 워크플로우 트리거를 위한 알림 관리자.
    재시도 로직 및 보안 헤더(X-Webhook-Secret)를 포함합니다.
    """
    def __init__(self):
        # K8s Service DNS 사용: http://n8n:5678
        self.base_url = os.getenv("N8N_URL", "http://n8n:5678")
        self.secret = os.getenv("N8N_WEBHOOK_SECRET", "")
        self.timeout = 5.0
        self.max_retries = 3

    async def send_webhook(self, endpoint: str, data: Dict[str, Any]) -> bool:
        """
        n8n 웹훅 엔드포인트로 데이터를 비동기 전송합니다.
        
        Args:
            endpoint: 웹훅 경로 (예: /webhook/trade)
            data: 전송할 JSON 데이터
        """
        if not self.secret:
            print("[!] N8N_WEBHOOK_SECRET is not set. Skipping notification.")
            return False

        url = f"{self.base_url}{endpoint}"
        headers = {
            "X-Webhook-Secret": self.secret,
            "Content-Type": "application/json"
        }
        
        # 타임스탬프 추가 (클라이언트 기준)
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(url, json=data, headers=headers)
                    if response.status_code == 200:
                        return True
                    else:
                        print(f"[!] Notification failed (Status {response.status_code}): {response.text}")
                except Exception as e:
                    print(f"[!] Notification attempt {attempt + 1} error: {e}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt) # Exponential backoff
            
        print(f"[!] Notification failed after {self.max_retries} attempts.")
        return False

# 싱글톤 인스턴스
notifier = NotificationManager()

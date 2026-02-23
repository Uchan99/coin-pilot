import os
import httpx
import asyncio
from typing import Dict, Any, List
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
        self.base_urls = self._build_base_urls()

    def _build_base_urls(self) -> List[str]:
        """
        웹훅 대상 URL 후보를 구성합니다.
        컨테이너 내부에서 localhost 오설정이 자주 발생하므로 서비스 DNS를 fallback으로 둡니다.
        """
        raw = (self.base_url or "").strip() or "http://n8n:5678"
        urls: List[str] = [raw]

        # 컨테이너 환경에서 localhost는 자기 자신을 가리켜 n8n 연결에 실패할 수 있습니다.
        if "localhost" in raw or "127.0.0.1" in raw:
            urls.append("http://n8n:5678")

        # 로컬 개발 환경에서 n8n 포트포워딩을 쓰는 경우를 대비한 역방향 fallback
        if raw != "http://localhost:5678":
            urls.append("http://localhost:5678")

        # 순서 유지 + 중복 제거
        seen = set()
        deduped: List[str] = []
        for u in urls:
            if u in seen:
                continue
            seen.add(u)
            deduped.append(u)
        return deduped

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

        headers = {
            "X-Webhook-Secret": self.secret,
            "Content-Type": "application/json"
        }
        
        # 타임스탬프 추가 (클라이언트 기준)
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for base in self.base_urls:
                url = f"{base}{endpoint}"
                for attempt in range(self.max_retries):
                    try:
                        response = await client.post(url, json=data, headers=headers)
                        if response.status_code == 200:
                            return True
                        print(
                            f"[!] Notification failed (Status {response.status_code}) "
                            f"url={url}: {response.text}"
                        )
                    except Exception as e:
                        print(
                            f"[!] Notification attempt {attempt + 1} error "
                            f"url={url}: {e}"
                        )

                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt) # Exponential backoff

        print(
            f"[!] Notification failed after retries. endpoint={endpoint}, "
            f"base_urls={self.base_urls}"
        )
        return False

# 싱글톤 인스턴스
notifier = NotificationManager()

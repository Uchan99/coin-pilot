import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.common.notification import notifier

async def test_notification():
    print("[*] Testing n8n Webhook Connection...")
    print(f"[*] Target URL: {notifier.base_url}/webhook/trade")
    
    test_data = {
        "symbol": "KRW-BTC-TEST",
        "side": "BUY",
        "price": 12345678,
        "quantity": 0.1,
        "strategy": "TestStrategy",
        "executed_at": "2026-01-29T01:15:00Z"
    }
    
    success = await notifier.send_webhook("/webhook/trade", test_data)
    
    if success:
        print("[+] Test Webhook sent successfully! (n8n responded with 200)")
    else:
        print("[-] Test Webhook failed. Check n8n logs or network settings.")

if __name__ == "__main__":
    if not os.getenv("N8N_WEBHOOK_SECRET"):
        # Local test fallback if run outside K8s without env
        os.environ["N8N_WEBHOOK_SECRET"] = "coinpilot-n8n-secret-2026"
        os.environ["N8N_URL"] = "http://localhost:5678" # If port-forwarded
        print("[!] Using local fallback settings for N8N_URL/SECRET")

    asyncio.run(test_notification())

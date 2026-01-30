import asyncio
from src.agents.router import process_chat

async def test_agents():
    test_queries = [
        # SQL Agent Tests
        "현재 잔고 알려줘", 
        "비트코인 가격 얼마야?",
        
        # RAG Agent Tests
        "이 프로젝트의 아키텍처는 뭐야?",
        "손절 규칙이 어떻게 돼?",
        
        # General Chat Test
        "안녕, 넌 누구니?"
    ]
    
    print("--- Starting Agent Verification ---")
    
    for query in test_queries:
        print(f"\n[QUERY] {query}")
        try:
            response = await process_chat(query)
            print(f"[RESPONSE] {response}")
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(test_agents())

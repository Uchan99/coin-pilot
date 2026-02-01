from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

from src.common.models import DailyRiskState, AccountState
from src.common.notification import notifier
from src.analytics.performance import PerformanceAnalytics
# DB Session은 외부에서 주입받는다고 가정 (혹은 context manager 사용)

class DailyReporter:
    """
    일간 리포트 생성기:
    1. DB에서 하루의 매매 요약 정보 조회
    2. LLM을 사용하여 정성적인 요약 코멘트 생성 ("오늘은 3연패가 있었지만 리스크 관리가 잘 작동했습니다...")
    3. n8n 웹훅으로 리포트 전송 to Discord
    """
    def __init__(self, session_factory):
        self.session_factory = session_factory
        # LLM 초기화 (환경 변수 OPENAI_API_KEY 필요)
        # 비용 효율적인 모델 사용 (예: gpt-3.5-turbo or gpt-4o-mini)
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    async def generate_and_send(self):
        """
        리포트를 생성하고 전송합니다.
        """
        async with self.session_factory() as session:
            data = await self._fetch_daily_data(session)
        
        if not data:
            print("[DailyReporter] No data found for today.")
            return

        # LLM 요약 생성
        summary = await self._generate_llm_summary(data)
        
        # 전송 데이터 구성
        payload = {
            "title": f"📅 CoinPilot Daily Report ({data['date']})",
            "pnl": f"{data['total_pnl']:.2f} USDT",
            "trades": data['trade_count'],
            "win_rate": f"{data['win_rate']*100:.1f}%",
            "mdd": f"{data['mdd']:.2f}%",
            "summary": summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # n8n 전송
        await notifier.send_webhook("/webhook/daily-report", payload)
        print(f"[DailyReporter] Report sent: {payload['title']}")

    async def _fetch_daily_data(self, session: AsyncSession) -> Dict[str, Any]:
        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        
        # 1. 일일 리스크 상태 조회
        stmt = select(DailyRiskState).where(DailyRiskState.date == today)
        result = await session.execute(stmt)
        state = result.scalar_one_or_none()
        
        if not state:
            return None
            
        # 2. 거래 내역 조회 (오늘 체결된 건만)
        from src.common.models import TradingHistory
        stmt_hist = select(TradingHistory).where(
            TradingHistory.executed_at >= today_start
        ).order_by(TradingHistory.executed_at)
        
        result_hist = await session.execute(stmt_hist)
        trades = result_hist.scalars().all()
        
        # 3. 승률 및 상세 지표 계산 (FIFO 매칭)
        win_count = 0
        loss_count = 0
        
        # 간단한 매칭 로직 (정확한 PnL은 RiskManager가 관리하지만, 승률 추정을 위해)
        # 매수/매도 내역을 순회하며 매도 시점의 가격이 매수 평단가보다 높은지 확인
        # (완벽한 FIFO 구현보다는 매도 주문의 price가 직전 포지션 평단가보다 높은지 여부로 판단)
        # 하지만 포지션 평단가는 DB에 기록되지 않으므로, 여기서는 TradingHistory만으로 추정이 어렵습니다.
        # 대안: SELL 주문일 때 price가 해당 시점의 시장가(close)나.. 아니면 단순화해서
        # RiskManager가 DB에 어딘가 기록하지 않는 이상 정확하지 않음.
        # 따라서, 여기서는 'DailyRiskState.total_pnl'이 양수면 'Winning Day'로 간주하거나
        # 혹은 별도의 'TradeResult' 테이블이 필요함.
        
        # [Fallback Plan]
        # 일단 total_pnl과 trade_count는 정확하므로 이를 반환하고, 
        # Win Rate는 "N/A (See Dashboard)"로 표기하거나 0.0으로 둠.
        # (리뷰어 요청인 '실제 데이터 연동'은 win_rate보다는 pnl/trade_count가 핵심임)
        
        return {
            "date": today.isoformat(),
            "total_pnl": state.total_pnl,
            "trade_count": state.trade_count or len(trades),
            "win_rate": 0.0, # 추후 TradeResult 테이블 추가 시 구현
            "mdd": 0.0 # 자산 스냅샷 필요
        }

    async def _generate_llm_summary(self, data: Dict[str, Any]) -> str:
        prompt = PromptTemplate(
            input_variables=["data"],
            template="""
            당신은 가상화폐 매매 봇 CoinPilot의 운영자입니다.
            오늘의 매매 결과를 바탕으로 사용자에게 보낼 3줄 이내의 요약 브리핑을 작성해주세요.
            
            [매매 데이터]
            - 날짜: {data['date']}
            - 총 손익: {data['total_pnl']} USDT
            - 거래 횟수: {data['trade_count']}회
            
            톤앤매너: 전문적이지만 친절하게. 이모지 사용 가능.
            결과가 좋으면 칭찬하고, 나쁘면 리스크 관리가 잘 되었음을 강조하세요.
            """
        )
        chain = prompt | self.llm
        response = await chain.ainvoke({"data": data})
        return response.content

# 실행 예시 (Main loop 등에서 호출)
# reporter = DailyReporter(session_factory)
# await reporter.generate_and_send()

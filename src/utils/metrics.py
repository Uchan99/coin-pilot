import prometheus_client
from prometheus_client import Gauge, Counter, Histogram
import threading

class MetricsExporter:
    """
    CoinPilot 시스템 메트릭을 관리하는 Singleton 클래스입니다.
    Prometheus Client 라이브러리를 사용하여 메트릭을 정의하고 업데이트합니다.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MetricsExporter, cls).__new__(cls)
                    cls._instance._initialize_metrics()
        return cls._instance

    def _initialize_metrics(self):
        """
        메트릭을 초기화하고 등록합니다.
        """
        # --- Business Metrics ---
        # 현재 활성 포지션 수 (Gauge: 늘어나거나 줄어들 수 있음)
        self.active_positions = Gauge(
            'coinpilot_active_positions', 
            'Number of current active positions'
        )
        
        # 누적 손익 (Gauge: 양수/음수 가능)
        self.total_pnl = Gauge(
            'coinpilot_total_pnl', 
            'Total cumulative PnL (Profit and Loss)'
        )
        
        # 총 거래 횟수 (Counter: 계속 증가함)
        self.trade_count = Counter(
            'coinpilot_trade_count_total', 
            'Total number of trades executed'
        )

        # AI 분석 요청 횟수 (Counter)
        self.ai_requests = Counter(
            'coinpilot_ai_requests_total',
            'Total number of AI analysis requests'
        )

        # AI pre-filter로 스킵된 횟수 (Counter)
        self.ai_prefilter_skips = Counter(
            'coinpilot_ai_prefilter_skips_total',
            'Total number of signals skipped by AI pre-filter'
        )

        # AI 입력 컨텍스트 캔들 길이 (Histogram)
        self.ai_context_candles = Histogram(
            'coinpilot_ai_context_candles',
            'Number of hourly candles provided to AI market context',
            buckets=[0, 4, 8, 12, 16, 20, 24, 30]
        )

        # 현재 변동성 지수 (Gauge: 변동성 모델에서 업데이트)
        self.volatility_index = Gauge(
            'coinpilot_volatility_index',
            'Current market volatility index (from GARCH model)'
        )

        # --- System Metrics ---
        # 거래소 API 응답 지연 (Histogram)
        self.api_latency = Histogram(
            'coinpilot_api_latency_seconds', 
            'Exchange API response latency in seconds',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0] # 0.1초 ~ 5초 구간
        )

    def start_server(self, port=8000):
        """
        Prometheus 메트릭 서버를 시작합니다.
        """
        try:
            prometheus_client.start_http_server(port)
            print(f"[Metrics] Prometheus metrics server started on port {port}")
        except Exception as e:
            print(f"[Metrics] Failed to start metrics server: {e}")

# Global Instance
metrics = MetricsExporter()

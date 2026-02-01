import pytest
import time
from src.utils.metrics import metrics, MetricsExporter

class TestMetricsExporter:
    def test_singleton(self):
        """
        MetricsExporter가 Singleton으로 동작하는지 확인합니다.
        """
        instance1 = MetricsExporter()
        instance2 = MetricsExporter()
        assert instance1 is instance2
        assert metrics is instance1

    def test_metrics_existence(self):
        """
        주요 메트릭 객체들이 정상적으로 초기화되었는지 확인합니다.
        """
        assert metrics.active_positions is not None
        assert metrics.total_pnl is not None
        assert metrics.trade_count is not None
        assert metrics.volatility_index is not None
        assert metrics.api_latency is not None

    def test_metric_updates(self):
        """
        메트릭 값 업데이트가 정상적으로 반영되는지 확인합니다.
        주의: Prometheus Client의 내부 값 확인은 _value 속성(비공개)을 통해야 하므로
        공식적으로는 inc(), set() 호출 시 에러가 없는지 확인하는 것이 주 목적입니다.
        """
        # Gauge: Set & Inc/Dec
        metrics.active_positions.set(5)
        assert metrics.active_positions._value.get() == 5.0
        
        metrics.active_positions.dec()
        assert metrics.active_positions._value.get() == 4.0

        # Counter: Inc
        initial_count = metrics.trade_count._value.get()
        metrics.trade_count.inc()
        assert metrics.trade_count._value.get() == initial_count + 1.0

        # Histogram: Observe
        metrics.api_latency.observe(0.5)
        # Histogram 값 검증은 복잡하므로 호출 성공 여부만 확인 (sum 값 확인)
        assert metrics.api_latency._sum.get() > 0

    def test_concurrency(self):
        """
        멀티스레드 환경에서 Singleton 인스턴스 생성이 안전한지 확인합니다.
        """
        instances = []
        import threading
        
        def get_instance():
            instances.append(MetricsExporter())

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 모든 인스턴스가 동일해야 함
        first_instance = instances[0]
        for inst in instances[1:]:
            assert inst is first_instance

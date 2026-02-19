from datetime import datetime, timedelta, timezone

from src.analytics.post_exit_tracker import _get_base_time, _is_complete
from src.common.models import TradingHistory


def test_is_complete_true_when_all_windows_present():
    data = {
        "1h": {"price": 1},
        "4h": {"price": 1},
        "12h": {"price": 1},
        "24h": {"price": 1},
    }
    assert _is_complete(data) is True


def test_is_complete_false_when_missing_window():
    data = {
        "1h": {"price": 1},
        "4h": {"price": 1},
        "12h": {"price": 1},
    }
    assert _is_complete(data) is False


def test_get_base_time_prefers_executed_at():
    created = datetime.now(timezone.utc)
    executed = created + timedelta(minutes=1)
    order = TradingHistory(created_at=created, executed_at=executed)
    assert _get_base_time(order) == executed


def test_get_base_time_falls_back_to_created_at():
    created = datetime.now(timezone.utc)
    order = TradingHistory(created_at=created, executed_at=None)
    assert _get_base_time(order) == created

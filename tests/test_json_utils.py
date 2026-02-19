from decimal import Decimal
from datetime import datetime, timezone
import numpy as np

from src.common.json_utils import to_builtin, dumps_json


def test_to_builtin_converts_numpy_and_decimal():
    payload = {
        "ok": np.bool_(True),
        "score": np.float64(1.5),
        "count": np.int64(3),
        "amount": Decimal("12.34"),
    }
    converted = to_builtin(payload)
    assert converted["ok"] is True
    assert converted["score"] == 1.5
    assert converted["count"] == 3
    assert converted["amount"] == 12.34


def test_dumps_json_handles_nested_special_types():
    payload = {
        "t": datetime(2026, 2, 19, 0, 0, tzinfo=timezone.utc),
        "arr": [np.bool_(False), Decimal("1.0")],
    }
    dumped = dumps_json(payload)
    assert '"t"' in dumped
    assert '"arr"' in dumped

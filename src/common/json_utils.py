from datetime import date, datetime
from decimal import Decimal
from typing import Any
import json


def to_builtin(value: Any) -> Any:
    """
    DB/Redis JSON 직렬화를 위해 numpy/pandas/decimal 타입을 Python 기본형으로 변환.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): to_builtin(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_builtin(v) for v in value]

    # numpy scalar / pandas scalar 대응 (np.bool_, np.float64, etc.)
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return to_builtin(item())
        except Exception:
            pass

    # pandas Timestamp 등 to_pydatetime 지원 타입
    to_pydt = getattr(value, "to_pydatetime", None)
    if callable(to_pydt):
        try:
            return to_pydt().isoformat()
        except Exception:
            pass

    return str(value)


def dumps_json(value: Any) -> str:
    return json.dumps(to_builtin(value), ensure_ascii=False)

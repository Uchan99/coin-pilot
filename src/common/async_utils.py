import asyncio
import threading
from typing import Any, Awaitable, Callable, Dict, TypeVar

T = TypeVar("T")


def run_async_safely(async_fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
    """
    동기 컨텍스트(Streamlit 등)에서 async 함수를 안전하게 실행합니다.

    - 실행 중인 이벤트 루프가 없으면 `asyncio.run`을 사용
    - 이미 루프가 돌고 있으면 별도 스레드에서 독립 루프로 실행

    이 방식은 Streamlit 재실행/멀티페이지 환경에서 발생할 수 있는
    "event loop already running" 충돌을 회피하기 위한 공용 래퍼입니다.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_fn(*args, **kwargs))

    result_box: Dict[str, Any] = {}

    def _thread_runner() -> None:
        try:
            result_box["result"] = asyncio.run(async_fn(*args, **kwargs))
        except Exception as exc:  # pragma: no cover - 예외 전달 브랜치
            result_box["error"] = exc

    worker = threading.Thread(target=_thread_runner, daemon=True)
    worker.start()
    worker.join()

    if "error" in result_box:
        raise result_box["error"]

    return result_box["result"]

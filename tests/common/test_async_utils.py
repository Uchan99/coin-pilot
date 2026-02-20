import pytest

from src.common.async_utils import run_async_safely


async def _double(value: int) -> int:
    return value * 2


def test_run_async_safely_without_running_loop():
    assert run_async_safely(_double, 3) == 6


@pytest.mark.asyncio
async def test_run_async_safely_with_running_loop():
    # asyncio 루프가 이미 실행 중인 컨텍스트에서도 안전하게 실행되어야 합니다.
    assert run_async_safely(_double, 4) == 8

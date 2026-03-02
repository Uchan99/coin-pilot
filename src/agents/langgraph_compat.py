from __future__ import annotations

from typing import Any


try:
    # LangGraph 1.x/0.6+ 공통 기본 경로
    from langgraph.graph import END, START, StateGraph  # type: ignore
except Exception:  # pragma: no cover - import fallback
    # 구버전 호환: START가 없는 경우가 있어 None으로 처리한다.
    from langgraph.graph import END, StateGraph  # type: ignore

    START = None  # type: ignore

try:
    # 구버전/신버전 모두에서 우선 시도
    from langgraph.graph.message import add_messages  # type: ignore
except Exception:  # pragma: no cover - import fallback
    def add_messages(left: list[Any], right: list[Any]) -> list[Any]:
        """add_messages 심볼이 사라진 버전을 위한 최소 병합 fallback."""
        merged: list[Any] = []
        merged.extend(left or [])
        merged.extend(right or [])
        return merged


def set_graph_entry(workflow: Any, node_name: str) -> None:
    """
    LangGraph 버전별 entry 설정 차이를 흡수합니다.

    - 신버전: START -> node edge 연결
    - 구버전: set_entry_point(node)
    """
    if START is not None and hasattr(workflow, "add_edge"):
        workflow.add_edge(START, node_name)
        return

    if hasattr(workflow, "set_entry_point"):
        workflow.set_entry_point(node_name)
        return

    raise RuntimeError("Unsupported LangGraph workflow entry API")

import time
import uuid
from typing import Dict, List

import streamlit as st

from src.agents.router import process_chat_sync

CHAT_HISTORY_KEY = "assistant_chat_history"
CHAT_CACHE_KEY = "assistant_chat_cache"
CHAT_LAST_REQUEST_TS_KEY = "assistant_chat_last_request_ts"
CHAT_SESSION_ID_KEY = "assistant_chat_session_id"
CHAT_COOLDOWN_SECONDS = 2.0


def get_shared_history() -> List[Dict[str, str]]:
    if CHAT_HISTORY_KEY not in st.session_state:
        st.session_state[CHAT_HISTORY_KEY] = [
            {
                "role": "assistant",
                "content": "안녕하세요. CoinPilot AI 트레이딩 비서입니다. 시장/전략/리스크 질문을 입력해주세요.",
            }
        ]
    return st.session_state[CHAT_HISTORY_KEY]


def _get_cache() -> Dict[str, str]:
    if CHAT_CACHE_KEY not in st.session_state:
        st.session_state[CHAT_CACHE_KEY] = {}
    return st.session_state[CHAT_CACHE_KEY]


def append_message(role: str, content: str) -> None:
    history = get_shared_history()
    history.append({"role": role, "content": content})


def _get_chat_session_id() -> str:
    if CHAT_SESSION_ID_KEY not in st.session_state:
        st.session_state[CHAT_SESSION_ID_KEY] = uuid.uuid4().hex
    return str(st.session_state[CHAT_SESSION_ID_KEY])


def ask_assistant(prompt: str) -> str:
    """
    공통 질의 실행기.
    - 세션 단위 짧은 쿨다운
    - 동일 질의 캐시
    """
    now = time.time()
    last_ts = float(st.session_state.get(CHAT_LAST_REQUEST_TS_KEY, 0.0))
    if now - last_ts < CHAT_COOLDOWN_SECONDS:
        return f"요청 간격이 너무 짧습니다. {CHAT_COOLDOWN_SECONDS:.0f}초 후 다시 시도해주세요."

    st.session_state[CHAT_LAST_REQUEST_TS_KEY] = now
    cache = _get_cache()
    normalized = prompt.strip()
    if normalized in cache:
        return cache[normalized]

    response = process_chat_sync(normalized, session_id=_get_chat_session_id())
    cache[normalized] = response
    return response


def render_chat_history(max_messages: int = 12, height: int = 320) -> None:
    history = get_shared_history()
    with st.container(height=height):
        for msg in history[-max_messages:]:
            role = "Assistant" if msg["role"] == "assistant" else "User"
            st.markdown(f"**{role}**")
            st.write(msg["content"])


def render_floating_chat() -> None:
    """
    우하단 고정 Popover 형태로 모든 페이지에서 호출 가능한 Assistant UI.
    """
    if not hasattr(st, "popover"):
        with st.sidebar.expander("AI Assistant", expanded=False):
            render_chat_history(max_messages=8, height=260)
            with st.form("floating_chat_form_fallback", clear_on_submit=True):
                prompt = st.text_input("질문", placeholder="예: 지금 BTC 시장 어떻게 봐?")
                submitted = st.form_submit_button("전송", use_container_width=True)

            if submitted and prompt and prompt.strip():
                append_message("user", prompt)
                with st.spinner("분석 중..."):
                    response = ask_assistant(prompt)
                append_message("assistant", response)
                st.rerun()
        return

    st.markdown(
        """
        <style>
        div[data-testid="stPopover"] {
            position: fixed;
            right: 1.5rem;
            bottom: 1.5rem;
            z-index: 1000;
        }
        div[data-testid="stPopover"] button {
            border-radius: 999px;
            padding: 0.5rem 0.9rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.popover("AI Assistant", help="시장/전략/리스크 질문"):
        st.caption("분석/진단 답변은 참고용이며 자동 주문을 실행하지 않습니다.")
        render_chat_history(max_messages=8, height=260)

        with st.form("floating_chat_form", clear_on_submit=True):
            prompt = st.text_input("질문", placeholder="예: 지금 BTC 시장 어떻게 봐?")
            submitted = st.form_submit_button("전송", use_container_width=True)

        if submitted and prompt and prompt.strip():
            append_message("user", prompt)
            with st.spinner("분석 중..."):
                response = ask_assistant(prompt)
            append_message("assistant", response)
            st.rerun()

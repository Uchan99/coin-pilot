import hmac
import os

import streamlit as st


AUTH_SESSION_KEY = "dashboard_authenticated"
AUTH_ERROR_KEY = "dashboard_auth_error"


def enforce_dashboard_access() -> None:
    """
    대시보드 접근 비밀번호 가드.
    - 운영 환경에서 DASHBOARD_ACCESS_PASSWORD를 필수로 주입하면 무단 접근을 차단할 수 있다.
    - 비밀번호 미설정 시에는 경고만 표시하고 기존 동작을 유지한다.
    """
    required_password = os.getenv("DASHBOARD_ACCESS_PASSWORD", "").strip()
    if not required_password:
        st.warning(
            "보안 경고: DASHBOARD_ACCESS_PASSWORD가 설정되지 않아 인증 없이 대시보드가 열립니다."
        )
        return

    if st.session_state.get(AUTH_SESSION_KEY):
        return

    st.title("CoinPilot Dashboard Login")
    st.caption("운영 대시보드 접근을 위해 비밀번호를 입력하세요.")

    with st.form("dashboard_login_form", clear_on_submit=True):
        password_input = st.text_input("Access Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if hmac.compare_digest(password_input, required_password):
            st.session_state[AUTH_SESSION_KEY] = True
            st.session_state.pop(AUTH_ERROR_KEY, None)
            st.rerun()
        st.session_state[AUTH_ERROR_KEY] = "비밀번호가 올바르지 않습니다."

    if st.session_state.get(AUTH_ERROR_KEY):
        st.error(st.session_state[AUTH_ERROR_KEY])

    st.stop()

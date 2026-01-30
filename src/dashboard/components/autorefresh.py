import streamlit as st
import time

def auto_refresh_component():
    """
    사이드바에 자동 새로고침 설정을 추가하는 컴포넌트

    Note: Pure Streamlit 방식은 한계가 있어, interval마다 정확히 갱신되지 않을 수 있음.
    사용자가 페이지와 상호작용하거나, interval 경과 후 다음 rerun 시점에 갱신됨.
    정밀한 자동 갱신이 필요하면 streamlit-autorefresh 라이브러리 사용 권장.
    """
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = False

    if "refresh_interval" not in st.session_state:
        st.session_state.refresh_interval = 30

    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = time.time()

    st.sidebar.markdown("### 🔄 Auto Refresh")

    enable_refresh = st.sidebar.checkbox("Enable Auto Refresh", value=st.session_state.auto_refresh)

    if enable_refresh:
        interval = st.sidebar.slider("Interval (seconds)", 10, 300, st.session_state.refresh_interval)
        st.session_state.auto_refresh = True
        st.session_state.refresh_interval = interval

        time_since_last = time.time() - st.session_state.last_refresh
        remaining = max(0, int(interval - time_since_last))

        # 남은 시간 표시
        st.sidebar.caption(f"Next refresh in: {remaining}s")

        # interval 경과 시에만 rerun
        if time_since_last >= interval:
            st.session_state.last_refresh = time.time()
            st.rerun()
        # else: 아무것도 하지 않음 (매초 rerun 방지)
        # 사용자 상호작용 시 자연스럽게 시간 체크됨

    else:
        st.session_state.auto_refresh = False
        st.session_state.last_refresh = time.time()  # 비활성화 시 타이머 리셋

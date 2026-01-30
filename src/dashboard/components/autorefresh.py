import streamlit as st
from streamlit_autorefresh import st_autorefresh

def auto_refresh_component():
    """
    streamlit-autorefresh 라이브러리를 사용한 진정한 자동 새로고침 컴포넌트.
    브라우저 단에서 타이머가 동작하여, 사용자가 가만히 있어도 자동으로 리로드됩니다.
    """
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = False
    
    if "refresh_interval" not in st.session_state:
        st.session_state.refresh_interval = 30000 # ms 단위 (기본 30초)

    st.sidebar.markdown("### 🔄 Auto Refresh")
    
    enable_refresh = st.sidebar.checkbox("Enable Auto Refresh", value=st.session_state.auto_refresh)
    
    if enable_refresh:
        # 슬라이더는 초 단위로 받지만, 라이브러리는 ms 단위 필요
        interval_sec = st.sidebar.slider("Interval (seconds)", 10, 300, int(st.session_state.refresh_interval / 1000))
        interval_ms = interval_sec * 1000
        
        st.session_state.auto_refresh = True
        st.session_state.refresh_interval = interval_ms
        
        # 실제 자동 갱신 트리거 생성
        # key를 설정하여 컴포넌트 고유성 유지
        count = st_autorefresh(interval=interval_ms, limit=None, key="dashboard_autorefresh")
        
        # 시각적 피드백 (선택사항)
        st.sidebar.caption(f"Refreshed: {count} times")
            
    else:
        st.session_state.auto_refresh = False

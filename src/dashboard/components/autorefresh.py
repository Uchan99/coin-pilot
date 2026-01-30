import streamlit as st
import time

def auto_refresh_component():
    """
    사이드바에 자동 새로고침 설정을 추가하는 컴포넌트
    """
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = False
    
    if "refresh_interval" not in st.session_state:
        st.session_state.refresh_interval = 30

    st.sidebar.markdown("### 🔄 Auto Refresh")
    
    enable_refresh = st.sidebar.checkbox("Enable Auto Refresh", value=st.session_state.auto_refresh)
    
    if enable_refresh:
        interval = st.sidebar.slider("Interval (seconds)", 10, 300, st.session_state.refresh_interval)
        st.session_state.auto_refresh = True
        st.session_state.refresh_interval = interval
        
        # 메인 컨텐츠 영역 우측 상단에 카운트다운 표시 (선택사항)
        # st.empty()를 사용하여 카운트다운을 보여주는 것은 복잡하므로,
        # 단순하게 sleep 후 rerun 하는 방식을 사용.
        # 주의: sleep은 블로킹이므로 UI 반응성을 해칠 수 있음.
        # streamlit_autorefresh 라이브러리를 쓰면 좋지만, 외부 의존성 최소화를 위해
        # st.empty() + time.time() 체크 방식을 권장.
        
        time_since_last = time.time() - st.session_state.get('last_refresh', 0)
        
        if time_since_last > interval:
            st.session_state.last_refresh = time.time()
            st.rerun()
        else:
            # 블로킹 없는 재실행을 위해 trick 사용 (잠시 대기 후 리런이 아니라, 다음 프레임에 체크하도록)
            # 하지만 Streamlit 특성상 loop가 없으면 멈춤.
            # 가장 확실한 방법: time.sleep(1) 후 rerun (반응성 저하 감수)
            time.sleep(1) 
            st.rerun()
            
    else:
        st.session_state.auto_refresh = False

import streamlit as st
from src.dashboard.utils.db_connector import check_db_connection

# 1. 페이지 설정 (가장 먼저 실행되어야 함)
st.set_page_config(
    page_title="CoinPilot Dashboard",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 사이드바 공통 설정
st.sidebar.title("CoinPilot v3.0")
st.sidebar.caption("AI-Powered Crypto Trading System")
st.sidebar.markdown("---")
# Auto Refresh
from src.dashboard.components.autorefresh import auto_refresh_component
auto_refresh_component()

# 시스템 상태 확인 (간단한 Ping)
if st.sidebar.button("시스템 상태 확인"):
    db_status = check_db_connection()
    status_icon = "🟢" if db_status else "🔴"
    status_text = "Connected" if db_status else "Disconnected"
    st.sidebar.info(f"DB Status: {status_icon} {status_text}")
    
st.sidebar.markdown("### Navigation")
st.sidebar.info("왼쪽 메뉴에서 페이지를 선택하세요.")

# 3. 메인 콘텐츠 (Landing Page)
st.title("🪙 CoinPilot Control Center")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    ### 👋 환영합니다!
    이 대시보드는 **CoinPilot 봇의 두뇌**를 시각화하는 도구입니다.
    
    #### 주요 기능
    - **📊 Overview**: 자산 현황과 수익률을 한눈에 확인
    - **📈 Market**: 실시간 차트와 봇의 매매 시그널 분석
    - **🛡️ Risk Monitor**: 리스크 한도 관리 상태 (Week 6 New!)
    - **📜 History**: 투명한 거래 내역 조회
    - **⚙️ System**: 인프라 상태 및 로그 확인
    """)

with col2:
    st.info("""
    #### 🚀 Quick Start
    1. 왼쪽 사이드바에서 **1_Overview**를 클릭하여 현재 자산을 확인하세요.
    2. 봇이 잘 돌고 있는지 **3_Risk**에서 리스크 상태를 점검하세요.
    
    **Tip**: 데이터 로딩이 안 된다면 `port-forward`가 켜져 있는지 확인하세요!
    """)
    st.code("kubectl port-forward -n coin-pilot-ns service/db 5432:5432", language="bash")

st.markdown("---")
st.caption("Developed by Antigravity & User | Week 6 Dashboard Polish")

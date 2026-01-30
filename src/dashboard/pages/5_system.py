import streamlit as st
import pandas as pd
import redis
import os
import requests
from src.dashboard.utils.db_connector import get_data_as_dataframe, get_engine
from sqlalchemy import text

st.title("⚙️ System Health")

# 1. Component Status Check
st.subheader("Component Connectivity")
col1, col2, col3 = st.columns(3)

# 1-1. DB Check
db_status = False
try:
    df_db = get_data_as_dataframe("SELECT 1")
    if not df_db.empty:
        db_status = True
except:
    pass

with col1:
    icon = "🟢" if db_status else "🔴"
    st.metric("PostgreSQL (TimescaleDB)", f"{icon} {'Connected' if db_status else 'Error'}")

# 1-2. Redis Check
redis_status = False
try:
    # Redis 연결 테스트 (동기식)
    # common.db.get_redis_client는 비동기이므로, 여기서 직접 redis-py 사용
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=1)
    if r.ping():
        redis_status = True
except:
    pass

with col2:
    icon = "🟢" if redis_status else "🔴"
    st.metric("Redis Cache", f"{icon} {'Connected' if redis_status else 'Error'}")

# 1-3. n8n Check
n8n_status = False
try:
    # n8n 헬스체크 (내부 서비스 URL 또는 로컬 포트포워딩 URL)
    # 로컬 개발 환경이므로 localhost:5678 사용
    resp = requests.get("http://localhost:5678/healthz", timeout=1)
    if resp.status_code == 200:
        n8n_status = True
except:
    pass

with col3:
    icon = "🟢" if n8n_status else "🔴"
    st.metric("n8n Workflow", f"{icon} {'Active' if n8n_status else 'Error'}")

st.markdown("---")

# 2. Notification Logs (System Logs)
st.subheader("Recent System Logs")

# system_logs 테이블이 없으면 생성되었는지 확인 필요. 
# 없으면 trading_history에서 에러 로그를 찾거나 제외.
# 여기서는 'system_logs'가 있다고 가정 (Week 6 Plan 2.2.D)
# models.py에는 system_logs가 안 보였음 -> (수정) risk_audit 사용 또는 직접 생성 필요.
# models.py에 SystemLogs 없음. -> 'system_logs' 테이블이 실제 DB에 있는지 확인 필요하나, 
# 안전하게 RiskAudit 테이블을 보여주거나, 구현되지 않았다면 안내 메시지.
# Notification Log를 보여주고 싶다면 notification_logs 테이블이 있어야 함.

# 대안: Notification 내역을 DB에 저장하지 않고 Discord로만 쏘는 경우 로그가 없을 수 있음.
# 현재 Week 5 결과물에 Notification Log DB 저장 로직이 있었는지 확인 -> Notification.py는 DB 저장 안 함.
# 따라서 여기서는 'Risk Audit' 로그를 다시 보여주거나, 추후 구현 안내.

st.info("Notification Log 저장은 Phase 3+에서 구현 예정입니다. 현재는 최근 Risk Audit 로그를 표시합니다.")

audit_df = get_data_as_dataframe("""
    SELECT timestamp, violation_type, description 
    FROM risk_audit 
    ORDER BY timestamp DESC 
    LIMIT 10
""")

if not audit_df.empty:
    st.dataframe(audit_df, use_container_width=True)
else:
    st.write("No critical system events found.")

# 3. Manual Refresh
if st.button("Refresh Status"):
    st.rerun()

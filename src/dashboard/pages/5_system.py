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
    # n8n 헬스체크
    # K8s 환경: N8N_SERVICE_HOST/PORT 자동 주입됨, 로컬 환경: localhost 사용
    # 주의: N8N_PORT는 K8s가 "tcp://IP:PORT" 형식으로 주입하므로 사용 불가
    N8N_HOST = os.getenv("N8N_SERVICE_HOST", "localhost")  # K8s 자동 주입 변수
    N8N_PORT = os.getenv("N8N_SERVICE_PORT", "5678")       # K8s 자동 주입 변수
    resp = requests.get(f"http://{N8N_HOST}:{N8N_PORT}/healthz", timeout=2)
    if resp.status_code == 200:
        n8n_status = True
except:
    pass

with col3:
    icon = "🟢" if n8n_status else "🔴"
    st.metric("n8n Workflow", f"{icon} {'Active' if n8n_status else 'Error'}")

st.markdown("---")

# 2. Recent AI Agent Decisions
st.subheader("Recent AI Agent Decisions")

decisions_df = get_data_as_dataframe("""
    SELECT created_at, symbol, decision, reasoning, confidence, model_used
    FROM agent_decisions
    ORDER BY created_at DESC
    LIMIT 10
""")

if not decisions_df.empty:
    st.dataframe(decisions_df, use_container_width=True)
else:
    st.write("No agent decisions recorded yet.")

st.markdown("---")

# 3. Risk Audit Logs
st.subheader("Risk Audit Logs")

audit_df = get_data_as_dataframe("""
    SELECT timestamp, violation_type, description
    FROM risk_audit
    ORDER BY timestamp DESC
    LIMIT 10
""")

if not audit_df.empty:
    st.dataframe(audit_df, use_container_width=True)
else:
    st.info("No risk violations recorded. This is good!")

# 3. Manual Refresh
if st.button("Refresh Status"):
    st.rerun()

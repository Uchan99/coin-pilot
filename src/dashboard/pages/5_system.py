import streamlit as st
from src.dashboard.components.auth_guard import enforce_dashboard_access
import pandas as pd
import redis
import os
import requests
from src.dashboard.utils.db_connector import get_data_as_dataframe, get_engine
from sqlalchemy import text
from src.dashboard.components.floating_chat import render_floating_chat

enforce_dashboard_access()

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
# Compose/K8s/로컬 실행 환경이 섞여도 점검이 깨지지 않도록
# 우선순위 기반으로 헬스체크 대상 URL 후보를 순차 시도한다.
n8n_candidates = []
n8n_url = os.getenv("N8N_URL")
if n8n_url:
    n8n_candidates.append(n8n_url.rstrip("/"))

n8n_service_host = os.getenv("N8N_SERVICE_HOST")
n8n_service_port = os.getenv("N8N_SERVICE_PORT", "5678")
if n8n_service_host:
    n8n_candidates.append(f"http://{n8n_service_host}:{n8n_service_port}")

# Compose 기본 서비스명(n8n)과 로컬 개발(localhost) fallback
n8n_candidates.extend(["http://n8n:5678", "http://localhost:5678"])

seen = set()
for base_url in n8n_candidates:
    if base_url in seen:
        continue
    seen.add(base_url)
    try:
        resp = requests.get(f"{base_url}/healthz", timeout=3)
        if resp.status_code == 200:
            n8n_status = True
            break
    except Exception:
        continue

with col3:
    icon = "🟢" if n8n_status else "🔴"
    st.metric("n8n Workflow", f"{icon} {'Active' if n8n_status else 'Error'}")

st.markdown("---")

# 2. Recent AI Agent Decisions
st.subheader("Recent AI Agent Decisions")

agent_decisions_exists_df = get_data_as_dataframe(
    "SELECT to_regclass('public.agent_decisions') AS tbl"
)
agent_decisions_exists = (
    not agent_decisions_exists_df.empty
    and agent_decisions_exists_df.iloc[0]["tbl"] is not None
)

if agent_decisions_exists:
    decisions_df = get_data_as_dataframe("""
        SELECT created_at + interval '9 hours' as created_at, symbol, decision, reasoning, confidence, model_used
        FROM agent_decisions
        ORDER BY created_at DESC
        LIMIT 10
    """)
else:
    decisions_df = pd.DataFrame()

if not decisions_df.empty:
    st.dataframe(decisions_df, use_container_width=True)
else:
    if agent_decisions_exists:
        st.write("No agent decisions recorded yet.")
    else:
        st.info("agent_decisions 테이블이 아직 생성되지 않았습니다. 마이그레이션 적용이 필요합니다.")

st.markdown("---")

# 3. Risk Audit Logs
st.subheader("Risk Audit Logs")

audit_df = get_data_as_dataframe("""
    SELECT timestamp + interval '9 hours' as timestamp, violation_type, description
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

render_floating_chat()

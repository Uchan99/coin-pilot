import streamlit as st

from src.dashboard.components.floating_chat import append_message, ask_assistant, get_shared_history

st.set_page_config(page_title="AI Chatbot | CoinPilot", page_icon="💬", layout="wide")

st.title("💬 AI Trading Assistant")
st.markdown(
    """
**CoinPilot AI**에게 물어보세요.
- 💰 **포트폴리오 조회**: "현재 잔고/포지션 상태 알려줘"
- 📈 **시장 해석**: "현재 비트코인 시장 어떻게 봐?"
- 🧭 **전략 리뷰**: "최근 매매 기준으로 장단점 분석해줘"
- 🛡️ **리스크 진단**: "지금 레짐에서 주의할 위험이 뭐야?"
"""
)

if st.button("대화 초기화"):
    st.session_state.pop("assistant_chat_history", None)
    st.session_state.pop("assistant_chat_cache", None)
    st.session_state.pop("assistant_chat_session_id", None)
    st.rerun()

history = get_shared_history()
for message in history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("질문을 입력하세요..."):
    st.chat_message("user").markdown(prompt)
    append_message("user", prompt)

    with st.chat_message("assistant"):
        with st.spinner("AI가 분석 중입니다..."):
            response = ask_assistant(prompt)
        st.markdown(response)

    append_message("assistant", response)

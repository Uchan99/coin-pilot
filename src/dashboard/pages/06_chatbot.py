import streamlit as st
import asyncio
from src.agents.router import process_chat

st.set_page_config(
    page_title="AI Chatbot | CoinPilot",
    page_icon="💬",
    layout="wide"
)

st.title("💬 AI Financial Assistant")
st.markdown("""
**CoinPilot AI**에게 물어보세요!  
- 💰 **자산 조회**: "현재 잔고 얼마야?", "비트코인 가격 알려줘"
- 📚 **지식 검색**: "이 프로젝트의 아키텍처는?", "손절 규칙이 뭐야?"
""")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("질문을 입력하세요..."):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        with st.spinner("AI가 생각 중입니다..."):
            try:
                # Run async agent loop in sync streamlit environment
                response = asyncio.run(process_chat(prompt))
                full_response = response
                message_placeholder.markdown(full_response)
            except Exception as e:
                full_response = f"⚠️ 에러가 발생했습니다: {str(e)}"
                message_placeholder.error(full_response)
        
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})

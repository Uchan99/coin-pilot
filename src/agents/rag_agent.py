from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from src.common.db import get_sync_db_url
from src.agents.config import LLM_MODEL, EMBEDDING_MODEL, VECTOR_TABLE_NAME
import os

# RAG Prompt
RAG_SYSTEM_PROMPT = """You are an assistant for question-answering tasks related to the 'CoinPilot' project.
Use the following pieces of retrieved context to answer the question.
If the context does not contain the answer, say that you don't know based on the provided documents.
Use three sentences maximum and keep the answer concise.

Context:
{context}
"""

def get_llm():
    """
    RAG에서 답변 생성(Generation)을 담당할 LLM을 초기화합니다.
    """
    if "claude" in LLM_MODEL:
        return ChatAnthropic(
            model=LLM_MODEL, 
            temperature=0, 
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)

def get_retriever():
    """
    PGVector 기반의 문서 검색기(Retriever)를 생성합니다.
    1. 동기식 DB URL을 사용하여 PostgreSQL 연결을 설정합니다.
    2. HuggingFace 임베딩 모델을 로드합니다.
    3. LangChain PGVector 객체를 생성하여 DB의 벡터 테이블과 연결합니다.
    """
    # PGVector는 psycopg2(동기 드라이버)를 사용하여 DB에 연결합니다.
    connection_string = get_sync_db_url()
    
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    
    # PGVector 저장소 초기화: 기존에 inges_docs.py로 저장된 테이블('langchain_pg_embedding' 등)을 사용합니다.
    # collection_name 내부적으로 'langchain_pg_collection' 테이블의 name 컬럼과 매핑됩니다.
    vectorstore = PGVector(
        connection_string=connection_string,
        embedding_function=embeddings,
        collection_name=VECTOR_TABLE_NAME,
    )
    
    # 검색기(Retriever)로 변환 (k=3: 유사도가 높은 상위 3개 문서 청크만 검색)
    return vectorstore.as_retriever(search_kwargs={"k": 3})

async def run_rag_agent(query: str) -> str:
    """
    RAG 에이전트 실행 진입점입니다.
    1. Retriever로 관련 문서를 검색(Retrieval)합니다.
    2. LLM이 검색된 문서를 컨텍스트로 사용하여 답변을 생성(Generation)합니다.
    """
    try:
        llm = get_llm()
        retriever = get_retriever()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SYSTEM_PROMPT),
            ("human", "{input}"),
        ])
        
        # Stuff Documents Chain: 검색된 모든 문서를 프롬프트에 'stuff'(채워넣기)하는 체인
        question_answer_chain = create_stuff_documents_chain(llm, prompt)
        
        # Retrieval Chain: 검색 + 답변 생성을 연결하는 최종 체인
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)
        
        # 체인 실행 (비동기)
        result = await rag_chain.ainvoke({"input": query})
        return result["answer"]
        
    except Exception as e:
        return f"Error executing RAG Agent: {str(e)}"

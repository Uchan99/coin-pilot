from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.vectorstores import PGVector
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import OpenAIEmbeddings

from src.agents.config import EMBEDDING_MODEL, VECTOR_TABLE_NAME
from src.agents.factory import get_chat_llm
from src.common.db import get_sync_db_url

# RAG Prompt (한국어)
RAG_SYSTEM_PROMPT = """당신은 'CoinPilot' 프로젝트에 대한 질문에 답변하는 어시스턴트입니다.

**중요: 반드시 한국어로만 답변하세요.**

아래 검색된 문서를 참고하여 질문에 답변하세요.
문서에 답변이 없으면 "제공된 문서에서 관련 정보를 찾을 수 없습니다."라고 답하세요.
최대 3문장으로 간결하게 답변하세요.

검색된 문서:
{context}
"""


def get_retriever():
    """
    PGVector 기반의 문서 검색기(Retriever)를 생성합니다.
    1. 동기식 DB URL을 사용하여 PostgreSQL 연결을 설정합니다.
    2. 임베딩 모델을 로드합니다.
    3. LangChain PGVector 객체를 생성하여 DB의 벡터 테이블과 연결합니다.
    """
    # PGVector는 psycopg2(동기 드라이버)를 사용하여 DB에 연결합니다.
    connection_string = get_sync_db_url()

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    # PGVector 저장소 초기화: 기존 ingest_docs.py로 저장된 컬렉션을 재사용합니다.
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
        llm = get_chat_llm(temperature=0)
        retriever = get_retriever()

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RAG_SYSTEM_PROMPT),
                ("human", "{input}"),
            ]
        )

        # Stuff Documents Chain: 검색된 모든 문서를 프롬프트에 'stuff'(채워넣기)하는 체인
        question_answer_chain = create_stuff_documents_chain(llm, prompt)

        # Retrieval Chain: 검색 + 답변 생성을 연결하는 최종 체인
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)

        # 체인 실행 (비동기)
        result = await rag_chain.ainvoke({"input": query})
        return result["answer"]

    except Exception as exc:
        return f"RAG Agent 실행 중 오류가 발생했습니다: {str(exc)}"

import types

import pytest

from src.agents import rag_agent


class _Doc:
    def __init__(self, page_content):
        self.page_content = page_content


class _AsyncRetriever:
    async def ainvoke(self, query):
        assert query == "질문"
        return [_Doc("문서A"), _Doc(""), _Doc(None), _Doc("문서B")]


class _SyncRetriever:
    def get_relevant_documents(self, query):
        assert query == "질문"
        return [_Doc("동기문서")]


class _LLMWithContent:
    def __init__(self):
        self.last_messages = None

    async def ainvoke(self, messages):
        self.last_messages = messages
        return types.SimpleNamespace(content="정상 응답")


class _LLMWithPlainText:
    async def ainvoke(self, _messages):
        return "plain-text"


class _LLMError:
    async def ainvoke(self, _messages):
        raise RuntimeError("llm fail")


@pytest.mark.asyncio
async def test_run_rag_agent_uses_async_retriever_and_builds_context(monkeypatch):
    llm = _LLMWithContent()
    monkeypatch.setattr(rag_agent, "get_chat_llm", lambda temperature=0: llm)
    monkeypatch.setattr(rag_agent, "get_retriever", lambda: _AsyncRetriever())

    result = await rag_agent.run_rag_agent("질문")

    assert result == "정상 응답"
    contents = [getattr(msg, "content", "") for msg in llm.last_messages]
    merged = "\n".join(str(c) for c in contents)
    assert "문서A" in merged
    assert "문서B" in merged
    assert "질문" in merged


@pytest.mark.asyncio
async def test_run_rag_agent_falls_back_to_sync_retriever(monkeypatch):
    monkeypatch.setattr(rag_agent, "get_chat_llm", lambda temperature=0: _LLMWithPlainText())
    monkeypatch.setattr(rag_agent, "get_retriever", lambda: _SyncRetriever())

    result = await rag_agent.run_rag_agent("질문")

    assert result == "plain-text"


@pytest.mark.asyncio
async def test_run_rag_agent_returns_error_message_on_llm_exception(monkeypatch):
    monkeypatch.setattr(rag_agent, "get_chat_llm", lambda temperature=0: _LLMError())
    monkeypatch.setattr(rag_agent, "get_retriever", lambda: _AsyncRetriever())

    result = await rag_agent.run_rag_agent("질문")

    assert result.startswith("RAG Agent 실행 중 오류가 발생했습니다:")

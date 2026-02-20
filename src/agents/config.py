import os

from src.agents.factory import get_default_model_name

# LLM Configuration
# 기본 경로는 factory 정책(LLM_MODE)과 동일하게 맞춥니다.
LLM_MODEL = os.getenv("LLM_MODEL", get_default_model_name())

# Embedding Configuration
# Local: HuggingFace (Free), Remote: OpenAI (Higher Quality/Cost)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Vector DB Configuration
# Use existing Postgres connection with pgvector extension
VECTOR_TABLE_NAME = "document_embeddings"

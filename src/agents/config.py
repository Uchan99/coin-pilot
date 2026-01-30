import os

# LLM Configuration
# Dev: Haiku (Cost-effective), Prod: Sonnet (High Performance)
LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-haiku-20240307")

# Embedding Configuration
# Local: HuggingFace (Free), Remote: OpenAI (Higher Quality/Cost)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Vector DB Configuration
# Use existing Postgres connection with pgvector extension
VECTOR_TABLE_NAME = "document_embeddings"

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- NOTE: LangChain PGVector uses 'langchain_pg_collection' and 'langchain_pg_embedding' tables by default.
-- The python library creates these tables automatically if they don't exist.
-- However, for reference, here is the schema it uses.
-- We can pre-create them or just let the library handle it.

-- Removing manual creation of 'document_embeddings' as it was unused.
-- Instead, we ensure the vector extension is enabled.

-- Approved DDL for OpenAI Embeddings
CREATE TABLE IF NOT EXISTS document_embeddings (
    id SERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector (1536), -- text-embedding-3-small dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Note: The LangChain PGVector library may use its own tables (langchain_pg_embedding/collection).
-- This table is created as per the project specification for direct SQL access or future custom implementation.
CREATE INDEX ON document_embeddings USING ivfflat (embedding vector_cosine_ops);
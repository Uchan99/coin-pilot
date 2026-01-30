-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- NOTE: LangChain PGVector uses 'langchain_pg_collection' and 'langchain_pg_embedding' tables by default.
-- The python library creates these tables automatically if they don't exist.
-- However, for reference, here is the schema it uses.
-- We can pre-create them or just let the library handle it.

-- Removing manual creation of 'document_embeddings' as it was unused.
-- Instead, we ensure the vector extension is enabled.

-- Optional: If we wanted to manually manage the schema, it looks like this:
-- CREATE TABLE IF NOT EXISTS langchain_pg_collection (
--     uuid UUID PRIMARY KEY,
--     name VARCHAR,
--     cmetadata JSON
-- );
-- CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
--     uuid UUID PRIMARY KEY,
--     collection_id UUID REFERENCES langchain_pg_collection(uuid),
--     embedding vector(384),
--     document VARCHAR,
--     cmetadata JSON,
--     custom_id VARCHAR
-- );
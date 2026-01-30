import os
import glob
from typing import List
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import PGVector
from src.agents.config import EMBEDDING_MODEL, VECTOR_TABLE_NAME
from src.common.db import DATABASE_URL, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME

# Load environment variables (db.py already loads .env)

def get_connection_string():
    # Construct synchronous connection string for PGVector (uses psycopg2)
    # DATABASE_URL in db.py might be async (postgresql+asyncpg) or None
    # We construct a standard postgresql:// url
    return f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def load_docs(directory: str) -> List:
    documents = []
    # Recursively find .md files
    files = glob.glob(os.path.join(directory, "**/*.md"), recursive=True)
    
    print(f"Found {len(files)} markdown files in {directory}")
    
    for file_path in files:
        try:
            # Using basic text loader if Unstructured is not available or too heavy
            # Manual loading to keep metadata clean
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Simple metadata
            metadata = {"source": file_path, "filename": os.path.basename(file_path)}
            
            from langchain_core.documents import Document
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)
            print(f"Loaded: {file_path}")
        except Exception as e:
            print(f"Failed to load {file_path}: {e}")
            
    return documents

def ingest_docs():
    print("--- Starting Document Ingestion ---")
    
    # 1. Load Documents
    docs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    if not os.path.exists(docs_path):
        print(f"Docs directory not found: {docs_path}")
        return

    raw_documents = load_docs(docs_path)
    if not raw_documents:
        print("No documents found.")
        return

    # 2. Split Text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    docs = text_splitter.split_documents(raw_documents)
    print(f"Split {len(raw_documents)} documents into {len(docs)} chunks.")

    # 3. Initialize Embeddings
    print(f"Initializing Embeddings: {EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # 4. Ingest to PGVector
    connection_string = get_connection_string()
    print(f"Connecting to DB: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    # Drop existing collection if needed? For now we just add.
    # To avoid duplicates, one might want to delete existing embeddings for these files.
    # But PGVector implementation is additive.
    
    db = PGVector.from_documents(
        embedding=embeddings,
        documents=docs,
        collection_name=VECTOR_TABLE_NAME,
        connection_string=connection_string,
        # WARNING: This deletes all existing embeddings in the collection!
        # Use with caution in production. For dev/re-indexing, this ensures freshness.
        pre_delete_collection=True, 
    )
    
    print("--- Ingestion Completed Successfully ---")

if __name__ == "__main__":
    ingest_docs()

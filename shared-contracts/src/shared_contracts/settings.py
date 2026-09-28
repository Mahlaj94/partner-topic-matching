from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class AppSettings(BaseSettings):
    # Embeddings & reranker model names
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    reranker_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")

    # Chroma / storage
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_collection: str = "competence_chunks"

    # LLM provider (generic)
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file='.env', env_prefix='CM_', extra='ignore')

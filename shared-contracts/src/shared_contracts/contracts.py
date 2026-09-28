from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl, confloat
from .models import Topic, Label, Evidence


# --- Retrieval ---
class RetrieveRequest(BaseModel):
    partner_id: str
    topic: Topic
    k_dense: int = 50
    k_bm25: int = 50


class RetrieveItem(BaseModel):
    text: str
    url: HttpUrl
    title: Optional[str] = None
    score_dense: Optional[float] = None
    score_bm25: Optional[float] = None


# --- Reranking ---
class RerankRequest(BaseModel):
    topic_query: str
    candidates: List[RetrieveItem]
    top_k: int = 10


class RerankedItem(BaseModel):
    text: str
    url: HttpUrl
    title: Optional[str] = None
    rerank_score: float


# --- Verification (LLM) ---
class VerifyRequest(BaseModel):
    partner_id: str
    topic: Topic
    snippets: List[RerankedItem]
    k: int = 10


class VerifyResponse(BaseModel):
    partner_id: str
    topic_id: str
    label: Label
    confidence: confloat(ge=0.0, le=1.0)
    evidence: List[Evidence]


# --- Fusion / Scoring ---
class ScoreRequest(BaseModel):
    cosine_max: float | None = None
    cosine_mean_top5: float | None = None
    rerank_mean_top5: float | None = None
    llm_confidence: float | None = None


class ScoreResponse(BaseModel):
    score: float
    label: Label

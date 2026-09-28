from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os

import chromadb
from chromadb.config import Settings
from sentence_transformers import CrossEncoder, SentenceTransformer

from shared_contracts import (
    RetrieveRequest, RetrieveItem,
    RerankRequest, RerankedItem,
    Topic
)

app = FastAPI(title="Hybrid Retrieval + Reranker API", version="0.1.0")

CHROMA_PATH = os.environ.get("CHROMA_PATH", ".chroma")
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "competence_chunks")
RERANKER_MODEL_NAME = os.environ.get("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
WHOOSH_INDEX_PATH = os.environ.get("WHOOSH_INDEX", None)

_client = None
_collection = None
_reranker = None
_embedding_model = None
_whoosh = None

def get_chroma_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH, settings=Settings(allow_reset=False))
        _collection = _client.get_or_create_collection(CHROMA_COLLECTION)
    return _collection

def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANKER_MODEL_NAME)
    return _reranker

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model

def get_whoosh():
    global _whoosh
    if _whoosh is None and WHOOSH_INDEX_PATH and os.path.isdir(WHOOSH_INDEX_PATH):
        try:
            from whoosh.index import open_dir
            from whoosh.qparser import MultifieldParser
            ix = open_dir(WHOOSH_INDEX_PATH)
            qp = MultifieldParser(["text","title","url","partner_id"], schema=ix.schema)
            _whoosh = (ix, qp)
        except Exception:
            _whoosh = None
    return _whoosh

def topic_to_query(topic: Topic) -> str:
    # Convert Topic (pydantic) → dict safely
    t = topic.model_dump() if hasattr(topic, "model_dump") else topic

    name = t.get("name", "")
    definition = t.get("definition", "")
    synonyms = t.get("synonyms", [])
    inputs = t.get("inputs", [])
    outputs = t.get("outputs", [])
    exclusions = t.get("exclusions", [])

    query_terms = [
        name,
        definition,
        *synonyms,
        *inputs,
        *outputs,
    ]

    excl = [f"-{w}" for w in exclusions]

    return " ".join([str(x) for x in query_terms if x] + excl).strip()


def merge_scores(dense_items: List[RetrieveItem], bm25_items: List[RetrieveItem], top_k: int = 100) -> List[RetrieveItem]:
    by_key: Dict[str, RetrieveItem] = {}
    def key(it): return (it.url, it.text[:64])
    def norm(xs):
        xs = [x for x in xs if x is not None]
        if not xs: return (0.0, 1.0)
        return (min(xs), max(xs) if max(xs)-min(xs)!=0 else min(xs)+1e-6)

    dmins,dmaxs = norm([i.score_dense for i in dense_items])
    bmins,bmaxs = norm([i.score_bm25 for i in bm25_items])

    for it in dense_items:
        k = str(key(it))
        it.score_dense = (it.score_dense - dmins)/(dmaxs-dmins+1e-9) if it.score_dense is not None else None
        if k not in by_key: by_key[k] = it
        else:
            if it.score_dense and (by_key[k].score_dense or 0) < it.score_dense:
                by_key[k].score_dense = it.score_dense

    for it in bm25_items:
        k = str(key(it))
        it.score_bm25 = (it.score_bm25 - bmins)/(bmaxs-bmins+1e-9) if it.score_bm25 is not None else None
        if k not in by_key: by_key[k] = it
        else:
            if it.score_bm25 and (by_key[k].score_bm25 or 0) < it.score_bm25:
                by_key[k].score_bm25 = it.score_bm25

    vals = list(by_key.values())
    vals.sort(key=lambda x: max(x.score_dense or 0, x.score_bm25 or 0), reverse=True)
    return vals[:top_k]

@app.post("/retrieve", response_model=List[RetrieveItem])
def retrieve(req: RetrieveRequest):
    col = get_chroma_collection()
    topic_query = topic_to_query(req.topic)
    query_embedding = get_embedding_model().encode(topic_query).tolist()
    results = col.query(
        query_embeddings=[query_embedding],
        n_results=req.k_dense,
        where={"partner_id": req.partner_id}
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    dense_items = []
    for d, m, distance in zip(docs, metas, distances):
        dense_items.append(RetrieveItem(
            text=d,
            url=m.get("url"),
            title=m.get("title"),
            score_dense=1.0 / (1.0 + float(distance)),
            score_bm25=None
        ))

    bm25_items: List[RetrieveItem] = []
    w = get_whoosh()
    # Only run BM25 if we actually want > 0 results
    if w is not None and (req.k_bm25 or 0) > 0:
        ix, qp = w
        with ix.searcher() as s:
            from whoosh.query import And, Term
            q = And([qp.parse(topic_query), Term("partner_id", req.partner_id)])
            rs = s.search(q, limit=req.k_bm25)
            for r in rs:
                bm25_items.append(RetrieveItem(
                    text=r.get("text", ""),
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    score_dense=None,
                    score_bm25=float(r.score)
                ))


    merged = merge_scores(dense_items, bm25_items, top_k=max(req.k_dense, req.k_bm25))
    return merged

@app.post("/rerank", response_model=List[RerankedItem])
def rerank(req: RerankRequest):
    reranker = get_reranker()
    pairs = [(req.topic_query, c.text) for c in req.candidates]
    scores = reranker.predict(pairs)
    items = []
    for c, sc in zip(req.candidates, scores):
        items.append(RerankedItem(text=c.text, url=c.url, title=c.title, rerank_score=float(sc)))
    items.sort(key=lambda x: x.rerank_score, reverse=True)
    return items[:req.top_k]

class HybridRequest(BaseModel):
    partner_id: str
    topic: Topic
    k_dense: int = 50
    k_bm25: int = 50
    top_k: int = 10

@app.post("/hybrid", response_model=List[RerankedItem])
def hybrid(req: HybridRequest):
    retrieved = retrieve(RetrieveRequest(partner_id=req.partner_id, topic=req.topic, k_dense=req.k_dense, k_bm25=req.k_bm25))
    topic_query = topic_to_query(req.topic)
    reranked = rerank(RerankRequest(topic_query=topic_query, candidates=retrieved, top_k=req.top_k))
    return reranked

# retriever-service

FastAPI microservice that provides **hybrid retrieval** (dense via Chroma, optional BM25)
and a **cross-encoder reranker**. Use the same embedding model for indexing and querying (`EMBEDDING_MODEL`).

## Install
```powershell
cd retriever-service
pip install -r requirements.txt
# Ensure shared-contracts is installed as well:
# cd ..\shared-contracts && pip install -e .
```

## Run
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## Optional: build BM25 index
```powershell
python -m app.bm25_build --in ..\chunker-deduper\chunks.csv --index .whoosh
# Then set env var WHOOSH_INDEX=.whoosh before starting the API
```

# embedding-indexer

Embeds `chunks.parquet` or `chunks.csv` and writes them into a **ChromaDB** collection.
Includes a simple query script to sanity-check retrieval.

## Install (inside your existing .venv)
```powershell
cd embedding-indexer
pip install -r requirements.txt
```

## Run the indexer
```powershell
# Example with CSV from the previous step
python index.py `
  --in ..\chunker-deduper\chunks.csv `
  --collection competence_chunks `
  --model sentence-transformers/all-MiniLM-L6-v2
```

You can also pass a Parquet file:
```powershell
python index.py --in ..\chunker-deduper\chunks.parquet --collection competence_chunks --model sentence-transformers/all-MiniLM-L6-v2
```

## Test a query
```powershell
python query.py --collection competence_chunks --query "model-based systems engineering SysML digital thread"
```


import argparse
import os
import sys
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

def load_df(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    else:
        return pd.read_parquet(path)

def main():
    ap = argparse.ArgumentParser(description="Index chunks to ChromaDB")
    ap.add_argument("--in", dest="inp", required=True, help="Path to chunks.csv or chunks.parquet")
    ap.add_argument("--collection", default="competence_chunks", help="Chroma collection name")
    ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2", help="SentenceTransformer model")
    ap.add_argument("--persist", default=".chroma", help="Chroma persistence directory")
    ap.add_argument("--batch", type=int, default=256, help="Batch size")
    args = ap.parse_args()

    df = load_df(Path(args.inp))
    required_cols = {"chunk_id","text","partner_id","url","title","date"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"[error] Missing columns in input: {missing}", file=sys.stderr)
        sys.exit(1)

    client = chromadb.PersistentClient(path=args.persist, settings=Settings(allow_reset=False))
    col = client.get_or_create_collection(args.collection, metadata={"hnsw:space": "cosine"})

    model = SentenceTransformer(args.model)

    ids = df["chunk_id"].astype(str).tolist()
    texts = df["text"].astype(str).tolist()
    metadatas = df[["partner_id","url","title","date","char_len"]].astype(str).to_dict(orient="records")

    # Insert in batches
    for i in tqdm(range(0, len(ids), args.batch), desc="Indexing"):
        j = min(i + args.batch, len(ids))
        batch_ids = ids[i:j]
        batch_texts = texts[i:j]
        batch_metas = metadatas[i:j]
        embeddings = model.encode(batch_texts, show_progress_bar=False, convert_to_numpy=True).tolist()
        col.upsert(ids=batch_ids, documents=batch_texts, metadatas=batch_metas, embeddings=embeddings)

    print(f"OK. Indexed {len(ids)} chunks into collection '{args.collection}'.")
    print(f"Chroma files persisted at: {args.persist}")

if __name__ == "__main__":
    main()

import argparse
import pandas as pd
from whoosh import index
from whoosh.fields import Schema, TEXT, ID
from whoosh.analysis import StemmingAnalyzer
from pathlib import Path
import os

def main():
    ap = argparse.ArgumentParser(description="Build Whoosh BM25 index from chunks CSV/Parquet")
    ap.add_argument("--in", dest="inp", required=True, help="Path to chunks.csv or chunks.parquet")
    ap.add_argument("--index", required=True, help="Output directory for Whoosh index")
    args = ap.parse_args()

    p = Path(args.inp)
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
    else:
        df = pd.read_parquet(p)

    os.makedirs(args.index, exist_ok=True)
    schema = Schema(
        id=ID(stored=True, unique=True),
        partner_id=ID(stored=True),
        url=ID(stored=True),
        title=TEXT(stored=True, analyzer=StemmingAnalyzer()),
        text=TEXT(stored=True, analyzer=StemmingAnalyzer())
    )
    if not index.exists_in(args.index):
        ix = index.create_in(args.index, schema)
    else:
        ix = index.open_dir(args.index)

    writer = ix.writer(limitmb=512, procs=1, multisegment=True)
    for i, row in df.iterrows():
        writer.update_document(
            id=str(row.get("chunk_id", f"row-{i}")),
            partner_id=str(row.get("partner_id","")),
            url=str(row.get("url","")),
            title=str(row.get("title","")),
            text=str(row.get("text",""))
        )
    writer.commit()
    print(f"OK. Built Whoosh index at: {args.index}")

if __name__ == "__main__":
    main()

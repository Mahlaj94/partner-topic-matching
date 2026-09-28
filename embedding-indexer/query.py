
import argparse
import chromadb
from chromadb.config import Settings

def main():
    ap = argparse.ArgumentParser(description="Simple ChromaDB query")
    ap.add_argument("--collection", default="competence_chunks")
    ap.add_argument("--query", required=True)
    ap.add_argument("--persist", default=".chroma")
    ap.add_argument("--topk", type=int, default=5)
    args = ap.parse_args()

    client = chromadb.PersistentClient(path=args.persist, settings=Settings(allow_reset=False))
    col = client.get_or_create_collection(args.collection)

    results = col.query(query_texts=[args.query], n_results=args.topk)
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    ids = results.get("ids", [[]])[0]

    for rank, (i, m, d) in enumerate(zip(ids, metas, docs), start=1):
        print(f"#{rank}  id={i}")
        print(f"    partner={m.get('partner_id')}  url={m.get('url')}")
        print(f"    title={m.get('title')}  date={m.get('date')}")
        #print(f"    text={d[:220].replace('\\n',' ')}...")
        print("    text=" + d[:220].replace("\n", " ") + "...")
        print()

if __name__ == "__main__":
    main()

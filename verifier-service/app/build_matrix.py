import argparse, json, pandas as pd
from pathlib import Path
import httpx
from shared_contracts import Topic, Partner

def load_topics(p: Path):
    data = json.loads(p.read_text(encoding="utf-8"))

    # Accept both legacy topics and supply chains
    items = data.get("topics") or data.get("supply_chains") or []

    topics = []
    for it in items:
        # Build a payload that includes SC semantics
        topic_payload = {
            "id": it.get("id"),
            "name": it.get("name"),
            "definition": it.get("definition") or it.get("description", ""),
            "synonyms": it.get("synonyms", []) or [],
            "exclusions": it.get("exclusions", []) or [],
            "inputs": it.get("inputs", []) or [],
            "outputs": it.get("outputs", []) or [],
        }
        topics.append(topic_payload)

    return topics



def load_partners(p: Path):
    data = json.loads(p.read_text(encoding="utf-8"))
    return [Partner(**t) for t in data.get("partners", [])]

def main():
    ap = argparse.ArgumentParser(description="Batch build Topic×Partner matrix")
    ap.add_argument("--topics", required=True)
    ap.add_argument("--partners", required=True)
    ap.add_argument("--retriever", required=True)  # http://localhost:8001/hybrid
    ap.add_argument("--verifier", default="http://localhost:8002/verify")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--out", default="matrix.csv")
    args = ap.parse_args()

    topics = load_topics(Path(args.topics))
    partners = load_partners(Path(args.partners))

    print(f"Loaded {len(topics)} topics")
    print(f"Loaded {len(partners)} partners")

    rows = []
    #with httpx.Client(timeout=120) as client:
    with httpx.Client(timeout=300) as client:

        for p in partners:
            for t in topics:
                topic_payload = t  # already a dict with inputs/outputs

                body = {
                    "partner_id": p.id,
                    "topic": topic_payload,
                    "k_dense": max(args.k, 10),
                    "k_bm25": max(args.k, 10),   # optional improvement
                    "top_k": args.k
                }

                r = client.post(args.retriever, json=body)
                r.raise_for_status()
                cands = r.json()
                #snippets = [{"text": c["text"], "url": c["url"], "title": c.get("title")} for c in cands[:args.k]]
                snippets = [
                    {
                        "text": c["text"][:800],  # truncate long chunks
                        "url": c["url"],
                        "title": c.get("title")
                    }
                    for c in cands[:args.k]
                ]

                #vbody = {"partner_id": p.id, "topic": t.model_dump(mode="json"), "snippets": snippets}
                vbody = {
                    "partner_id": p.id,
                    "topic": topic_payload,
                    "snippets": snippets
                }

                vr = client.post(args.verifier, json=vbody)
                vr.raise_for_status()
                verdict = vr.json()

                rows.append({
                    "partner_id": p.id,
                    #"topic_id": t.id,
                    "topic_id": t["id"],
                    "label": verdict.get("label"),
                    "confidence": verdict.get("confidence"),
                    "rationale": verdict.get("rationale"),
                    "evidence_json": json.dumps(verdict.get("evidence", []), ensure_ascii=False)
                })
                #print(f"[{p.id} × {t.id}] -> {verdict.get('label')} ({verdict.get('confidence')})")
                print(f"[{p.id} × {t['id']}] -> {verdict.get('label')} ({verdict.get('confidence')})")


    pd.DataFrame(rows).to_csv(args.out, index=False, encoding="utf-8")
    print(f"OK. Wrote matrix -> {args.out}")

if __name__ == "__main__":
    main()

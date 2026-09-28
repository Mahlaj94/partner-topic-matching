import argparse
import json
import re
import sys
import hashlib
from pathlib import Path
from typing import List, Dict

import pandas as pd
from datasketch import MinHash, MinHashLSH
from tqdm import tqdm

SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9])')

def read_ndjson(path: Path) -> List[Dict]:
    out = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out

def normalize_text(s: str) -> str:
    import re
    s = re.sub(r'\s+', ' ', (s or '')).strip()
    return s

def split_into_sentences(text: str) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    parts = SENT_SPLIT_RE.split(text)
    if len(parts) <= 1:
        words = text.split()
        step = 120
        return [' '.join(words[i:i+step]) for i in range(0, len(words), step)]
    return parts

def chunk_text(sentences: List[str], target_len: int, overlap: int, min_chars: int) -> List[str]:
    chunks = []
    buf = ''
    for sent in sentences:
        if not sent:
            continue
        if len(buf) + 1 + len(sent) <= target_len:
            buf = (buf + ' ' + sent).strip()
        else:
            if len(buf) >= min_chars:
                chunks.append(buf)
            if overlap > 0 and buf:
                tail = buf[-overlap:]
                buf = (tail + ' ' + sent).strip()
            else:
                buf = sent.strip()
    if len(buf) >= min_chars:
        chunks.append(buf)
    return chunks

def shingle_words(text: str, k: int = 5):
    import re
    words = re.findall(r'\w+', text.lower())
    for i in range(max(0, len(words) - k + 1)):
        yield ' '.join(words[i:i+k])

def minhash_signature(text: str, num_perm: int = 64) -> MinHash:
    m = MinHash(num_perm=num_perm)
    for sh in shingle_words(text, k=5):
        m.update(sh.encode('utf8'))
    return m

def dedup_chunks(rows: List[Dict], threshold: float = 0.82) -> List[Dict]:
    if not rows:
        return rows
    lsh = MinHashLSH(threshold=threshold, num_perm=64)
    kept = []
    for idx, r in enumerate(rows):
        m = minhash_signature(r['text'], num_perm=64)
        dupes = lsh.query(m)
        if not dupes:
            key = f'k{idx}'
            lsh.insert(key, m)
            kept.append(r)
        else:
            pass
    return kept

def make_chunk_id(partner_id: str, url: str, text: str, i: int) -> str:
    h = hashlib.sha1(f'{partner_id}|{url}|{i}|{text[:64]}'.encode('utf-8')).hexdigest()[:16]
    return f'{partner_id}-{h}-{i}'

def main():
    ap = argparse.ArgumentParser(description='Chunk + Dedup')
    ap.add_argument('--in', dest='inp', required=True, help='Path to crawl.ndjson')
    ap.add_argument('--out', default='chunks.parquet', help='Output path')
    ap.add_argument('--out-format', choices=['parquet','csv'], default='parquet', help='File format')
    ap.add_argument('--target-len', type=int, default=1000, help='Target chunk length in characters')
    ap.add_argument('--overlap', type=int, default=150, help='Character overlap between chunks')
    ap.add_argument('--min-chars', type=int, default=200, help='Minimum characters to keep a chunk')
    ap.add_argument('--dedup-threshold', type=float, default=0.82, help='Jaccard threshold for near-duplicate removal')
    args = ap.parse_args()

    src = Path(args.inp)
    if not src.exists():
        print(f'[error] Input not found: {src}', file=sys.stderr)
        sys.exit(1)

    pages = read_ndjson(src)
    cols = ['chunk_id','partner_id','url','title','date','text','char_len']
    if not pages:
        print('[warn] No pages in input.', file=sys.stderr)
        import pandas as pd
        df = pd.DataFrame(columns=cols)
        if args.out_format=='parquet':
            df.to_parquet(args.out, index=False)
        else:
            df.to_csv(args.out, index=False, encoding='utf-8')
        return

    rows = []
    for p in tqdm(pages, desc='Chunking pages'):
        text = p.get('text') or ''
        if not text:
            continue
        sentences = split_into_sentences(text)
        chunks = chunk_text(sentences, target_len=args.target_len, overlap=args.overlap, min_chars=args.min_chars)
        for i, ch in enumerate(chunks):
            rows.append({
                'partner_id': p.get('partner_id'),
                'url': p.get('url'),
                'title': p.get('title'),
                'date': p.get('date'),
                'text': ch,
                'char_len': len(ch),
            })

    if not rows:
        print('[warn] No chunks created from input.', file=sys.stderr)

    rows = dedup_chunks(rows, threshold=args.dedup_threshold)

    for i, r in enumerate(rows):
        r['chunk_id'] = make_chunk_id(r.get('partner_id',''), r.get('url',''), r['text'], i)

    import pandas as pd
    df = pd.DataFrame(rows, columns=cols)
    if args.out_format == 'parquet':
        df.to_parquet(args.out, index=False)
    else:
        df.to_csv(args.out, index=False, encoding='utf-8')

    print(f'OK. Wrote {len(df)} chunks -> {args.out}')

if __name__ == '__main__':
    main()
# chunker-deduper

Reads `crawl.ndjson` from the crawler, splits pages into overlapping chunks,
removes near-duplicates, and writes `chunks.parquet` (or CSV).

## Install (inside your existing .venv)
```powershell
cd chunker-deduper
pip install -r requirements.txt
```

## Run
```powershell
python chunk.py `
  --in ..\focused-crawler\crawl.ndjson `
  --out chunks.parquet `
  --target-len 1000 `
  --overlap 150 `
  --min-chars 200 `
  --dedup-threshold 0.82 `
  --out-format parquet
```

> Use `--out-format csv` if you prefer CSV.

## Output columns
- `chunk_id` – deterministic id
- `partner_id`
- `url`
- `title`
- `date`
- `text`
- `char_len`

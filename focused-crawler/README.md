# focused-crawler

A lightweight, domain-focused web crawler that:
- Reads partners from `seed-data/build/partners.json`
- Stays within each partner's domains
- Respects `robots.txt`
- Uses `trafilatura` to extract clean text, title, and date
- Writes **newline-delimited JSON** to `crawl.ndjson`

## Install (inside your existing .venv)
```powershell
cd focused-crawler
pip install -r requirements.txt
```
> If you haven't installed the shared package yet, do:
> ```powershell
> cd ..\shared-contracts
> pip install -e .
> ```

## Run
```powershell
# From the repo root
python .\focused-crawler\crawler.py `
  --partners .\seed-data\build\partners.json `
  --out .\focused-crawler\crawl.ndjson `
  --max-pages 50 `
  --depth 2
```
Run from the repository root in PowerShell. The example domain is a placeholder.

## Output
Each line in `crawl.ndjson` is an object like:
```json
{
  "partner_id": "demo_partner",
  "url": "https://example.com/example-page",
  "title": "Page title",
  "date": "2024-05-12T00:00:00",
  "html_bytes": 53210,
  "text": "Cleaned textual content..."
}
```

## Notes
- We attempt sitemap discovery first; if no sitemap is found, we crawl the homepage and its in-domain links up to `--depth`.
- We limit to `--max-pages` **per partner**.
- The crawler is polite (robots-aware) and defaults to a short delay between requests.

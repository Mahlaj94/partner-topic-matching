import argparse
import json
import time
import re
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Set, List, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import tldextract
from urllib import robotparser

import trafilatura
from trafilatura.sitemaps import sitemap_search


USER_AGENT = "CompetenceMatrixCrawler/0.1 (+https://example.com)"
REQ_TIMEOUT = 15
SLEEP_BETWEEN = 0.5  # seconds between requests (be polite)


@dataclass
class Partner:
    id: str
    name: str
    domains: List[str]
    aliases: List[str]


def load_partners(path: Path) -> List["Partner"]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for p in data.get("partners", []):
        items.append(Partner(
            id=p["id"],
            name=p["name"],
            domains=p.get("domains", []),
            aliases=p.get("aliases", []),
        ))
    return items


def same_registered_domain(a: str, b: str) -> bool:
    ea = tldextract.extract(a)
    eb = tldextract.extract(b)
    return (ea.domain, ea.suffix) == (eb.domain, eb.suffix)


def in_allowed_domains(url: str, allowed: List[str]) -> bool:
    if not allowed:
        return True
    try:
        uhost = urlparse(url).netloc.lower()
    except Exception:
        return False
    for d in allowed:
        host = urlparse(d).netloc.lower()
        if uhost == host or uhost.endswith("." + host):
            return True
        # Also allow same registered domain (e.g., sub-sites)
        if same_registered_domain("http://" + uhost, d):
            return True
    return False


def get_robot_parser(seed_url: str) -> robotparser.RobotFileParser:
    parsed = urlparse(seed_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
    except Exception:
        pass  # If robots fails, default to allowing
    return rp


def discover_urls_via_sitemaps(domain: str, limit: int = 200) -> List[str]:
    """Try to find a sitemap and return up to `limit` URLs from it."""
    out = []
    try:
        smaps = sitemap_search(domain, verify=False, timeout=REQ_TIMEOUT)
        for sm in smaps[:5]:  # try a few sitemaps, not all
            try:
                r = requests.get(sm, headers={"User-Agent": USER_AGENT}, timeout=REQ_TIMEOUT)
                if r.status_code != 200 or "xml" not in r.headers.get("Content-Type",""):
                    continue
                # naive parse: look for <loc>...</loc>
                locs = re.findall(r"<loc>(.*?)</loc>", r.text)
                for u in locs:
                    if in_allowed_domains(u, [domain]):
                        out.append(u.strip())
                        if len(out) >= limit:
                            return out
            except Exception:
                continue
    except Exception:
        pass
    return out


def extract_clean(html: bytes, url: str) -> Tuple[str, str, datetime | None]:
    downloaded = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        # output="json",   # currently commented out
        with_metadata=True,
        favor_recall=True,
        url=url
    )
    text, title, date_dt = "", None, None

    if downloaded:
        try:
            # try JSON mode (works if extract() actually returned JSON)
            obj = json.loads(downloaded)
            text = obj.get("text", "") or ""
            title = obj.get("title") or None
            date = obj.get("date") or obj.get("timestamp") or None
            if date:
                try:
                    date_dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                except Exception:
                    date_dt = None
        except Exception:
            # ✅ fallback: plain-text output
            text = downloaded or ""

    if not title:
        try:
            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
        except Exception:
            pass

    return text, (title or ""), date_dt



def fetch(url: str, rp: robotparser.RobotFileParser) -> bytes | None:
    if rp and not rp.can_fetch(USER_AGENT, url):
        return None
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQ_TIMEOUT)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            return r.content
    except Exception:
        return None
    return None


def extract_links(html: bytes, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        try:
            full = urljoin(base_url, href)
            out.append(full)
        except Exception:
            continue
    return out


def crawl_partner(partner: Partner, out_path: Path, max_pages: int, max_depth: int):
    seen: Set[str] = set()
    from collections import deque
    q = deque()

    # seeds from sitemaps or homepage
    seed_domain = partner.domains[0] if partner.domains else None
    if not seed_domain:
        print(f"[warn] Partner {partner.id} has no domain; skipping", file=sys.stderr)
        return

    # Start seeds: sitemap URLs first, then homepage
    seeds = discover_urls_via_sitemaps(seed_domain, limit=min(200, max_pages*2))
    if not seeds:
        seeds = [seed_domain]

    rp = get_robot_parser(seed_domain)
    for s in seeds[:max_pages]:
        if in_allowed_domains(s, partner.domains):
            q.append((s, 0))

    written = 0
    with out_path.open("a", encoding="utf-8") as f:
        while q and written < max_pages:
            url, depth = q.popleft()
            if url in seen:
                continue
            seen.add(url)

            if not in_allowed_domains(url, partner.domains):
                continue
            if depth > max_depth:
                continue

            html = fetch(url, rp)
            time.sleep(SLEEP_BETWEEN)
            if not html:
                continue

            text, title, date_dt = extract_clean(html, url)
            if text and len(text) >= 200:
                rec = {
                    "partner_id": partner.id,
                    "url": url,
                    "title": title,
                    "date": date_dt.isoformat() if date_dt else None,
                    "html_bytes": len(html),
                    "text": text,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
                print(f"[{partner.id}] {written}/{max_pages} {url}")

            # Enqueue links for BFS
            if depth < max_depth:
                for link in extract_links(html, url):
                    if in_allowed_domains(link, partner.domains) and link not in seen:
                        q.append((link, depth + 1))


def main():
    ap = argparse.ArgumentParser(description="Focused domain crawler -> crawl.ndjson")
    ap.add_argument("--partners", required=True, help="Path to partners.json (from seed-data/build)")
    ap.add_argument("--out", default="crawl.ndjson", help="Output NDJSON path")
    ap.add_argument("--max-pages", type=int, default=50, help="Max pages per partner")
    ap.add_argument("--depth", type=int, default=2, help="Max crawl depth from seeds")
    ap.add_argument("--partner-id", default=None, help="If set, only crawl this partner id")
    args = ap.parse_args()

    partners_path = Path(args.partners)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    partners = load_partners(partners_path)
    if args.partner_id:
        partners = [p for p in partners if p.id == args.partner_id]
        if not partners:
            print(f"[error] partner id '{args.partner_id}' not found in {partners_path}", file=sys.stderr)
            sys.exit(1)

    for p in partners:
        print(f"== Crawling {p.id} ({p.name}) ==")
        crawl_partner(p, out_path, max_pages=args.max_pages, max_depth=args.depth)

    print(f"Done. Output -> {out_path}")

if __name__ == "__main__":
    main()

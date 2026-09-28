#!/usr/bin/env python3
import sys, json, os
from pathlib import Path

try:
    import yaml
except Exception as e:
    print("Please install pyyaml: pip install pyyaml", file=sys.stderr)
    raise

# Try to import shared-contracts for strong validation
try:
    from shared_contracts.models import Topic, Partner
    HAVE_SHARED = True
except Exception as e:
    HAVE_SHARED = False
    print("[warn] shared-contracts not found. Will perform light validation only.", file=sys.stderr)

ROOT = Path(__file__).parent
out_dir = ROOT / "build"
out_dir.mkdir(exist_ok=True)

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def validate_topics(data):
    items = data.get("topics", [])
    if HAVE_SHARED:
        from pydantic import ValidationError
        validated = []
        seen_ids = set()
        for t in items:
            obj = Topic(**t)
            if obj.id in seen_ids:
                raise ValueError(f"Duplicate topic id: {obj.id}")
            seen_ids.add(obj.id)
            validated.append(obj.model_dump(mode="json"))
        return validated
    else:
        # light checks
        validated = []
        seen = set()
        for t in items:
            assert "id" in t and t["id"], "topic missing id"
            assert "name" in t and t["name"], "topic missing name"
            assert "definition" in t and t["definition"], "topic missing definition"
            if t["id"] in seen:
                raise ValueError(f"Duplicate topic id: {t['id']}")
            seen.add(t["id"])
            validated.append(t)
        return validated

def validate_partners(data):
    items = data.get("partners", [])
    if HAVE_SHARED:
        validated = []
        seen_ids = set()
        for p in items:
            obj = Partner(**p)
            if obj.id in seen_ids:
                raise ValueError(f"Duplicate partner id: {obj.id}")
            seen_ids.add(obj.id)
            validated.append(obj.model_dump(mode="json"))
        return validated
    else:
        validated = []
        seen = set()
        for p in items:
            assert "id" in p and p["id"], "partner missing id"
            assert "name" in p and p["name"], "partner missing name"
            if p["id"] in seen:
                raise ValueError(f"Duplicate partner id: {p['id']}")
            seen.add(p["id"])
            validated.append(p)
        return validated

def main():
    topics_raw = load_yaml(ROOT / "topics.yaml")
    partners_raw = load_yaml(ROOT / "partners.yaml")

    topics_v = validate_topics(topics_raw)
    partners_v = validate_partners(partners_raw)

    (out_dir / "topics.json").write_text(json.dumps({"topics": topics_v}, indent=2, ensure_ascii=False))
    (out_dir / "partners.json").write_text(json.dumps({"partners": partners_v}, indent=2, ensure_ascii=False))

    print("OK. Wrote:")
    print(" - build/topics.json")
    print(" - build/partners.json")

if __name__ == "__main__":
    main()

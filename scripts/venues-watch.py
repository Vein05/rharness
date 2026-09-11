#!/usr/bin/env python3
"""Hash every sources[].url per venue; exit 1 when any changed. --update rewrites sources.lock.json."""
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENUES = ROOT / "venues"


def page_hash(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "rharness-venues-watch"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(text.encode()).hexdigest()


update = "--update" in sys.argv
changed = []
for d in sorted(p for p in VENUES.iterdir() if p.is_dir() and (p / "venue.json").exists()):
    v = json.loads((d / "venue.json").read_text())
    lock_path = d / "sources.lock.json"
    lock = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    new = {}
    for s in v.get("sources", []):
        try:
            new[s["url"]] = page_hash(s["url"])
        except Exception as e:  # unreachable page is reported, not fatal
            print(f"{d.name}: {s['url']}: fetch failed: {e}")
            new[s["url"]] = lock.get(s["url"], "")
        if lock.get(s["url"]) and lock[s["url"]] != new[s["url"]]:
            changed.append(f"{d.name}: {s['kind']} page changed: {s['url']}")
    if update or not lock_path.exists():
        lock_path.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n")
for c in changed:
    print(c)
if changed and not update:
    print(f"{len(changed)} source page(s) changed; review venue.json and bump revision, then run with --update")
    sys.exit(1)
print("sources unchanged" if not changed else "lock files updated")

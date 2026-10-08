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


def run(venues_dir, update=False, fetch=page_hash) -> int:
    venues_dir = Path(venues_dir)
    changed = []
    for d in sorted(p for p in venues_dir.iterdir() if p.is_dir() and (p / "venue.json").exists()):
        v = json.loads((d / "venue.json").read_text())
        lock_path = d / "sources.lock.json"
        have_lock = lock_path.exists()
        lock = json.loads(lock_path.read_text()) if have_lock else {}
        if not have_lock and not update:
            print(f"no sources.lock.json for {d.name}; run scripts/venues-watch.py --update")
        new = {}
        for s in v.get("sources", []):
            try:
                new[s["url"]] = fetch(s["url"])
            except Exception as e:  # unreachable page is reported, not fatal; no entry is stored
                print(f"{d.name}: {s['url']}: fetch failed: {e}")
                continue
            if lock.get(s["url"]) and lock[s["url"]] != new[s["url"]]:
                changed.append(f"{d.name}: {s['kind']} page changed: {s['url']}")
        if update:  # rewriting from new also drops URLs no longer in venue.json
            lock_path.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n")
    for c in changed:
        print(c)
    if changed and not update:
        print(f"{len(changed)} source page(s) changed; review venue.json and bump revision, then run with --update")
        return 1
    print("sources unchanged" if not changed else "lock files updated")
    return 0


if __name__ == "__main__":
    sys.exit(run(VENUES, "--update" in sys.argv))

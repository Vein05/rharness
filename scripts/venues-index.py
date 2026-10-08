#!/usr/bin/env python3
"""Generate venues/INDEX.json from the packages. --check exits 1 when the file is out of date."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENUES = ROOT / "venues"


def build():
    out = []
    for d in sorted(p for p in VENUES.iterdir() if p.is_dir() and (p / "venue.json").exists()):
        v = json.loads((d / "venue.json").read_text())
        p = json.loads((d / "plugin.json").read_text()) if (d / "plugin.json").exists() else {}
        out.append({"name": v["name"], "venue": v["venue"], "cycle": v["cycle"], "primary": v["primary"],
                    "deadline": v["deadlines"][v["primary"]], "revision": v["revision"],
                    "description": p.get("description", "")})
    return json.dumps(out, indent=2) + "\n"


text = build()
idx = VENUES / "INDEX.json"
if "--check" in sys.argv:
    current = idx.read_text() if idx.exists() else ""
    if current != text:
        print("venues/INDEX.json is out of date; run python scripts/venues-index.py")
        sys.exit(1)
    print("venues/INDEX.json is current")
    sys.exit(0)
idx.write_text(text)
print(f"wrote {idx}")

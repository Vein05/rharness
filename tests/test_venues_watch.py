import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("venues_watch", REPO / "scripts" / "venues-watch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


watch = _load()

A = "https://example.invalid/cfp"
B = "https://example.invalid/template"


@pytest.fixture
def venues(tmp_path):
    d = tmp_path / "x2026"
    d.mkdir()
    (d / "venue.json").write_text(json.dumps({
        "venue": "x", "cycle": "2026", "name": "x2026", "revision": "2026-09-10",
        "deadlines": {"full": "2026-09-25T23:59:00-12:00"}, "primary": "full", "anonymous": True,
        "sources": [{"kind": "cfp", "url": A, "retrieved": "2026-09-10"},
                    {"kind": "template", "url": B, "retrieved": "2026-09-10"}],
    }))
    return tmp_path, d


def _fetch(table):
    def fetch(url):
        v = table[url]
        if isinstance(v, Exception):
            raise v
        return v
    return fetch


def test_plain_run_without_lock_writes_nothing_and_exits_zero(venues, capsys):
    root, d = venues
    rc = watch.run(root, update=False, fetch=_fetch({A: "h1", B: "h2"}))
    assert rc == 0
    assert not (d / "sources.lock.json").exists()
    out = capsys.readouterr().out
    assert "no sources.lock.json for x2026; run scripts/venues-watch.py --update" in out


def test_update_writes_the_lock(venues):
    root, d = venues
    assert watch.run(root, update=True, fetch=_fetch({A: "h1", B: "h2"})) == 0
    assert json.loads((d / "sources.lock.json").read_text()) == {A: "h1", B: "h2"}


def test_changed_hash_exits_one_and_names_kind_and_url(venues, capsys):
    root, d = venues
    watch.run(root, update=True, fetch=_fetch({A: "h1", B: "h2"}))
    rc = watch.run(root, update=False, fetch=_fetch({A: "CHANGED", B: "h2"}))
    assert rc == 1
    out = capsys.readouterr().out
    assert f"x2026: cfp page changed: {A}" in out
    assert B not in out.split("page changed")[1]
    assert json.loads((d / "sources.lock.json").read_text()) == {A: "h1", B: "h2"}, "plain run must not write"


def test_unchanged_exits_zero(venues, capsys):
    root, _ = venues
    watch.run(root, update=True, fetch=_fetch({A: "h1", B: "h2"}))
    assert watch.run(root, update=False, fetch=_fetch({A: "h1", B: "h2"})) == 0
    assert "sources unchanged" in capsys.readouterr().out


def test_fetch_failure_stores_no_entry_and_is_reported(venues, capsys):
    root, d = venues
    rc = watch.run(root, update=True, fetch=_fetch({A: "h1", B: RuntimeError("HTTP 503")}))
    assert rc == 0
    assert json.loads((d / "sources.lock.json").read_text()) == {A: "h1"}
    assert f"x2026: {B}: fetch failed: HTTP 503" in capsys.readouterr().out
    # the next successful fetch establishes the baseline
    watch.run(root, update=True, fetch=_fetch({A: "h1", B: "h2"}))
    assert json.loads((d / "sources.lock.json").read_text()) == {A: "h1", B: "h2"}


def test_update_drops_urls_no_longer_in_venue_json(venues):
    root, d = venues
    watch.run(root, update=True, fetch=_fetch({A: "h1", B: "h2"}))
    v = json.loads((d / "venue.json").read_text())
    v["sources"] = [s for s in v["sources"] if s["url"] == A]
    (d / "venue.json").write_text(json.dumps(v))
    watch.run(root, update=True, fetch=_fetch({A: "h1"}))
    assert json.loads((d / "sources.lock.json").read_text()) == {A: "h1"}

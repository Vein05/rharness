import json
from conftest import run_cli
from rharness import gitutil
from rharness.provenance import parse_ledger, upsert_rows


def _project(ws, slug="seam"):
    run_cli(["new", slug], cwd=ws)
    p = ws / slug
    (p / "traces").mkdir()
    (p / "traces" / "run-1.jsonl").write_text('{"a": 1}\n')
    (p / "traces" / "run-2.jsonl").write_text('{"a": 2}\n')
    gitutil.git(["add", "-A"], p); gitutil.git(["commit", "-q", "-m", "traces"], p)
    return p


def _msgs(ws, *args):
    code, out, err = run_cli(["lint", "--json", *args], cwd=ws)
    return [json.loads(l) for l in out.splitlines() if l.startswith("{")]


def test_new_project_has_ledger_template(ws):
    run_cli(["new", "seam"], cwd=ws)
    t = (ws / "seam" / "research" / "PROVENANCE.md").read_text()
    assert "| path | sha16 |" in t


def test_hash_records_rows_with_commit_and_note(ws):
    p = _project(ws)
    code, out, err = run_cli(["hash", "traces/run-1.jsonl", "--note", "pilot"], cwd=p)
    assert code == 0, err
    rows = parse_ledger((p / "research" / "PROVENANCE.md").read_text())
    assert len(rows) == 1
    r = rows[0]
    assert r["path"] == "traces/run-1.jsonl" and len(r["sha16"]) == 16 and r["bytes"] == "9"
    assert r["note"] == "pilot" and r["commit"] not in ("no-git", "no-commit")
    assert "+dirty" not in r["commit"]
    assert "traces/run-1.jsonl" in out and r["sha16"] in out


def test_hash_from_subdir_and_rehash_replaces_row(ws):
    p = _project(ws)
    run_cli(["hash", "run-1.jsonl"], cwd=p / "traces")
    (p / "traces" / "run-1.jsonl").write_text('{"a": 111}\n')
    run_cli(["hash", "traces/run-1.jsonl"], cwd=p)
    rows = parse_ledger((p / "research" / "PROVENANCE.md").read_text())
    assert len(rows) == 1 and rows[0]["bytes"] == "11"
    assert "+dirty" in rows[0]["commit"]


def test_hash_outside_project_is_error(ws):
    code, out, err = run_cli(["hash", "AGENTS.md"], cwd=ws)
    assert code == 2 and "project" in err


def test_lint_flags_changed_and_missing_recorded_artifacts(ws):
    p = _project(ws)
    run_cli(["hash", "traces/run-1.jsonl", "traces/run-2.jsonl"], cwd=p)
    gitutil.git(["add", "-A"], p); gitutil.git(["commit", "-q", "-m", "ledger"], p)
    assert not [m for m in _msgs(ws) if "PROVENANCE" in m["message"] or "changed since" in m["message"]]
    (p / "traces" / "run-1.jsonl").write_text("tampered\n")
    (p / "traces" / "run-2.jsonl").unlink()
    msgs = _msgs(ws)
    changed = [m for m in msgs if "changed since it was recorded" in m["message"]]
    missing = [m for m in msgs if "is missing" in m["message"] and "run-2" in m["message"]]
    assert changed and changed[0]["severity"] == "error" and "run-1" in changed[0]["message"]
    assert missing and missing[0]["severity"] == "error"


def test_lint_warns_on_unrecorded_trace(ws):
    p = _project(ws)
    run_cli(["hash", "traces/run-1.jsonl"], cwd=p)
    msgs = _msgs(ws)
    hit = [m for m in msgs if "not in research/PROVENANCE.md" in m["message"]]
    assert len(hit) == 1 and "run-2" in hit[0]["message"] and hit[0]["severity"] == "warning"


def test_upsert_rows_creates_table_when_absent():
    text = "# Provenance ledger\n"
    row = {"path": "traces/x", "sha16": "a" * 16, "bytes": "1", "recorded": "2026-09-10", "commit": "abc", "note": ""}
    out = upsert_rows(text, [row])
    assert "| path | sha16 |" in out and "| `traces/x` |" in out
    out2 = upsert_rows(out, [dict(row, sha16="b" * 16)])
    assert out2.count("| `traces/x` |") == 1 and "b" * 16 in out2


def test_brief_mentions_ledger_state(ws):
    p = _project(ws)
    run_cli(["hash", "traces/run-1.jsonl"], cwd=p)
    code, out, err = run_cli(["brief", "seam"], cwd=ws)
    assert "## Provenance: 1 recorded artifact" in out

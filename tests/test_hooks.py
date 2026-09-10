import datetime as dt
import json
import os
import subprocess
from conftest import run_cli, REPO, BIN
from rharness import gitutil


def _settings(ws):
    return json.loads((ws / ".claude" / "settings.json").read_text())


def _hook_cmds(settings, event):
    return [h["command"] for e in settings.get("hooks", {}).get(event, []) for h in e["hooks"]]


def test_init_registers_session_hooks_for_claude(tmp_path, home):
    root = tmp_path / "r"
    code, out, err = run_cli(["init", str(root), "--no-plugins"], cwd=tmp_path)
    assert code == 0, err
    s = _settings(root)
    assert any("rharness brief" in c for c in _hook_cmds(s, "SessionStart"))
    assert any("session-check" in c for c in _hook_cmds(s, "Stop"))
    m = json.loads((root / ".rharness" / "manifest.json").read_text())
    assert "base" in m["hooks"] and len(m["hooks"]["base"]) == 2


def test_init_codex_only_registers_no_hooks(tmp_path, home):
    root = tmp_path / "r"
    run_cli(["init", str(root), "--harness", "codex", "--no-plugins"], cwd=tmp_path)
    assert not (root / ".claude").exists()


def test_adopt_registers_session_hooks_once(tmp_path, home):
    root = tmp_path / "research"; root.mkdir()
    (root / "AGENTS.md").write_text("# ws\n")
    (root / "p").mkdir(); (root / "p" / "CHARTER.md").write_text("# p\n")
    run_cli(["adopt", str(root)], cwd=tmp_path)
    run_cli(["adopt", str(root)], cwd=tmp_path)
    s = _settings(root)
    assert len([c for c in _hook_cmds(s, "SessionStart") if "rharness brief" in c]) == 1


def test_session_start_hook_command_prints_brief(ws, tmp_path):
    run_cli(["new", "seam"], cwd=ws)
    shim = tmp_path / "shimbin"; shim.mkdir()
    (shim / "rharness").write_text(f"#!/bin/sh\nexec python3 {BIN} \"$@\"\n"); (shim / "rharness").chmod(0o755)
    cmd = [c for c in _hook_cmds(_settings(ws), "SessionStart") if "brief" in c][0]
    env = dict(os.environ, PATH=f"{shim}:{os.environ['PATH']}", CLAUDE_PROJECT_DIR=str(ws / "seam"),
               RHARNESS_SKIP_SETUP="1")
    r = subprocess.run(["sh", "-c", cmd], env=env, capture_output=True, text=True, cwd=str(ws))
    assert r.returncode == 0
    assert r.stdout.startswith("# Brief: seam")


def _worked_today(ws, slug):
    run_cli(["new", slug], cwd=ws)
    p = ws / slug
    for f in list((p / "handoff").glob("20*.md")) + list((p / "changelog").glob("20*.md")):
        f.unlink()
    gitutil.git(["add", "-A"], p); gitutil.git(["commit", "-q", "-m", "work"], p)
    return p


def test_session_check_blocks_when_todays_records_missing(ws):
    _worked_today(ws, "seam")
    code, out, err = run_cli(["session-check"], cwd=ws / "seam")
    assert code == 0, err
    d = json.loads(out)
    assert d["decision"] == "block"
    assert f"handoff/{dt.date.today().isoformat()}.md" in d["reason"]
    assert "changelog/" in d["reason"]


def test_session_check_silent_when_records_exist(ws):
    p = _worked_today(ws, "seam")
    t = dt.date.today().isoformat()
    (p / "handoff" / f"{t}.md").write_text("# Handoff\n")
    (p / "changelog" / f"{t}.md").write_text("# Changelog\n")
    code, out, err = run_cli(["session-check"], cwd=p)
    assert code == 0 and out.strip() == ""


def test_session_check_silent_when_untouched_today(ws):
    p = _worked_today(ws, "seam")
    gitutil.git(["commit", "-q", "--amend", "--no-edit", "--date", "2020-01-01T00:00:00"], p)
    os.environ.get("X")
    # amend keeps the committer date as now, so set both dates explicitly via env
    env = dict(GIT_COMMITTER_DATE="2020-01-01T00:00:00", GIT_AUTHOR_DATE="2020-01-01T00:00:00")
    subprocess.run(["git", "commit", "-q", "--amend", "--no-edit"], cwd=p, env={**os.environ, **env}, check=True)
    for f in p.rglob("*"):
        if f.is_file() and ".git" not in f.parts:
            os.utime(f, (946684800, 946684800))
    code, out, err = run_cli(["session-check"], cwd=p)
    assert code == 0 and out.strip() == "", out


def test_session_check_respects_stop_hook_active(ws):
    _worked_today(ws, "seam")
    r = subprocess.run(["python3", str(BIN), "session-check"], cwd=str(ws / "seam"), input='{"stop_hook_active": true}',
                       capture_output=True, text=True, env={**os.environ, "RHARNESS_SKIP_SETUP": "1"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_session_check_from_workspace_root_covers_all_projects(ws):
    _worked_today(ws, "a")
    _worked_today(ws, "b")
    code, out, err = run_cli(["session-check"], cwd=ws)
    d = json.loads(out)
    assert "a: write" in d["reason"] and "b: write" in d["reason"]


def test_doctor_reports_session_hooks(ws, tmp_path):
    code, out, err = run_cli(["doctor"], cwd=ws)
    assert "session hooks registered" in out and any(l.startswith("ok") and "session hooks" in l for l in out.splitlines())
    s = ws / ".claude" / "settings.json"
    s.write_text(json.dumps({"hooks": {}}))
    code, out, err = run_cli(["doctor"], cwd=ws)
    assert any(l.startswith("FAIL") and "session hooks" in l for l in out.splitlines())

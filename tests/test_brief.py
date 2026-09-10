import datetime as dt
from conftest import run_cli
from rharness import gitutil


def _project(ws, slug="seam"):
    run_cli(["new", slug, "--title", "Paste boundaries"], cwd=ws)
    p = ws / slug
    ch = (p / "CHARTER.md").read_text()
    ch = ch.replace("## Core Question\n\n<!-- One sentence. The thing the paper answers. -->",
                    "## Core Question\n\nDo models fold a trailing remark into the pasted document?")
    ch = ch.replace("**Status:** NOT TRIGGERED", "**Status:** NOT TRIGGERED (recall < 0.5 kills it)")
    (p / "CHARTER.md").write_text(ch)
    for h in (p / "handoff").glob("20*.md"):
        h.unlink()
    (p / "handoff" / "2026-09-08.md").write_text("# Handoff — 2026-09-08\n\nRead AGENTS.md first.\n\n## Next up\n\n1. Score the pilot.\n")
    (p / "changelog" / "2026-09-08.md").write_text("# Changelog — 2026-09-08\n\n## 10:00 — checkpoint 1\n\n- Pilot run collected.\n")
    gitutil.git(["add", "-A"], p); gitutil.git(["commit", "-q", "-m", "c"], p)
    return p


def test_brief_for_named_project(ws):
    _project(ws)
    code, out, err = run_cli(["brief", "seam"], cwd=ws)
    assert code == 0, err
    assert out.startswith("# Brief: seam (Paste boundaries)")
    assert "Core question: Do models fold a trailing remark into the pasted document?" in out
    assert "Kill criterion: NOT TRIGGERED (recall < 0.5 kills it)" in out
    assert "## Newest handoff: handoff/2026-09-08.md" in out and "Score the pilot." in out
    assert "## Last changelog: changelog/2026-09-08.md" in out and "Pilot run collected." in out
    assert "`CHARTER.md`: core question, success and kill criteria" in out
    assert "## Lint:" in out
    assert "Rules: this project's AGENTS.md" in out


def test_brief_detects_project_from_cwd(ws):
    p = _project(ws)
    sub = p / "research"
    code, out, err = run_cli(["brief"], cwd=sub)
    assert code == 0, err
    assert out.startswith("# Brief: seam")


def test_brief_at_workspace_root_lists_projects(ws):
    _project(ws, "a")
    _project(ws, "b")
    code, out, err = run_cli(["brief"], cwd=ws)
    assert code == 0, err
    assert out.startswith("# Brief: workspace")
    assert "| a |" in out and "| b |" in out and "2026-09-08" in out
    assert "rharness brief <project>" in out


def test_brief_without_handoff_says_so(ws):
    run_cli(["new", "z"], cwd=ws)
    for h in (ws / "z" / "handoff").glob("20*.md"):
        h.unlink()
    code, out, err = run_cli(["brief", "z"], cwd=ws)
    assert code == 0, err
    assert "None yet. Write handoff/YYYY-MM-DD.md" in out


def test_brief_caps_long_handoff(ws):
    p = _project(ws)
    (p / "handoff" / "2026-09-09.md").write_text("# Handoff — 2026-09-09\n" + "\n".join(f"line {i}" for i in range(200)))
    code, out, err = run_cli(["brief", "seam", "--lines", "20"], cwd=ws)
    assert code == 0, err
    assert "handoff/2026-09-09.md" in out and "more lines]" in out
    assert "line 150" not in out


def test_brief_unknown_project(ws):
    code, out, err = run_cli(["brief", "nope"], cwd=ws)
    assert code == 2 and "nope" in err

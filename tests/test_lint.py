import json, datetime as dt
from pathlib import Path
from conftest import run_cli
from rharness.lintcfg import load_lint_config
from rharness import gitutil


def _commit_all(p, msg="c"):
    gitutil.git(["add", "-A"], p)
    r = gitutil.git(["commit", "-q", "-m", msg], p)
    assert r.returncode == 0, r.stderr


def _clean_project(ws, slug="p"):
    run_cli(["new", slug], cwd=ws)
    p = ws / slug
    ch = (p / "CHARTER.md").read_text().replace(
        "<!-- The negative result that means stop spending. State a threshold. -->",
        "Stop if the pilot AUC is below 0.55 on the held-out split.").replace(
        "<!-- One sentence. The thing the paper answers. -->",
        "Does the intervention close the gap on the hard split?")
    (p / "CHARTER.md").write_text(ch)
    _commit_all(p)
    today = dt.date.today().isoformat()
    (p / "changelog" / f"{today}.md").write_text(f"# Changelog — {today}\n")
    _commit_all(p)
    return p


def _msgs(out):
    return [json.loads(l) for l in out.splitlines() if l.startswith("{")]


def _run(ws, *extra):
    code, out, err = run_cli(["lint", "--json", *extra], cwd=ws)
    return code, [f["message"] for f in _msgs(out)], _msgs(out)


def test_lintcfg_defaults_and_parse(tmp_path):
    assert load_lint_config(None)["changelog_window_days"] == 14
    f = tmp_path / "lint.toml"
    f.write_text("# c\nhandoff_max_days_behind_commit = 3\n[ignored]\nflag = true\nname = \"x\"\n")
    cfg = load_lint_config(f)
    assert cfg["handoff_max_days_behind_commit"] == 3 and cfg["flag"] is True and cfg["name"] == "x"


def test_clean_project_has_no_errors(ws):
    _clean_project(ws)
    code, msgs, findings = _run(ws)
    assert [f for f in findings if f["severity"] == "error"] == [], msgs
    assert code == 0, msgs


def test_missing_required_file(ws):
    p = _clean_project(ws)
    (p / "spec" / "README.md").unlink(); _commit_all(p)
    code, msgs, _ = _run(ws)
    assert code == 1 and any("spec/README.md" in m and "missing" in m for m in msgs)


def test_kill_criterion_missing(ws):
    p = _clean_project(ws)
    (p / "CHARTER.md").write_text("# c\n"); _commit_all(p)
    code, msgs, _ = _run(ws)
    assert any("Kill Criterion" in m for m in msgs)


def test_spec_status_line(ws):
    p = _clean_project(ws)
    (p / "spec" / "bad.md").write_text("# no status\n"); _commit_all(p)
    _, msgs, _ = _run(ws)
    assert any("spec/bad.md" in m and "Status:" in m for m in msgs)


def test_zero_commits_is_error(ws):
    run_cli(["new", "z"], cwd=ws)
    _, msgs, f = _run(ws)
    assert any("no commits" in m for m in msgs)
    assert [x for x in f if "no commits" in x["message"]][0]["severity"] == "error"


def test_dirty_tree_warning(ws):
    p = _clean_project(ws)
    (p / "scratch.txt").write_text("x")
    _, msgs, f = _run(ws)
    hit = [x for x in f if "uncommitted" in x["message"]]
    assert hit and hit[0]["severity"] == "warning"


def test_stale_handoff_warning(ws):
    p = _clean_project(ws)
    for h in (p / "handoff").glob("20*.md"):
        h.rename(p / "handoff" / "2020-01-01.md")
    _commit_all(p)
    _, msgs, _ = _run(ws)
    assert any("handoff" in m and "older" in m for m in msgs)


def test_changelog_missing_for_commit_day(ws):
    p = _clean_project(ws)
    for c in (p / "changelog").glob("20*.md"):
        c.unlink()
    _commit_all(p)
    _, msgs, _ = _run(ws)
    assert any("changelog" in m and "commit day" in m for m in msgs)


def test_lfs_rules_missing(ws):
    p = _clean_project(ws)
    (p / ".gitattributes").write_text(""); _commit_all(p)
    _, msgs, _ = _run(ws)
    assert any("LFS" in m for m in msgs)


def test_env_not_ignored_is_error(ws):
    p = _clean_project(ws)
    (p / ".gitignore").write_text(""); (p / ".env").write_text("K=1"); _commit_all(p)
    _, msgs, f = _run(ws)
    hit = [x for x in f if ".env" in x["message"]]
    assert hit and hit[0]["severity"] == "error"


def test_relative_dates_warning(ws):
    p = _clean_project(ws)
    (p / "handoff" / "2026-01-01.md").write_text("We ran it last week and will finish next Thursday.\n")
    _commit_all(p)
    _, msgs, _ = _run(ws)
    assert any("relative date" in m and "last week" in m for m in msgs)


def test_writing_guide_drift_warning(ws):
    p = _clean_project(ws)
    w = p / "paper" / "writing.md"
    w.write_text(w.read_text().replace("three-reader", "three-READER"))
    _commit_all(p)
    _, msgs, _ = _run(ws)
    assert any("writing.md" in m and "differs" in m for m in msgs)


def test_text_output_format(ws):
    _clean_project(ws)
    run_cli(["new", "z"], cwd=ws)
    code, out, err = run_cli(["lint"], cwd=ws)
    assert code == 1
    assert "error z/: no commits" in out
    assert out.strip().splitlines()[-1].startswith("Summary:")


def test_lint_single_project_dir_argument(ws):
    p = _clean_project(ws)
    run_cli(["new", "z"], cwd=ws)
    code, out, err = run_cli(["lint", str(p)], cwd=ws)
    assert code == 0, out


def test_workspace_table_mismatch(ws):
    _clean_project(ws, "p")
    a = (ws / "AGENTS.md").read_text().replace("| `p/` |", "| `ghost/` |")
    (ws / "AGENTS.md").write_text(a)
    _, msgs, f = _run(ws)
    assert any("ghost" in m and "no directory" in m for m in msgs)
    assert any("p" in x["message"] and "no row" in x["message"] for x in f if x["project"] == ".")


def test_workspace_row_for_non_project_dir(ws):
    _clean_project(ws, "p")
    (ws / "notes").mkdir()
    a = (ws / "AGENTS.md").read_text().replace("| `p/` |", "| `notes/` |")
    (ws / "AGENTS.md").write_text(a)
    _, msgs, _ = _run(ws)
    assert any("notes" in m and "not a project directory" in m for m in msgs)


def test_workspace_root_clutter(ws):
    _clean_project(ws)
    (ws / "old.zip").write_bytes(b""); (ws / "paper.pdf").write_bytes(b""); (ws / "tmp_bench").mkdir()
    _, msgs, _ = _run(ws)
    for n in ("old.zip", "paper.pdf", "tmp_bench"):
        assert any(n in m for m in msgs)


def test_workspace_manifest_missing_file_is_error(ws):
    _clean_project(ws)
    (ws / "lint.toml").unlink()
    _, msgs, f = _run(ws)
    hit = [x for x in f if "lint.toml" in x["message"] and "manifest" in x["message"]]
    assert hit and hit[0]["severity"] == "error"


def test_kill_criterion_without_threshold_is_error(ws):
    run_cli(["new", "k"], cwd=ws)
    _, msgs, f = _run(ws)
    hit = [x for x in f if "states no threshold" in x["message"]]
    assert hit and hit[0]["severity"] == "error"


def test_scoring_without_control_and_ceiling_rows(ws):
    p = _clean_project(ws)
    (p / "spec" / "scoring.md").write_text("# Scoring\n\nStatus: frozen, 2026-09-10.\n\n| condition | m |\n|---|---|\n| method | |\n")
    _commit_all(p)
    _, msgs, _ = _run(ws)
    assert any("no `control` row" in m for m in msgs) and any("no `ceiling` row" in m for m in msgs)


def test_reports_before_frozen_scoring_warns(ws):
    p = _clean_project(ws)
    (p / "research" / "PILOT_2026-09-10.md").write_text("# Pilot\n\nArchetype: B, experiment report.\n")
    _commit_all(p)
    _, msgs, _ = _run(ws)
    assert any("still proposed" in m for m in msgs)


def test_code_without_component_spec_warns(ws):
    p = _clean_project(ws)
    (p / "seam").mkdir(); (p / "seam" / "scorer.py").write_text("x = 1\n")
    (p / "tests" / "test_x.py").write_text("def test(): pass\n")
    _commit_all(p)
    _, msgs, _ = _run(ws)
    assert any("code without a spec is a probe" in m for m in msgs)
    (p / "spec" / "scorer.md").write_text("# Scorer\n\nStatus: frozen, 2026-09-10.\n")
    _commit_all(p)
    _, msgs, _ = _run(ws)
    assert not any("code without a spec" in m for m in msgs)

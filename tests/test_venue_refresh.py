import datetime as dt
import json
import subprocess

from conftest import run_cli
from venue_helpers import venue_index_repo, point_workspace_at, make_project
from rharness import venue as V
from rharness.lintcfg import load_lint_config
from rharness.workspace import Workspace


def _setup(ws, tmp_path, monkeypatch):
    env, index, repo = venue_index_repo(tmp_path)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    point_workspace_at(ws, index)
    p = make_project(ws)
    code, out, err = run_cli(["venue", "add", "testconf2026"], cwd=p, env=env)
    assert code == 0, err
    return env, index, repo, p


def _age_block(p, days):
    pm = json.loads((p / ".rharness" / "project.json").read_text())
    old = (dt.datetime.now().astimezone() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    pm["venue"]["fetched"] = old
    (p / ".rharness" / "project.json").write_text(json.dumps(pm, indent=2, sort_keys=True) + "\n")


def _bump_upstream(repo, change_checks=False):
    vj = repo / "venues" / "testconf2026" / "venue.json"
    d = json.loads(vj.read_text()); d["revision"] = "2026-10-01"; d["page_limit"]["main"] = 3
    vj.write_text(json.dumps(d, indent=2) + "\n")
    (repo / "venues" / "testconf2026" / "agents.md").write_text("## Venue: testconf2026\n\n- updated upstream\n")
    if change_checks:
        (repo / "venues" / "testconf2026" / "checks.py").write_text("def check(project_dir, venue):\n    return [('warning', 'x', 'v2 check')]\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "bump"], cwd=repo, check=True)


def test_fresh_cache_is_not_checked(ws, tmp_path, home, monkeypatch):
    env, index, repo, p = _setup(ws, tmp_path, monkeypatch)
    _bump_upstream(repo)
    wsobj = Workspace.open(override=ws)
    r = V.refresh_if_stale(wsobj, p, load_lint_config(ws / "lint.toml"))
    assert r["status"] == "fresh"


def test_stale_targeted_index_package_auto_updates(ws, tmp_path, home, monkeypatch):
    env, index, repo, p = _setup(ws, tmp_path, monkeypatch)
    _age_block(p, 2)
    wsobj = Workspace.open(override=ws)
    r = V.refresh_if_stale(wsobj, p, load_lint_config(ws / "lint.toml"))
    assert r["status"] == "unchanged", r   # upstream tip equals the cached commit: only the stamp moves
    assert V._age_days(V.read_block(p)["fetched"]) == 0
    _age_block(p, 2)
    _bump_upstream(repo, change_checks=True)
    r = V.refresh_if_stale(wsobj, p, load_lint_config(ws / "lint.toml"))
    assert r["status"] == "updated", r
    assert json.loads((V.package_dir("testconf2026") / "venue.json").read_text())["page_limit"]["main"] == 3
    assert "v2 check" in (V.package_dir("testconf2026") / "checks.py").read_text()
    assert "updated upstream" in (p / "AGENTS.md").read_text()
    blk = V.read_block(p)
    assert blk["commit"] != "" and blk["tree"]
    backups = list((home / ".rharness" / "backup").rglob("venue.json"))
    assert backups, "old package must be backed up"


def test_stale_locked_package_reports_available_and_update_applies(ws, tmp_path, home, monkeypatch):
    env, index, repo, p = _setup(ws, tmp_path, monkeypatch)
    run_cli(["venue", "lock"], cwd=p, env=env)
    _age_block(p, 2)
    _bump_upstream(repo)
    wsobj = Workspace.open(override=ws)
    r = V.refresh_if_stale(wsobj, p, load_lint_config(ws / "lint.toml"))
    assert r["status"] == "available", r
    assert json.loads((V.package_dir("testconf2026") / "venue.json").read_text())["page_limit"]["main"] == 2
    code, out, err = run_cli(["venue"], cwd=p, env=env)
    assert "update available" in out
    code, out, err = run_cli(["venue", "update"], cwd=p, env=env)
    assert code == 0, err
    assert json.loads((V.package_dir("testconf2026") / "venue.json").read_text())["page_limit"]["main"] == 3


def test_non_index_source_holds_code_until_update(ws, tmp_path, home, monkeypatch):
    env, index, repo, p = _setup(ws, tmp_path, monkeypatch)
    (ws / "lint.toml").write_text('venue_index = "other/place/venues"\n')  # the installed source is now foreign
    _age_block(p, 2)
    _bump_upstream(repo, change_checks=True)
    wsobj = Workspace.open(override=ws)
    r = V.refresh_if_stale(wsobj, p, load_lint_config(ws / "lint.toml"))
    assert r["status"] == "code-held", r
    assert json.loads((V.package_dir("testconf2026") / "venue.json").read_text())["page_limit"]["main"] == 3
    assert "v2 check" not in (V.package_dir("testconf2026") / "checks.py").read_text()
    code, out, err = run_cli(["venue", "update"], cwd=p, env=env)
    assert code == 1 and "checks.py" in out and "--yes" in out
    code, out, err = run_cli(["--yes", "venue", "update"], cwd=p, env=env)
    assert code == 0, err
    assert "v2 check" in (V.package_dir("testconf2026") / "checks.py").read_text()


def test_pinned_never_refreshes(ws, tmp_path, home, monkeypatch):
    env, index, repo, p = _setup(ws, tmp_path, monkeypatch)
    run_cli(["--yes", "venue", "remove"], cwd=p, env=env)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    code, out, err = run_cli(["--yes", "venue", "add", f"{index}/testconf2026@{sha}"], cwd=p, env=env)
    assert code == 0, err
    assert V.read_block(p)["ref"] == sha
    _age_block(p, 3)
    _bump_upstream(repo)
    r = V.refresh_if_stale(Workspace.open(override=ws), p, load_lint_config(ws / "lint.toml"))
    assert r["status"] == "pinned"


def test_offline_is_silent(ws, tmp_path, home, monkeypatch):
    env, index, repo, p = _setup(ws, tmp_path, monkeypatch)
    _age_block(p, 2)
    monkeypatch.setenv("RHARNESS_GITHUB_BASE", "file:///nonexistent/")
    r = V.refresh_if_stale(Workspace.open(override=ws), p, load_lint_config(ws / "lint.toml"))
    assert r["status"] == "offline"


def test_change_swaps_packages(ws, tmp_path, home, monkeypatch):
    import shutil
    env, index, repo, p = _setup(ws, tmp_path, monkeypatch)
    # second venue in the same index
    src = repo / "venues" / "testconf2026"; dst = repo / "venues" / "otherconf2027"
    shutil.copytree(src, dst)
    vj = json.loads((dst / "venue.json").read_text())
    vj.update(venue="otherconf", cycle="2027", name="otherconf2027")
    vj["template"]["files"] = ["testconf2026.sty"]
    (dst / "venue.json").write_text(json.dumps(vj) + "\n")
    pj = json.loads((dst / "plugin.json").read_text()); pj["name"] = "otherconf2027"
    (dst / "plugin.json").write_text(json.dumps(pj) + "\n")
    (dst / "project-files" / "research" / "venue-otherconf2027.md").write_text("# other\n")
    (dst / "project-files" / "research" / "venue-testconf2026.md").unlink()
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "second venue"], cwd=repo, check=True)
    (p / "paper" / "testconf2026.sty").write_text("% edited by user\n")
    code, out, err = run_cli(["venue", "change", "otherconf", "2027"], cwd=p, env=env)
    assert code == 1 and "If you are an agent" in out
    code, out, err = run_cli(["--yes", "venue", "change", "otherconf", "2027"], cwd=p, env=env)
    assert code == 0, err
    assert "kept paper/testconf2026.sty" in out
    assert (p / "paper" / "testconf2026.sty").read_text() == "% edited by user\n"
    assert V.read_block(p)["name"] == "otherconf2027" and V.read_block(p)["state"] == "targeted"
    assert not (p / "research" / "venue-testconf2026.md").exists()
    assert (p / "research" / "venue-otherconf2027.md").exists()
    ch = (p / "CHARTER.md").read_text()
    assert "venue changed from testconf2026 to otherconf2027" in ch
    assert "otherconf2027 (targeted)" in (ws / "AGENTS.md").read_text()


def test_list_uses_index_and_cache(ws, tmp_path, home, monkeypatch):
    env, index, repo, p = _setup(ws, tmp_path, monkeypatch)
    code, out, err = run_cli(["venue", "list"], cwd=ws, env=env)
    assert code == 0, err
    assert "testconf2026" in out and "2027-06-08" in out
    monkeypatch.setenv("RHARNESS_GITHUB_BASE", "file:///nonexistent/")
    code, out, err = run_cli(["venue", "list"], cwd=ws, env={"RHARNESS_GITHUB_BASE": "file:///nonexistent/"})
    assert code == 0 and "testconf2026" in out and "cached" in out

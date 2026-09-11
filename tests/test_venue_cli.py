import json
import subprocess

from conftest import run_cli
from venue_helpers import venue_index_repo, point_workspace_at, make_project


def _setup(ws, tmp_path):
    env, index, repo = venue_index_repo(tmp_path)
    point_workspace_at(ws, index)
    p = make_project(ws)
    return env, index, repo, p


def test_add_from_workspace_root_off_tty_refuses(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    code, out, err = run_cli(["venue", "add", "testconf", "2026"], cwd=ws, env=env)
    assert code == 2 and "--project" in err and "seam" in err


def test_add_inside_project_and_status(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    code, out, err = run_cli(["venue", "add", "testconf", "2026"], cwd=p, env=env)
    assert code == 0, err
    assert "Installed venue testconf2026" in out and "targeted" in out
    assert "expected to be open" in out and "Overleaf" in out
    pm = json.loads((p / ".rharness" / "project.json").read_text())
    assert pm["venue"]["name"] == "testconf2026" and pm["venue"]["state"] == "targeted"
    assert (p / "paper" / "testconf2026.sty").exists()
    code, out, err = run_cli(["venue"], cwd=p, env=env)
    assert code == 0, err
    assert out.startswith("Venue: testconf2026 (targeted)")
    assert "full" in out and "2027-06-08" in out and "primary" in out
    assert "Checks:" in out and "does not load testconf2026" in out
    # a second add is refused
    code, out, err = run_cli(["venue", "add", "testconf2026"], cwd=p, env=env)
    assert code == 1 and "venue change" in err


def test_add_with_project_flag_from_root(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    code, out, err = run_cli(["venue", "add", "testconf2026", "--project", "seam"], cwd=ws, env=env)
    assert code == 0, err
    code, out, err = run_cli(["venue", "add", "testconf2026", "--project", "nope"], cwd=ws, env=env)
    assert code == 2 and "not a project" in err


def test_add_unknown_venue_is_error(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    code, out, err = run_cli(["venue", "add", "nosuch", "2030"], cwd=p, env=env)
    assert code == 2 and "nosuch2030" in err


def test_add_from_non_index_source_needs_confirmation(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    (ws / "lint.toml").write_text('venue_index = "other/place/venues"\n')
    code, out, err = run_cli(["venue", "add", f"{index}/testconf2026"], cwd=p, env=env)
    assert code == 1 and "checks.py" in out and "--yes" in out
    assert not (p / "paper" / "testconf2026.sty").exists()
    code, out, err = run_cli(["--yes", "venue", "add", f"{index}/testconf2026"], cwd=p, env=env)
    assert code == 0, err


def test_lock_unlock_and_remove(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    run_cli(["venue", "add", "testconf2026"], cwd=p, env=env)
    code, out, err = run_cli(["venue", "lock"], cwd=p, env=env)
    assert code == 0, err
    assert "warning" in out and "NOT YET" in out  # success criterion warning, not a refusal
    pm = json.loads((p / ".rharness" / "project.json").read_text())
    assert pm["venue"]["state"] == "locked" and pm["venue"]["locked_on"]
    ch = (p / "CHARTER.md").read_text()
    assert "venue testconf2026 locked" in ch
    assert "testconf2026 (locked)" in (ws / "AGENTS.md").read_text()
    # unlock off a TTY needs --yes
    code, out, err = run_cli(["venue", "unlock"], cwd=p, env=env)
    assert code == 1 and "If you are an agent" in out and "rharness --yes venue unlock" in out
    code, out, err = run_cli(["--yes", "venue", "unlock"], cwd=p, env=env)
    assert code == 0, err
    assert json.loads((p / ".rharness" / "project.json").read_text())["venue"]["state"] == "targeted"
    code, out, err = run_cli(["venue", "remove"], cwd=p, env=env)
    assert code == 1
    code, out, err = run_cli(["--yes", "venue", "remove"], cwd=p, env=env)
    assert code == 0, err
    assert "venue" not in json.loads((p / ".rharness" / "project.json").read_text())
    assert "venue testconf2026 removed" in (p / "CHARTER.md").read_text()


def test_status_without_venue(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    code, out, err = run_cli(["venue"], cwd=p, env=env)
    assert code == 0 and "No venue" in out and "rharness venue add" in out


def test_list_hides_project_scoped_packages_from_plugin_list(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    run_cli(["venue", "add", "testconf2026"], cwd=p, env=env)
    code, out, err = run_cli(["list"], cwd=ws, env=env)
    assert code == 0
    assert "testconf2026" not in out


def test_project_flag_before_the_subcommand(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    code, out, err = run_cli(["venue", "--project", "seam", "add", "testconf2026"], cwd=ws, env=env)
    assert code == 0, err
    code, out, err = run_cli(["venue", "--project", "seam", "lock"], cwd=ws, env=env)
    assert code == 0, err
    assert "Locked testconf2026 on seam" in out
    code, out, err = run_cli(["venue", "unlock", "--project", "seam", "--yes"], cwd=ws, env=env)
    assert code == 2  # --yes is a global flag, before the subcommand
    code, out, err = run_cli(["--yes", "venue", "unlock", "--project", "seam"], cwd=ws, env=env)
    assert code == 0, err
    assert "Unlocked testconf2026 on seam" in out


def test_add_by_full_index_spec_needs_no_confirmation(ws, tmp_path, home):
    env, index, repo, p = _setup(ws, tmp_path)
    code, out, err = run_cli(["venue", "add", f"{index}/testconf2026"], cwd=p, env=env)
    assert code == 0, err
    assert "Installed venue testconf2026" in out
    assert (p / "paper" / "testconf2026.sty").exists()

import json
import shutil
import subprocess

from conftest import run_cli
from venue_helpers import venue_index_repo, point_workspace_at, make_project

from rharness import venue as V


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


def _commit(repo, msg="fixture change"):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True, capture_output=True)


def _second_venue(repo, name="otherconf2027"):
    """Copy the fixture into the index under a new, self-consistent name."""
    src, dst = repo / "venues" / "testconf2026", repo / "venues" / name
    shutil.copytree(src, dst)
    vj = json.loads((dst / "venue.json").read_text())
    vj.update(venue=name[:-4], cycle=name[-4:], name=name)
    vj["template"]["files"] = ["testconf2026.sty"]
    (dst / "venue.json").write_text(json.dumps(vj) + "\n")
    pj = json.loads((dst / "plugin.json").read_text())
    pj["name"] = name
    (dst / "plugin.json").write_text(json.dumps(pj) + "\n")
    _commit(repo, "second venue")
    return name


def test_index_relative_escape_is_refused(ws, tmp_path, home):
    """C1: <index>/../name escapes the index; it must be rejected, not silently trusted."""
    env, index, repo, p = _setup(ws, tmp_path)
    # a real package outside the index directory, reachable only through ..
    shutil.copytree(repo / "venues" / "testconf2026", repo / "testconf2026")
    _commit(repo, "package outside the index")
    code, out, err = run_cli(["venue", "add", f"{index}/../testconf2026"], cwd=p, env=env)
    assert code == 2, (code, out, err)
    assert "must not contain '..'" in err
    assert V.read_block(p) is None
    assert not (p / "paper" / "testconf2026.sty").exists()
    assert not (home / ".rharness" / "plugins" / "testconf2026").exists()


def test_add_refuses_a_package_that_declares_another_name(ws, tmp_path, home):
    """C2: a package at <index>/impostor2026 declaring testconf2026 must not be cached as it."""
    env, index, repo, p = _setup(ws, tmp_path)
    shutil.copytree(repo / "venues" / "testconf2026", repo / "venues" / "impostor2026")
    _commit(repo, "impostor")
    legit = home / ".rharness" / "plugins" / "testconf2026"
    assert not legit.exists()
    code, out, err = run_cli(["venue", "add", "impostor2026"], cwd=p, env=env)
    assert code == 2, (code, out, err)
    assert "impostor2026" in err and "testconf2026" in err
    assert not legit.exists()
    assert V.read_block(p) is None


def test_impostor_does_not_clobber_an_existing_cache(ws, tmp_path, home):
    """C2: nothing reaches ~/.rharness/plugins until the package has passed validation."""
    from rharness.plugin import tree_hash
    env, index, repo, p = _setup(ws, tmp_path)
    code, out, err = run_cli(["venue", "add", "testconf2026"], cwd=p, env=env)
    assert code == 0, err
    legit = home / ".rharness" / "plugins" / "testconf2026"
    before = tree_hash(legit)
    shutil.copytree(repo / "venues" / "testconf2026", repo / "venues" / "impostor2026")
    (repo / "venues" / "impostor2026" / "checks.py").write_text(
        "def check(project_dir, venue):\n    return [('error', 'x', 'impostor code ran')]\n")
    _commit(repo, "impostor")
    other = make_project(ws, slug="other")
    code, out, err = run_cli(["venue", "add", "impostor2026"], cwd=other, env=env)
    assert code == 2, (code, out, err)
    assert "impostor2026" in err and "testconf2026" in err
    assert tree_hash(legit) == before
    assert "impostor code ran" not in (legit / "checks.py").read_text()


def test_change_to_an_unknown_venue_keeps_the_old_one(ws, tmp_path, home):
    """C3: a failed change must not leave the project venue-less."""
    env, index, repo, p = _setup(ws, tmp_path)
    code, out, err = run_cli(["venue", "add", "testconf2026"], cwd=p, env=env)
    assert code == 0, err
    code, out, err = run_cli(["--yes", "venue", "change", "nosuch", "2030"], cwd=p, env=env)
    assert code == 2, (code, out, err)
    assert "nosuch2030" in err
    assert V.read_block(p)["name"] == "testconf2026"
    assert (p / "paper" / "testconf2026.sty").exists()
    row = next(l for l in (ws / "AGENTS.md").read_text().splitlines() if l.startswith("| `seam/` |"))
    assert "testconf2026" in row.split("|")[3]
    assert "venue changed from" not in (p / "CHARTER.md").read_text()


def test_change_to_a_non_index_source_without_yes_keeps_the_old_one(ws, tmp_path, home):
    """C3: consent for foreign code is asked before anything is removed."""
    env, index, repo, p = _setup(ws, tmp_path)
    other = _second_venue(repo)
    code, out, err = run_cli(["venue", "add", "testconf2026"], cwd=p, env=env)
    assert code == 0, err
    (ws / "lint.toml").write_text('venue_index = "other/place/venues"\n')
    code, out, err = run_cli(["venue", "change", f"{index}/{other}"], cwd=p, env=env)
    assert code == 1, (code, out, err)
    assert "checks.py" in out and "--yes" in out
    assert V.read_block(p)["name"] == "testconf2026"
    assert (p / "paper" / "testconf2026.sty").exists()


def test_add_without_the_style_marker_says_so(ws, tmp_path, home):
    """I4: upgraded projects have no % rharness:venue-style line."""
    env, index, repo, p = _setup(ws, tmp_path)
    main = p / "paper" / "main.tex"
    main.write_text("\n".join(l for l in main.read_text().splitlines()
                              if "rharness:venue-style" not in l) + "\n")
    code, out, err = run_cli(["venue", "add", "testconf2026"], cwd=p, env=env)
    assert code == 0, err
    assert "no % rharness:venue-style marker" in out
    assert "add the \\usepackage line to the preamble yourself" in out

import json
from conftest import run_cli


def _legacy_workspace(root):
    root.mkdir(parents=True)
    (root / "AGENTS.md").write_text(
        "# My workspace\n\nHand-written intro.\n\n| dir | paper | venue target | status |\n"
        "|---|---|---|---|\n| `p1/` | Paper One | ACL | drafting |\n")
    p1 = root / "p1"; (p1 / "handoff").mkdir(parents=True)
    (p1 / "CHARTER.md").write_text("# Charter p1\n\n## Kill Criterion\n\n**Status:** NOT TRIGGERED\n")
    (p1 / "AGENTS.md").write_text("# p1 agents\n")
    p2 = root / "p2"; p2.mkdir()
    (p2 / "AGENTS.md").write_text("# p2 agents\n")
    (root / "figures").mkdir(); (root / "figures" / "x.py").write_text("")
    return root


def test_adopt_workspace_adds_missing_never_overwrites(tmp_path, home):
    root = _legacy_workspace(tmp_path / "research")
    code, out, err = run_cli(["adopt", str(root)], cwd=tmp_path)
    assert code == 0, err
    agents = (root / "AGENTS.md").read_text()
    assert agents.startswith("# My workspace")
    assert "<!-- rharness:begin base -->" in agents
    assert "| `p2/` | p2 | TBD | adopted" in agents
    assert agents.count("| `p1/` |") == 1
    assert (root / "CLAUDE.md").exists() and (root / "lint.toml").exists()
    assert (root / "p1" / "CHARTER.md").read_text().startswith("# Charter p1")
    assert (root / "p1" / "spec" / "scoring.md").exists()
    assert (root / "p2" / "CHARTER.md").exists()
    assert not (root / "figures" / "CHARTER.md").exists()
    m = json.loads((root / ".rharness" / "manifest.json").read_text())
    assert m["files"]["AGENTS.md"]["owner"] == "user"
    assert m["files"]["AGENTS.md"]["region"] is True
    assert sorted(m["projects"]) == ["p1", "p2"]
    pm = json.loads((root / "p1" / ".rharness" / "project.json").read_text())
    assert pm["files"]["CHARTER.md"]["owner"] == "user"
    assert pm["files"]["spec/scoring.md"]["owner"] == "base"
    assert "added" in out and "kept" in out
    assert (root / ".rharness" / "archetypes" / "A-method-spec.md").exists()


def test_adopt_is_repeatable(tmp_path, home):
    root = _legacy_workspace(tmp_path / "research")
    run_cli(["adopt", str(root)], cwd=tmp_path)
    (root / "p1" / "spec" / "scoring.md").write_text("edited")
    code, out, err = run_cli(["adopt", str(root)], cwd=tmp_path)
    assert code == 0, err
    assert (root / "p1" / "spec" / "scoring.md").read_text() == "edited"
    assert (root / "AGENTS.md").read_text().count("rharness:begin base") == 1


def test_adopt_projects_filter(tmp_path, home):
    root = _legacy_workspace(tmp_path / "research")
    code, out, err = run_cli(["adopt", str(root), "--projects", "p1"], cwd=tmp_path)
    assert code == 0, err
    assert (root / "p1" / "spec").exists() and not (root / "p2" / "spec").exists()


def test_adopt_single_project_inside_workspace(ws):
    p = ws / "legacy"; p.mkdir()
    (p / "CHARTER.md").write_text("# legacy\n")
    code, out, err = run_cli(["adopt", "legacy"], cwd=ws)
    assert code == 0, err
    assert (p / "AGENTS.md").exists() and (p / ".rharness" / "project.json").exists()
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert m["projects"] == ["legacy"]
    assert "| `legacy/` |" in (ws / "AGENTS.md").read_text()


def test_adopt_single_project_standalone(tmp_path, home):
    p = tmp_path / "solo"; p.mkdir()
    (p / "AGENTS.md").write_text("# solo\n")
    code, out, err = run_cli(["adopt", str(p)], cwd=tmp_path)
    assert code == 0, err
    assert (p / "CHARTER.md").exists()
    assert not (tmp_path / ".rharness").exists()


def test_adopt_empty_dir_is_error(tmp_path, home):
    d = tmp_path / "empty"; d.mkdir()
    code, out, err = run_cli(["adopt", str(d)], cwd=tmp_path)
    assert code == 1 and "nothing to adopt" in err


def test_adopt_dry_run(tmp_path, home):
    root = _legacy_workspace(tmp_path / "research")
    code, out, err = run_cli(["--dry-run", "adopt", str(root)], cwd=tmp_path)
    assert code == 0 and not (root / ".rharness").exists() and "would" in out

import json, re
from conftest import run_cli
from rharness import gitutil


def test_new_scaffolds_project(ws):
    code, out, err = run_cli(["new", "seam", "--title", "SEAM: paste boundaries"], cwd=ws)
    assert code == 0, err
    p = ws / "seam"
    for rel in ["CHARTER.md", "AGENTS.md", "README.md", "spec/scoring.md", "paper/writing.md",
                ".gitattributes", "handoff/README.md", "changelog/README.md", "tests/.gitkeep"]:
        assert (p / rel).exists(), rel
    assert "SEAM: paste boundaries" in (p / "CHARTER.md").read_text()
    assert "{{" not in (p / "CHARTER.md").read_text()
    assert gitutil.is_repo(p)
    handoffs = [f.name for f in (p / "handoff").iterdir() if re.match(r"\d{4}-\d{2}-\d{2}\.md", f.name)]
    assert len(handoffs) == 1
    assert "Read AGENTS.md first" in (p / "handoff" / handoffs[0]).read_text()
    pm = json.loads((p / ".rharness" / "project.json").read_text())
    assert pm["ctx"] == {"slug": "seam", "title": "SEAM: paste boundaries"}
    assert pm["files"]["CHARTER.md"]["source"] == "base/project/CHARTER.md"
    wm = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert wm["projects"] == ["seam"]
    agents = (ws / "AGENTS.md").read_text()
    assert "| `seam/` | SEAM: paste boundaries | TBD | scaffolded" in agents
    assert (ws / ".rharness" / "archetypes" / "B-experiment-report.md").exists()


def test_new_default_title_is_slug(ws):
    code, out, err = run_cli(["new", "rank-validity"], cwd=ws)
    assert code == 0, err
    assert "# Project Charter — rank-validity" in (ws / "rank-validity" / "CHARTER.md").read_text()


def test_new_refuses_existing_dir(ws):
    (ws / "seam").mkdir()
    code, out, err = run_cli(["new", "seam"], cwd=ws)
    assert code == 1 and "exists" in err


def test_new_rejects_bad_slug(ws):
    code, out, err = run_cli(["new", "Bad Slug!"], cwd=ws)
    assert code == 2


def test_new_outside_workspace_fails(tmp_path, home):
    code, out, err = run_cli(["new", "x"], cwd=tmp_path)
    assert code == 2 and "workspace" in err


def test_new_from_subdir_finds_workspace(ws):
    sub = ws / "notes"; sub.mkdir()
    code, out, err = run_cli(["new", "x"], cwd=sub)
    assert code == 0, err
    assert (ws / "x" / "CHARTER.md").exists()


def test_new_dry_run(ws):
    code, out, err = run_cli(["--dry-run", "new", "seam"], cwd=ws)
    assert code == 0 and not (ws / "seam").exists() and "CHARTER.md" in out


def test_new_project_has_claude_include_and_rules_region(ws):
    run_cli(["new", "seam"], cwd=ws)
    assert (ws / "seam" / "CLAUDE.md").read_text().strip() == "@AGENTS.md"
    agents = (ws / "seam" / "AGENTS.md").read_text()
    assert "<!-- rharness:begin base -->" in agents and "rharness brief" in agents
    pm = json.loads((ws / "seam" / ".rharness" / "project.json").read_text())
    assert pm["files"]["AGENTS.md"]["region"] is True


def test_new_codex_only_project_has_no_claude_md(tmp_path, home):
    root = tmp_path / "r"
    run_cli(["init", str(root), "--harness", "codex", "--no-plugins"], cwd=tmp_path)
    code, out, err = run_cli(["new", "seam"], cwd=root)
    assert code == 0, err
    assert not (root / "seam" / "CLAUDE.md").exists()

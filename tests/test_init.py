import json
from conftest import run_cli


def test_init_creates_workspace(tmp_path, home):
    root = tmp_path / "research"
    code, out, err = run_cli(["init", str(root), "--no-plugins"], cwd=tmp_path)
    assert code == 0, err
    assert (root / "AGENTS.md").exists()
    assert (root / "CLAUDE.md").read_text().strip() == "@AGENTS.md"
    assert (root / "lint.toml").exists()
    m = json.loads((root / ".rharness" / "manifest.json").read_text())
    assert m["harness"] == ["claude", "codex"]
    assert set(m["files"]) == {"AGENTS.md", "CLAUDE.md", "lint.toml"}
    assert m["files"]["AGENTS.md"]["region"] is True
    assert m["files"]["AGENTS.md"]["source"] == "base/workspace/AGENTS.md"
    assert "<!-- rharness:begin base -->" in (root / "AGENTS.md").read_text()
    assert "Created workspace" in out


def test_init_default_dir_is_cwd(tmp_path, home):
    code, out, err = run_cli(["init", "--no-plugins"], cwd=tmp_path)
    assert code == 0, err
    assert (tmp_path / ".rharness" / "manifest.json").exists()


def test_init_refuses_existing_workspace(ws, tmp_path):
    code, out, err = run_cli(["init", str(ws), "--no-plugins"], cwd=tmp_path)
    assert code == 1
    assert "adopt" in err


def test_init_harness_flag(tmp_path, home):
    root = tmp_path / "r"
    code, out, err = run_cli(["init", str(root), "--harness", "codex", "--no-plugins"], cwd=tmp_path)
    assert code == 0, err
    m = json.loads((root / ".rharness" / "manifest.json").read_text())
    assert m["harness"] == ["codex"]
    assert not (root / "CLAUDE.md").exists()


def test_init_bad_harness(tmp_path, home):
    code, out, err = run_cli(["init", str(tmp_path / "r"), "--harness", "cursor"], cwd=tmp_path)
    assert code == 2 and "cursor" in err


def test_init_dry_run_writes_nothing(tmp_path, home):
    root = tmp_path / "r"
    code, out, err = run_cli(["--dry-run", "init", str(root), "--no-plugins"], cwd=tmp_path)
    assert code == 0, err
    assert not root.exists()
    assert "AGENTS.md" in out

import subprocess
from pathlib import Path
import pytest
from rharness import gitutil
from rharness.manifest import Manifest
from rharness.workspace import Workspace, NotAWorkspace, find_root, detect_projects


def _git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


def test_gitutil_on_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t"); monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@x")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t"); monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@x")
    r = _git_repo(tmp_path / "r")
    assert gitutil.is_repo(r) and not gitutil.is_repo(tmp_path)
    assert gitutil.commit_count(r) == 0
    assert gitutil.newest_commit_date(r) is None
    (r / "a").write_text("a")
    assert gitutil.dirty_count(r) == 1
    gitutil.git(["add", "a"], r); gitutil.git(["commit", "-q", "-m", "a"], r)
    assert gitutil.commit_count(r) == 1
    assert gitutil.dirty_count(r) == 0
    d = gitutil.newest_commit_date(r)
    assert len(d) == 10 and d[4] == "-"
    assert d in gitutil.commit_days(r, 14)
    (r / ".gitignore").write_text(".env\n")
    (r / ".env").write_text("K=1")
    assert gitutil.is_ignored(r, ".env")
    assert not gitutil.is_ignored(r, "a")


def test_gitutil_never_raises_outside_repo(tmp_path):
    assert gitutil.commit_count(tmp_path) == 0
    assert gitutil.dirty_count(tmp_path) == 0
    assert gitutil.newest_commit_date(tmp_path) is None


def test_find_root_walks_up(tmp_path):
    root = tmp_path / "ws"
    Manifest.new(root / ".rharness" / "manifest.json", "0.1.0").save()
    deep = root / "a" / "b"; deep.mkdir(parents=True)
    assert find_root(deep) == root
    assert find_root(tmp_path) is None


def test_workspace_open_and_props(tmp_path):
    root = tmp_path / "ws"
    Manifest.new(root / ".rharness" / "manifest.json", "0.1.0", harness=("codex",)).save()
    w = Workspace.open(start=root)
    assert w.root == root
    assert w.agents_path == root / "AGENTS.md"
    assert w.claude_md_path == root / "CLAUDE.md"
    assert w.settings_path == root / ".claude" / "settings.json"
    assert w.wants("codex") and not w.wants("claude")
    with pytest.raises(NotAWorkspace):
        Workspace.open(start=tmp_path)
    assert Workspace.open(start=tmp_path, override=root).root == root


def test_detect_projects(tmp_path):
    (tmp_path / "p1").mkdir(); (tmp_path / "p1" / "CHARTER.md").write_text("")
    (tmp_path / "p2").mkdir(); (tmp_path / "p2" / "AGENTS.md").write_text("")
    _git_repo(tmp_path / "p3")
    (tmp_path / "figures").mkdir(); (tmp_path / "figures" / "x.py").write_text("")
    (tmp_path / ".hidden").mkdir(); (tmp_path / ".hidden" / "CHARTER.md").write_text("")
    (tmp_path / "_archive").mkdir(); (tmp_path / "_archive" / "CHARTER.md").write_text("")
    names = [p.name for p in detect_projects(tmp_path)]
    assert names == ["p1", "p2", "p3"]

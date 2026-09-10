"""Installing plugins from outside the built-in set: local paths, git URLs, GitHub shorthand."""
import json
import os
import subprocess
from pathlib import Path

from conftest import run_cli


def _make_plugin(root: Path, name: str, rule="External rule."):
    d = root / name
    (d / "files" / name).mkdir(parents=True)
    (d / "project-files" / "tools").mkdir(parents=True)
    (d / "plugin.json").write_text(json.dumps({
        "name": name, "description": "external test plugin", "version": "0.0.1",
        "harness": ["claude", "codex"], "requires": {"binaries": [], "python": ">=3.9"}}))
    (d / "agents.md").write_text(f"## {name}\n\n- {rule}\n")
    (d / "files" / name / "tool.py").write_text(f"print('{name} {{{{workspace}}}}')\n")
    (d / "project-files" / "tools" / f"{name}_helper.py").write_text(f"# {name} for {{{{slug}}}}\n")
    return d


def _git_repo(path: Path):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "plugin"], cwd=path, check=True)
    return path


def test_add_from_local_path(ws, tmp_path, home):
    src = _make_plugin(tmp_path / "ext", "extra")
    code, out, err = run_cli(["--yes", "add", str(src)], cwd=ws)
    assert code == 0, err
    assert (ws / "extra" / "tool.py").read_text() == f"print('extra {ws}')\n"
    assert "External rule." in (ws / "AGENTS.md").read_text()
    store = home / ".rharness" / "plugins" / "extra"
    assert (store / "plugin.json").exists()
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert m["plugins"] == ["extra"]
    assert m["plugin_sources"]["extra"] == str(src)
    assert m["files"]["extra/tool.py"]["source"] == "plugins/extra/files/extra/tool.py"


def test_add_from_git_url(ws, tmp_path, home):
    repo = _git_repo(_make_plugin(tmp_path / "repos", "gitplug"))
    url = f"file://{repo}"
    code, out, err = run_cli(["--yes", "add", url], cwd=ws)
    assert code == 0, err
    assert (ws / "gitplug" / "tool.py").exists()
    assert (home / ".rharness" / "plugins" / "gitplug" / "agents.md").exists()
    assert not (home / ".rharness" / "plugins" / "gitplug" / ".git").exists()
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert m["plugin_sources"]["gitplug"] == url


def test_add_github_shorthand_with_subdir(ws, tmp_path, home):
    # owner/repo/subdir resolved against RHARNESS_GITHUB_BASE (a file:// dir in tests)
    base = tmp_path / "gh"
    repo = base / "alice" / "research-plugins"
    _make_plugin(repo / "plugins", "sub")
    (repo / "README.md").write_text("many plugins\n")
    _git_repo(repo)
    env = {"RHARNESS_GITHUB_BASE": f"file://{base}/"}
    code, out, err = run_cli(["--yes", "add", "alice/research-plugins/plugins/sub"], cwd=ws, env=env)
    assert code == 0, err
    assert (ws / "sub" / "tool.py").exists()
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert m["plugin_sources"]["sub"] == "alice/research-plugins/plugins/sub"


def test_add_missing_plugin_json_is_error(ws, tmp_path):
    d = tmp_path / "notaplugin"; d.mkdir()
    (d / "agents.md").write_text("x")
    code, out, err = run_cli(["--yes", "add", str(d)], cwd=ws)
    assert code == 2 and "plugin.json" in err


def test_external_add_without_yes_shows_capabilities_and_refuses(ws, tmp_path, home):
    src = _make_plugin(tmp_path / "ext", "extra")
    (src / "setup.sh").write_text("#!/bin/sh\necho hi\n")
    (src / "claude").mkdir()
    (src / "claude" / "hooks.json").write_text(json.dumps(
        {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo spy"}]}]}))
    code, out, err = run_cli(["add", str(src)], cwd=ws)
    assert code == 1
    assert "Plugin extra from" in out
    assert "setup.sh: yes" in out and "hook PreToolUse: runs `echo spy`" in out
    assert "AGENTS.md section: yes" in out and "--yes" in out
    assert not (ws / "extra").exists()
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert m["plugins"] == [] and not (ws / ".claude" / "settings.json").exists() or "spy" not in (ws / ".claude" / "settings.json").read_text()


def test_builtin_add_needs_no_confirmation(ws):
    code, out, err = run_cli(["add", "ideas"], cwd=ws)
    assert code == 0, err and "Plugin ideas from" not in out


def test_add_pinned_to_tag_and_commit(ws, tmp_path, home):
    repo = _make_plugin(tmp_path / "repos", "pinned", rule="Version one.")
    _git_repo(repo)
    subprocess.run(["git", "tag", "v1"], cwd=repo, check=True)
    v1 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    (repo / "agents.md").write_text("## pinned\n\n- Version two.\n")
    subprocess.run(["git", "commit", "-q", "-am", "v2"], cwd=repo, check=True)
    url = f"file://{repo}"
    code, out, err = run_cli(["--yes", "add", f"{url}@v1"], cwd=ws)
    assert code == 0, err
    assert "Version one." in (ws / "AGENTS.md").read_text()
    assert f"commit {v1[:12]}" in out
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert m["plugin_sources"]["pinned"] == f"{url}@v1"
    code, out, err = run_cli(["list"], cwd=ws)
    assert f"@{v1[:12]}" in out
    code, out, err = run_cli(["--yes", "add", f"{url}@{v1}", "--refresh"], cwd=ws)
    assert code == 0, err and "Version one." in (ws / "AGENTS.md").read_text()
    code, out, err = run_cli(["--yes", "add", f"{url}@main", "--refresh"], cwd=ws)
    assert code == 0, err
    assert "Version two." in (ws / "AGENTS.md").read_text()


def test_add_pinned_to_missing_ref_fails(ws, tmp_path, home):
    repo = _git_repo(_make_plugin(tmp_path / "repos", "p2"))
    code, out, err = run_cli(["--yes", "add", f"file://{repo}@nope"], cwd=ws)
    assert code == 2 and "@nope" in err


def test_add_unknown_name_mentions_sources(ws):
    code, out, err = run_cli(["add", "nope"], cwd=ws)
    assert code == 2 and "owner/repo" in err


def test_external_plugin_applies_to_projects_and_update_reapplies(ws, tmp_path, home):
    src = _make_plugin(tmp_path / "ext", "extra")
    run_cli(["new", "seam"], cwd=ws)
    code, out, err = run_cli(["--yes", "add", str(src)], cwd=ws)
    assert code == 0, err
    helper = ws / "seam" / "tools" / "extra_helper.py"
    assert helper.read_text() == "# extra for seam\n"
    (ws / "extra" / "tool.py").unlink()
    code, out, err = run_cli(["update", "--no-fetch"], cwd=ws)
    assert code == 0, err
    assert (ws / "extra" / "tool.py").exists()
    assert "replaced extra/tool.py" in out


def test_refresh_refetches_from_source(ws, tmp_path, home):
    src = _make_plugin(tmp_path / "ext", "extra", rule="Version one.")
    run_cli(["--yes", "add", str(src)], cwd=ws)
    (src / "agents.md").write_text("## extra\n\n- Version two.\n")
    code, out, err = run_cli(["--yes", "add", str(src)], cwd=ws)
    assert code == 0, err
    assert "Version one." in (ws / "AGENTS.md").read_text()      # cached copy reused
    code, out, err = run_cli(["--yes", "add", str(src), "--refresh"], cwd=ws)
    assert code == 0, err
    assert "Version two." in (ws / "AGENTS.md").read_text()


def test_list_shows_origin_and_source(ws, tmp_path, home):
    src = _make_plugin(tmp_path / "ext", "extra")
    run_cli(["--yes", "add", str(src)], cwd=ws)
    code, out, err = run_cli(["list"], cwd=ws)
    assert code == 0, err
    lines = {l.split()[0]: l for l in out.splitlines() if l.strip()}
    assert "builtin" in lines["rtk"] and "available" in lines["rtk"]
    assert "user" in lines["extra"] and "installed" in lines["extra"] and str(src) in lines["extra"]


def test_plugin_new_scaffolds_installable_plugin(ws, tmp_path, home):
    code, out, err = run_cli(["plugin", "new", "mytools", "--dir", str(tmp_path)], cwd=ws)
    assert code == 0, err
    d = tmp_path / "mytools"
    for rel in ("plugin.json", "agents.md", "README.md", "files/mytools/README.md",
                "project-files/.gitkeep", "claude/skills/mytools/SKILL.md"):
        assert (d / rel).exists(), rel
    meta = json.loads((d / "plugin.json").read_text())
    assert meta["name"] == "mytools" and set(meta["harness"]) == {"claude", "codex"}
    assert "rharness add" in (d / "README.md").read_text()
    code, out, err = run_cli(["--yes", "add", str(d)], cwd=ws)
    assert code == 0, err
    assert (ws / "mytools" / "README.md").exists()
    assert (ws / ".claude" / "skills" / "mytools" / "SKILL.md").exists()


def test_plugin_new_rejects_bad_name_and_existing_dir(ws, tmp_path):
    code, out, err = run_cli(["plugin", "new", "Bad Name", "--dir", str(tmp_path)], cwd=ws)
    assert code == 2
    (tmp_path / "taken").mkdir()
    code, out, err = run_cli(["plugin", "new", "taken", "--dir", str(tmp_path)], cwd=ws)
    assert code == 1 and "exists" in err


def test_remove_external_plugin_keeps_cached_copy(ws, tmp_path, home):
    src = _make_plugin(tmp_path / "ext", "extra")
    run_cli(["--yes", "add", str(src)], cwd=ws)
    code, out, err = run_cli(["remove", "extra"], cwd=ws)
    assert code == 0, err
    assert not (ws / "extra").exists()
    assert (home / ".rharness" / "plugins" / "extra" / "plugin.json").exists()
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert "extra" not in m["plugin_sources"]

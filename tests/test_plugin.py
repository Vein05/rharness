import json, os
from pathlib import Path
import pytest
from conftest import run_cli, REPO
from rharness.plugin import merge_hooks, unmerge_hooks

FIX = str(REPO / "tests" / "fixtures" / "plugins")
ENV = {"RHARNESS_PLUGINS_DIR": FIX}


def test_add_installs_files_region_skills_hooks(ws):
    code, out, err = run_cli(["add", "demo"], cwd=ws, env=ENV)
    assert code == 0, err
    assert (ws / "demo" / "tool.py").read_text() == f'print("demo {ws}")'
    agents = (ws / "AGENTS.md").read_text()
    assert "<!-- rharness:begin plugin:demo -->" in agents and "Demo rule one" in agents
    assert (ws / ".claude" / "skills" / "demo-skill" / "SKILL.md").exists()
    settings = json.loads((ws / ".claude" / "settings.json").read_text())
    assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "echo demo"
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert m["plugins"] == ["demo"]
    assert m["files"]["demo/tool.py"]["owner"] == "plugin:demo"
    assert m["files"][".claude/skills/demo-skill/SKILL.md"]["owner"] == "plugin:demo"
    assert m["hooks"]["demo"][0][0] == "PreToolUse"
    assert not (ws / "demo-setup.txt").exists()  # RHARNESS_SKIP_SETUP=1 in tests


def test_add_runs_setup_when_not_skipped(ws):
    code, out, err = run_cli(["add", "demo"], cwd=ws, env={**ENV, "RHARNESS_SKIP_SETUP": ""})
    assert code == 0, err
    assert (ws / "demo-setup.txt").read_text().strip() == "demo setup ran"


def test_add_twice_is_idempotent(ws):
    run_cli(["add", "demo"], cwd=ws, env=ENV)
    code, out, err = run_cli(["add", "demo"], cwd=ws, env=ENV)
    assert code == 0, err
    agents = (ws / "AGENTS.md").read_text()
    assert agents.count("<!-- rharness:begin plugin:demo -->") == 1
    settings = json.loads((ws / ".claude" / "settings.json").read_text())
    assert len(settings["hooks"]["PreToolUse"]) == 1


def test_add_preserves_existing_settings_keys(ws):
    (ws / ".claude").mkdir(exist_ok=True)
    (ws / ".claude" / "settings.json").write_text(json.dumps(
        {"model": "opus", "hooks": {"PreToolUse": [{"matcher": "Write", "hooks": []}]}}))
    code, out, err = run_cli(["add", "demo"], cwd=ws, env=ENV)
    assert code == 0, err
    s = json.loads((ws / ".claude" / "settings.json").read_text())
    assert s["model"] == "opus"
    assert [e["matcher"] for e in s["hooks"]["PreToolUse"]] == ["Write", "Bash"]


def test_add_codex_only_skips_claude_extras(tmp_path, home):
    root = tmp_path / "r"
    run_cli(["init", str(root), "--harness", "codex", "--no-plugins"], cwd=tmp_path)
    code, out, err = run_cli(["add", "demo"], cwd=root, env=ENV)
    assert code == 0, err
    assert (root / "demo" / "tool.py").exists()
    assert not (root / ".claude").exists()
    assert "Demo rule one" in (root / "AGENTS.md").read_text()


def test_add_applies_project_files_to_existing_projects(ws):
    run_cli(["new", "seam"], cwd=ws)
    code, out, err = run_cli(["add", "demo"], cwd=ws, env=ENV)
    assert code == 0, err
    assert (ws / "seam" / "tools" / "demo_helper.py").read_text() == "# helper for seam"
    pm = json.loads((ws / "seam" / ".rharness" / "project.json").read_text())
    assert pm["files"]["tools/demo_helper.py"]["owner"] == "plugin:demo"


def test_new_after_add_gets_project_files(ws):
    run_cli(["add", "demo"], cwd=ws, env=ENV)
    run_cli(["new", "seam"], cwd=ws, env=ENV)
    assert (ws / "seam" / "tools" / "demo_helper.py").exists()


def test_remove_deletes_unmodified_and_keeps_modified(ws):
    run_cli(["add", "demo"], cwd=ws, env=ENV)
    (ws / "demo" / "tool.py").write_text("user changed")
    code, out, err = run_cli(["remove", "demo"], cwd=ws, env=ENV)
    assert code == 0, err
    assert (ws / "demo" / "tool.py").exists() and "kept" in out
    assert not (ws / ".claude" / "skills" / "demo-skill").exists()
    assert "plugin:demo" not in (ws / "AGENTS.md").read_text()
    s = json.loads((ws / ".claude" / "settings.json").read_text())
    assert s["hooks"]["PreToolUse"] == []
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert m["plugins"] == [] and "demo" not in m["hooks"]
    assert "demo/tool.py" not in m["files"]


def test_unknown_plugin(ws):
    code, out, err = run_cli(["add", "nope"], cwd=ws, env=ENV)
    assert code == 2 and "nope" in err


def test_list_shows_installed_and_available(ws):
    run_cli(["add", "demo"], cwd=ws, env=ENV)
    code, out, err = run_cli(["list"], cwd=ws, env=ENV)
    assert code == 0 and "demo" in out and "installed" in out


def test_merge_and_unmerge_hooks_pure():
    settings = {"hooks": {"PreToolUse": [{"matcher": "Write", "hooks": []}]}}
    added = merge_hooks(settings, {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "x"}]}],
                                  "Stop": [{"hooks": [{"type": "command", "command": "y"}]}]})
    assert [a[0] for a in added] == ["PreToolUse", "Stop"]
    assert len(settings["hooks"]["PreToolUse"]) == 2 and len(settings["hooks"]["Stop"]) == 1
    unmerge_hooks(settings, [list(a) for a in added])
    assert settings["hooks"]["PreToolUse"] == [{"matcher": "Write", "hooks": []}]
    assert settings["hooks"]["Stop"] == []


def test_real_rtk_plugin_installs(ws):
    code, out, err = run_cli(["add", "rtk"], cwd=ws)
    assert code == 0, err
    hook = ws / ".rharness" / "hooks" / "rtk-rewrite.sh"
    assert hook.exists() and os.access(hook, os.X_OK)
    s = json.loads((ws / ".claude" / "settings.json").read_text())
    cmd = s["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "rtk-rewrite.sh" in cmd and "$CLAUDE_PROJECT_DIR" in cmd
    assert "rtk" in (ws / "AGENTS.md").read_text()


def test_init_installs_rtk_by_default(tmp_path, home):
    root = tmp_path / "r"
    code, out, err = run_cli(["init", str(root)], cwd=tmp_path)
    assert code == 0, err
    m = json.loads((root / ".rharness" / "manifest.json").read_text())
    assert m["plugins"] == ["rtk"]
    assert (root / ".rharness" / "hooks" / "rtk-rewrite.sh").exists()


@pytest.mark.parametrize("name", ["figures", "review-panel", "wandb", "ideas"])
def test_shipped_plugins_install_and_remove_cleanly(ws, name):
    code, out, err = run_cli(["add", name], cwd=ws)
    assert code == 0, err
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert name in m["plugins"]
    assert f"plugin:{name}" in (ws / "AGENTS.md").read_text()
    code, out, err = run_cli(["remove", name], cwd=ws)
    assert code == 0, err
    assert f"plugin:{name}" not in (ws / "AGENTS.md").read_text()
    m = json.loads((ws / ".rharness" / "manifest.json").read_text())
    assert not [k for k, v in m["files"].items() if v["owner"] == f"plugin:{name}"]


def test_wandb_project_file_lands_in_projects(ws):
    run_cli(["new", "seam"], cwd=ws)
    run_cli(["add", "wandb"], cwd=ws)
    helper = ws / "seam" / "tools" / "wandb_init.py"
    assert helper.exists() and 'project="seam"' in helper.read_text()


def test_figures_plugin_ships_checker_and_style(ws):
    run_cli(["add", "figures"], cwd=ws)
    for rel in ("figures/check_svg.py", "figures/figure-style.md", "figures/AGENTS.md",
                "figures/CLAUDE.md", "figures/Makefile.template", "figures/paper.mplstyle"):
        assert (ws / rel).exists(), rel
    assert os.access(ws / "figures" / "get-icon.sh", os.X_OK)


def test_shipped_plugin_manifests_valid():
    for d in sorted((REPO / "plugins").iterdir()):
        if not d.is_dir():
            continue
        meta = json.loads((d / "plugin.json").read_text())
        assert meta["name"] == d.name
        assert set(meta["harness"]) <= {"claude", "codex"}
        assert (d / "agents.md").exists()


def test_add_reports_missing_env_and_binaries(ws, tmp_path):
    fake = tmp_path / "fakebin"; fake.mkdir()
    code, out, err = run_cli(["add", "review-panel"], cwd=ws,
                             env={"PATH": str(fake), "OPENROUTER_API_KEY": ""})
    assert code == 0, err
    assert "OPENROUTER_API_KEY" in out and "pdftotext" in out

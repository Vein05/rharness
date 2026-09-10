import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "bin" / "rharness"


def run_cli(argv, cwd, env=None):
    """Run the CLI as a subprocess. Returns (code, stdout, stderr)."""
    full_env = dict(os.environ)
    full_env["RHARNESS_SKIP_SETUP"] = "1"
    full_env["GIT_AUTHOR_NAME"] = full_env["GIT_COMMITTER_NAME"] = "rharness-test"
    full_env["GIT_AUTHOR_EMAIL"] = full_env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    if env:
        full_env.update(env)
    p = subprocess.run([sys.executable, str(BIN), *argv], cwd=str(cwd),
                       env=full_env, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("RHARNESS_HOME", str(h / ".rharness"))
    return h


@pytest.fixture
def ws(tmp_path, home):
    """A freshly initialised workspace with no plugins."""
    root = tmp_path / "research"
    code, out, err = run_cli(["init", str(root), "--no-plugins"], cwd=tmp_path)
    assert code == 0, err
    return root

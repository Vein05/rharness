"""Shared setup for the venue tests: a local venue index, a template repo, and a project.

No test ever touches the network: GitHub shorthand is resolved against
RHARNESS_GITHUB_BASE, which points at a file:// directory of git repositories.
"""
import shutil
import subprocess
from pathlib import Path

from conftest import run_cli

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "venues"
INDEX_SHORTHAND = "lab/venues-repo/venues"
STYLE = "% testconf2026 style v1\n\\ProvidesPackage{testconf2026}\n"


def git_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True,
                   capture_output=True, timeout=60)
    subprocess.run(["git", "add", "-A"], cwd=str(path), check=True,
                   capture_output=True, timeout=60)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=str(path), check=True,
                   capture_output=True, timeout=60)
    return path


def venue_index_repo(tmp_path, names=("testconf2026",)):
    """Build a GitHub-shaped base dir holding a venue index repo and a template repo.

    Returns (env, index, repo): env sets RHARNESS_GITHUB_BASE, index is the shorthand
    prefix of the index (so f"{index}/testconf2026" is an installable spec), and repo
    is the index repository on disk.
    """
    base = Path(tmp_path) / "gh"
    repo = base / "lab" / "venues-repo"
    venues = repo / "venues"
    venues.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copytree(FIXTURES / name, venues / name)
    (repo / "README.md").write_text("venue packages\n")
    git_repo(repo)
    template = base / "lab" / "template-repo"
    template.mkdir(parents=True, exist_ok=True)
    (template / "testconf2026.sty").write_text(STYLE)
    git_repo(template)
    return {"RHARNESS_GITHUB_BASE": f"file://{base}/"}, INDEX_SHORTHAND, repo


def point_workspace_at(ws, index):
    """Make the workspace resolve bare venue names against a local index."""
    path = Path(ws) / "lint.toml"
    text = path.read_text() if path.exists() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + f'venue_index = "{index}"\n')
    return path


def make_project(ws, slug="seam"):
    """Scaffold a project in the workspace and return its directory."""
    code, out, err = run_cli(["new", slug], cwd=ws)
    assert code == 0, err
    return Path(ws) / slug

import io, json, os, tarfile
from pathlib import Path
from conftest import run_cli, REPO
from rharness.update import apply_managed, fetch_release, relink
from rharness.workspace import Workspace

EXCLUDE_PARTS = (".git", "__pycache__", ".pytest_cache", "tests")


def make_tarball(tmp_path, version="9.9.9"):
    """Build a release-like tarball of this repo with a bumped VERSION."""
    top = f"rharness-{version}"
    buf = tmp_path / f"{version}.tar.gz"
    with tarfile.open(buf, "w:gz") as tf:
        for p in sorted(REPO.rglob("*")):
            if not p.is_file() or any(s in p.parts for s in EXCLUDE_PARTS):
                continue
            rel = p.relative_to(REPO)
            data = p.read_bytes()
            if rel.as_posix() == "VERSION":
                data = f"{version}\n".encode()
            info = tarfile.TarInfo(f"{top}/{rel.as_posix()}")
            info.size = len(data)
            info.mode = p.stat().st_mode & 0o777
            tf.addfile(info, io.BytesIO(data))
    return buf


def test_fetch_release_from_file_url_and_relink(tmp_path, home):
    make_tarball(tmp_path)
    env = {"RHARNESS_RELEASE_URL": f"file://{tmp_path}/{{version}}.tar.gz", "RHARNESS_VERSION": "9.9.9"}
    dest = fetch_release("9.9.9", home / ".rharness", env)
    assert (dest / "VERSION").read_text().strip() == "9.9.9"
    assert (dest / "bin" / "rharness").exists()
    relink(home / ".rharness", "9.9.9")
    assert (home / ".rharness" / "store" / "current").resolve() == dest.resolve()


def test_apply_managed_replaces_unmodified_keeps_modified_and_regions(ws):
    run_cli(["new", "seam"], cwd=ws)
    w = Workspace.open(override=ws)
    p = ws / "seam"
    (p / "CHARTER.md").write_text("user edit")
    orig_spec = (p / "spec" / "README.md").read_text()
    agents = ws / "AGENTS.md"
    agents.write_text(agents.read_text() + "\nUser notes at the end.\n")
    replaced, kept = apply_managed(w)
    assert "seam/CHARTER.md" in kept
    assert "seam/spec/README.md" in replaced
    assert (p / "spec" / "README.md").read_text() == orig_spec
    assert (p / "CHARTER.md").read_text() == "user edit"
    assert "User notes at the end." in agents.read_text()


def test_apply_managed_force_backs_up_and_overwrites(ws):
    run_cli(["new", "seam"], cwd=ws)
    w = Workspace.open(override=ws)
    p = ws / "seam"
    (p / "CHARTER.md").write_text("user edit")
    replaced, kept = apply_managed(w, force=True)
    assert "seam/CHARTER.md" in replaced and kept == []
    assert "Project Charter" in (p / "CHARTER.md").read_text()
    backups = list((p / ".rharness" / "backup").rglob("CHARTER.md"))
    assert backups and backups[0].read_text() == "user edit"


def test_update_command_no_fetch(ws):
    code, out, err = run_cli(["update", "--no-fetch"], cwd=ws)
    assert code == 0, err
    assert "replaced" in out and "kept" in out


def test_update_command_fetches_and_applies(ws, tmp_path, home):
    run_cli(["new", "seam"], cwd=ws)
    make_tarball(tmp_path)
    env = {"RHARNESS_RELEASE_URL": f"file://{tmp_path}/{{version}}.tar.gz", "RHARNESS_VERSION": "9.9.9"}
    code, out, err = run_cli(["update"], cwd=ws, env=env)
    assert code == 0, err
    assert (home / ".rharness" / "store" / "9.9.9" / "VERSION").exists()
    assert "fetched 9.9.9" in out

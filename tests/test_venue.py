import json
from pathlib import Path

from conftest import run_cli
from venue_helpers import venue_index_repo, point_workspace_at, make_project

from rharness import venue as V
from rharness.manifest import Manifest
from rharness.plugin import Plugin, fetch_plugin
from rharness.workspace import Workspace


def _fetched_plugin(tmp_path, monkeypatch):
    env, index, repo = venue_index_repo(tmp_path)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    d = fetch_plugin(f"{index}/testconf2026")
    return Plugin("testconf2026", d), env, index


def test_block_roundtrip_and_charter_note(ws, tmp_path, home):
    p = make_project(ws)
    assert V.read_block(p) is None
    blk = V.venue_block("testconf2026", "lab/venues-repo/venues/testconf2026", None, "c" * 40,
                        "2026-09-10T10:00:00-05:00", "t" * 64)
    V.write_block(p, blk)
    assert V.read_block(p)["state"] == "targeted" and V.read_block(p)["locked_on"] is None
    pm = V.load_pm(p)
    V.charter_note(p, pm, "venue target set to testconf2026")
    pm.save()
    ch = (p / "CHARTER.md").read_text()
    assert "## Revision notes" in ch and ch.rstrip().endswith("venue target set to testconf2026")
    assert Manifest.load(p / ".rharness" / "project.json").is_unmodified("CHARTER.md")
    V.write_block(p, None)
    assert V.read_block(p) is None


def test_set_table_cell(ws, tmp_path, home):
    make_project(ws)
    wsobj = Workspace.open(override=ws)
    V.set_table_cell(wsobj, "seam", "testconf2026 (targeted)")
    row = next(l for l in (ws / "AGENTS.md").read_text().splitlines() if l.startswith("| `seam/` |"))
    assert row.split("|")[3].strip() == "testconf2026 (targeted)"
    assert wsobj.manifest.is_unmodified("AGENTS.md")


def test_install_and_remove_package(ws, tmp_path, home, monkeypatch):
    plugin, env, index = _fetched_plugin(tmp_path, monkeypatch)
    p = make_project(ws)
    wsobj = Workspace.open(override=ws)
    venue = V.load_venue(plugin.dir)
    written = V.install_package(wsobj, p, plugin, venue, f"{index}/testconf2026", None)
    assert "paper/testconf2026.sty" in written and "research/venue-testconf2026.md" in written
    assert (p / "paper" / "testconf2026.sty").read_text().startswith("% testconf2026 style v1")
    pm = Manifest.load(p / ".rharness" / "project.json")
    assert pm.entry("paper/testconf2026.sty")["owner"] == "venue:testconf2026"
    assert "source" not in pm.entry("paper/testconf2026.sty")
    assert pm.entry("research/venue-testconf2026.md")["source"] == "plugins/testconf2026/project-files/research/venue-testconf2026.md"
    assert "seam" in (p / "research" / "venue-testconf2026.md").read_text()
    agents = (p / "AGENTS.md").read_text()
    assert "<!-- rharness:begin plugin:testconf2026 -->" in agents and "rharness:venue-style" in agents
    assert pm.is_unmodified("AGENTS.md") and pm.is_unmodified("CHARTER.md")
    blk = V.read_block(p)
    assert blk["name"] == "testconf2026" and blk["state"] == "targeted" and len(blk["commit"]) == 40
    assert blk["source"] == f"{index}/testconf2026" and blk["ref"] is None and len(blk["tree"]) == 64
    assert "testconf2026 (targeted)" in (ws / "AGENTS.md").read_text()
    assert "venue target set to testconf2026" in (p / "CHARTER.md").read_text()
    # modify one file, then remove: modified is kept, unmodified is deleted
    (p / "paper" / "testconf2026.sty").write_text("% edited\n")
    removed, kept = V.remove_package(wsobj, p, "testconf2026", "venue testconf2026 removed")
    assert "research/venue-testconf2026.md" in removed and "paper/testconf2026.sty" in kept
    assert (p / "paper" / "testconf2026.sty").exists() and not (p / "research" / "venue-testconf2026.md").exists()
    pm = Manifest.load(p / ".rharness" / "project.json")
    assert pm.entry("paper/testconf2026.sty") is None and V.read_block(p) is None
    assert "plugin:testconf2026" not in (p / "AGENTS.md").read_text()
    row = next(l for l in (ws / "AGENTS.md").read_text().splitlines() if l.startswith("| `seam/` |"))
    assert row.split("|")[3].strip() == "-"


def test_fetch_templates_from_zip(ws, tmp_path, home):
    import hashlib, io, zipfile
    p = make_project(ws)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("kit/conf.sty", "% conf sty\n")
        z.writestr("kit/conf.bst", "% conf bst\n")
        z.writestr("kit/README", "ignore\n")
    data = buf.getvalue()
    zpath = tmp_path / "kit.zip"; zpath.write_bytes(data)
    venue = {"name": "zipconf2026", "template": {"url": f"file://{zpath}", "sha256": hashlib.sha256(data).hexdigest(),
                                                  "extract": ["kit/conf.sty", "kit/conf.bst"]}}
    pm = V.load_pm(p)
    written = V.fetch_templates(p, venue, pm, "zipconf2026")
    assert sorted(written) == ["paper/conf.bst", "paper/conf.sty"]
    assert (p / "paper" / "conf.sty").read_text() == "% conf sty\n"
    venue["template"]["sha256"] = "0" * 64
    import pytest
    with pytest.raises(V.VenueError):
        V.fetch_templates(p, venue, pm, "zipconf2026")


def test_load_venue_rejects_invalid(tmp_path):
    d = tmp_path / "bad"; d.mkdir()
    (d / "venue.json").write_text(json.dumps({"venue": "x", "cycle": "2026", "name": "x2026"}))
    import pytest
    with pytest.raises(V.VenueError) as e:
        V.load_venue(d)
    assert "primary" in str(e.value)


def test_template_refuses_main_tex_and_keeps_files_it_does_not_own(ws, tmp_path, home, capsys):
    import hashlib, io, zipfile
    import pytest
    p = make_project(ws)
    pm = V.load_pm(p)
    bad = {"name": "zipconf2026",
           "template": {"repo": "lab/template-repo", "ref": "main", "files": ["main.tex"]}}
    with pytest.raises(V.VenueError) as e:
        V.fetch_templates(p, bad, pm, "zipconf2026")
    assert "main.tex" in str(e.value)
    # a template file that collides with a base-owned scaffold file leaves it alone
    before = (p / "paper" / "references.bib").read_text()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("kit/references.bib", "% not yours\n")
    data = buf.getvalue()
    zpath = tmp_path / "collide.zip"; zpath.write_bytes(data)
    venue = {"name": "zipconf2026", "template": {"url": f"file://{zpath}",
             "sha256": hashlib.sha256(data).hexdigest(), "extract": ["kit/references.bib"]}}
    assert V.fetch_templates(p, venue, pm, "zipconf2026") == []
    assert (p / "paper" / "references.bib").read_text() == before
    assert "kept existing paper/references.bib" in capsys.readouterr().out
    assert pm.entry("paper/references.bib")["owner"] == "base"

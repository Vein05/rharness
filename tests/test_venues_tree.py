import json
import subprocess
import sys
from pathlib import Path

import pytest

from rharness.venuemeta import validate

REPO = Path(__file__).resolve().parents[1]
VENUES = REPO / "venues"

pytestmark = pytest.mark.skipif(not VENUES.is_dir(),
                                reason="venues/ is export-ignored from the release tarball")


def _packages():
    return sorted(d for d in VENUES.iterdir() if d.is_dir() and (d / "venue.json").exists())


def test_every_package_validates_and_matches_its_directory():
    assert _packages(), "no venue packages"
    for d in _packages():
        v = json.loads((d / "venue.json").read_text())
        assert validate(v) == [], (d.name, validate(v))
        assert v["name"] == d.name
        pj = json.loads((d / "plugin.json").read_text())
        assert pj["name"] == d.name and pj["scope"] == "project" and pj["kind"] == "venue"
        assert (d / "agents.md").exists()
        assert "rharness:venue-style" in (d / "agents.md").read_text()
        assert "Overleaf" in (d / "agents.md").read_text()


def test_index_is_current():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "venues-index.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_validate_script_passes():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "venues-validate.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_venues_are_export_ignored():
    attrs = (REPO / ".gitattributes").read_text()
    assert "venues/ export-ignore" in attrs


def test_iclr2027_package_shape():
    v = json.loads((VENUES / "iclr2027" / "venue.json").read_text())
    assert v["anonymous"] is True and v["primary"] == "full"
    assert v["deadlines"]["full"].endswith("-12:00")
    assert v["template"]["repo"] == "ICLR/Master-Template" and len(v["template"]["ref"]) == 40
    assert any(f.endswith(".sty") for f in v["template"]["files"])
    assert any(s["kind"] == "cfp" for s in v["sources"])


@pytest.mark.parametrize("name,deadline", [("naacl2027", "2026-10-12T23:59:00-12:00"),
                                           ("acl2027", "2027-01-04T23:59:00-12:00")])
def test_arr_package_shape(name, deadline):
    d = VENUES / name
    v = json.loads((d / "venue.json").read_text())
    assert v["deadlines"][v["primary"]] == deadline
    assert v["page_limit"]["main"] == 8 and "limitations" in v["page_limit"]["excludes"]
    assert "limitations" in v["required_sections"] and v["anonymous"] is True
    assert v["template"]["repo"] == "acl-org/acl-style-files"
    assert v["template"]["files"] == ["acl.sty", "acl_natbib.bst"]
    assert len(v["template"]["ref"]) == 40
    assert (d / "project-files" / "research" / f"venue-{name}.md").exists()
    assert set(json.loads((d / "sources.lock.json").read_text())) == {s["url"] for s in v["sources"]}


@pytest.mark.parametrize("name", ["naacl2027", "acl2027"])
def test_arr_checks_py_wants_review_mode(name, tmp_path):
    from rharness.venuecheck import author_block_hidden, load_package_checks, _strip_comments
    v = json.loads((VENUES / name / "venue.json").read_text())
    fn = load_package_checks(VENUES / name)
    (tmp_path / "paper").mkdir()
    main = tmp_path / "paper" / "main.tex"
    main.write_text("\\documentclass[11pt]{article}\n\\usepackage{acl}\n")
    rows = fn(tmp_path, v)
    assert len(rows) == 1 and rows[0][0] == "warning" and rows[0][1] == "paper/main.tex", rows
    main.write_text("\\documentclass[11pt]{article}\n\\usepackage[review]{acl}\n% \\usepackage{acl}\n")
    assert fn(tmp_path, v) == []
    assert author_block_hidden(v, _strip_comments(main.read_text()))
    main.write_text("\\usepackage[review]{acl}\n\\begin{document}\n\\begin{verbatim}\n\\usepackage{acl}\n\\end{verbatim}\n")
    assert fn(tmp_path, v) == []
    main.write_text("\\usepackage[final]{acl}\n")
    assert not author_block_hidden(v, _strip_comments(main.read_text())) and len(fn(tmp_path, v)) == 1

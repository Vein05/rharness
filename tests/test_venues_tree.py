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

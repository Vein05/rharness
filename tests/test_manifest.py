import json
from pathlib import Path
import pytest
from rharness.manifest import Manifest, sha256_file


def test_sha256_file(tmp_path):
    f = tmp_path / "a"; f.write_text("abc")
    assert sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_new_save_load_roundtrip(tmp_path):
    p = tmp_path / ".rharness" / "manifest.json"
    m = Manifest.new(p, "0.1.0")
    m.save()
    data = json.loads(p.read_text())
    assert data["rharness_version"] == "0.1.0"
    assert data["harness"] == ["claude", "codex"]
    assert data["plugins"] == [] and data["files"] == {} and data["hooks"] == {}
    assert data["projects"] == []
    assert len(data["created"]) == 10
    m2 = Manifest.load(p)
    assert m2.root == tmp_path
    assert m2.harness == ["claude", "codex"]


def test_load_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Manifest.load(tmp_path / ".rharness" / "manifest.json")


def test_record_and_unmodified(tmp_path):
    p = tmp_path / ".rharness" / "manifest.json"
    m = Manifest.new(p, "0.1.0")
    f = tmp_path / "CHARTER.md"; f.write_text("v1")
    m.record("CHARTER.md", "base", source="base/project/CHARTER.md")
    e = m.entry("CHARTER.md")
    assert e["owner"] == "base" and e["source"] == "base/project/CHARTER.md"
    assert e["sha256"] == sha256_file(f)
    assert "region" not in e
    assert m.is_unmodified("CHARTER.md")
    f.write_text("v2")
    assert not m.is_unmodified("CHARTER.md")
    f.unlink()
    assert not m.is_unmodified("CHARTER.md")


def test_record_region_flag(tmp_path):
    p = tmp_path / ".rharness" / "manifest.json"
    m = Manifest.new(p, "0.1.0")
    (tmp_path / "AGENTS.md").write_text("x")
    m.record("AGENTS.md", "base", region=True)
    assert m.entry("AGENTS.md")["region"] is True


def test_forget_and_owned_by(tmp_path):
    p = tmp_path / ".rharness" / "manifest.json"
    m = Manifest.new(p, "0.1.0")
    for name, owner in [("a", "base"), ("b", "plugin:rtk"), ("c", "plugin:rtk")]:
        (tmp_path / name).write_text(name)
        m.record(name, owner)
    assert m.files_owned_by("plugin:rtk") == ["b", "c"]
    m.forget("b")
    assert m.files_owned_by("plugin:rtk") == ["c"]
    assert m.entry("b") is None


def test_plugins_hooks_projects(tmp_path):
    p = tmp_path / ".rharness" / "manifest.json"
    m = Manifest.new(p, "0.1.0")
    m.add_plugin("rtk"); m.add_plugin("rtk")
    assert m.plugins == ["rtk"]
    m.hooks["rtk"] = [{"matcher": "Bash"}]
    m.projects.append("seam")
    m.save()
    m2 = Manifest.load(p)
    assert m2.plugins == ["rtk"] and m2.hooks == {"rtk": [{"matcher": "Bash"}]}
    assert m2.projects == ["seam"]
    m2.remove_plugin("rtk"); m2.remove_plugin("missing")
    assert m2.plugins == []


def test_ctx_persists(tmp_path):
    p = tmp_path / ".rharness" / "project.json"
    m = Manifest.new(p, "0.1.0", ctx={"slug": "seam", "title": "SEAM"})
    m.save()
    assert Manifest.load(p).ctx == {"slug": "seam", "title": "SEAM"}

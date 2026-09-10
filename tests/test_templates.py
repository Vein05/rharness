import os
from pathlib import Path
from rharness.templates import render, copy_tree, PLACEHOLDERS


def test_render_replaces_only_known_placeholders():
    ctx = {"slug": "seam", "title": "SEAM", "date": "2026-09-09", "workspace": "/w"}
    text = "# {{title}} ({{slug}}) {{date}} {{workspace}} {{unknown}} {{ spaced }}"
    assert render(text, ctx) == "# SEAM (seam) 2026-09-09 /w {{unknown}} {{ spaced }}"


def test_render_missing_key_leaves_placeholder():
    assert render("{{slug}}-{{title}}", {"slug": "x"}) == "x-{{title}}"


def test_placeholders_constant():
    assert PLACEHOLDERS == ("slug", "title", "date", "workspace")


def test_copy_tree_writes_renders_and_skips_existing(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.md").write_text("hello {{slug}}")
    (src / "sub" / "b.txt").write_text("b")
    (src / "run.sh").write_text("#!/bin/sh\n")
    os.chmod(src / "run.sh", 0o755)
    (src / "bin.dat").write_bytes(b"\x00\xff\x00")
    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "sub").mkdir()
    (dst / "sub" / "b.txt").write_text("user edited")

    written, skipped = copy_tree(src, dst, {"slug": "seam"})

    assert sorted(written) == ["a.md", "bin.dat", "run.sh"]
    assert skipped == ["sub/b.txt"]
    assert (dst / "a.md").read_text() == "hello seam"
    assert (dst / "sub" / "b.txt").read_text() == "user edited"
    assert (dst / "bin.dat").read_bytes() == b"\x00\xff\x00"
    assert os.access(dst / "run.sh", os.X_OK)


def test_copy_tree_overwrite(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "a.md").write_text("new")
    dst = tmp_path / "dst"; dst.mkdir()
    (dst / "a.md").write_text("old")
    written, skipped = copy_tree(src, dst, {}, overwrite=True)
    assert written == ["a.md"] and skipped == []
    assert (dst / "a.md").read_text() == "new"


def test_copy_tree_keeps_gitkeep_and_dotfiles(tmp_path):
    src = tmp_path / "src"; (src / "tests").mkdir(parents=True)
    (src / "tests" / ".gitkeep").write_text("")
    (src / ".gitignore").write_text("x")
    dst = tmp_path / "dst"; dst.mkdir()
    written, _ = copy_tree(src, dst, {})
    assert sorted(written) == [".gitignore", "tests/.gitkeep"]

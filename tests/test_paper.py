import os
import stat
from pathlib import Path

from conftest import run_cli
from rharness import paper


def _fake(bindir: Path, name: str, body: str):
    f = bindir / name
    f.write_text("#!/bin/sh\n" + body)
    f.chmod(f.stat().st_mode | stat.S_IEXEC)


def _fakes(tmp_path, with_tlmgr=True, with_latexmk=True):
    b = tmp_path / "fakebin"; b.mkdir(exist_ok=True)
    if with_latexmk:
        _fake(b, "latexmk", 'if [ -f .pkg_ok ]; then printf "%%PDF-1.5 fake" > main.pdf; exit 0; fi\n'
                            'printf "! LaTeX Error: File \\140foo.sty\\047 not found.\\n"; exit 1\n')
    _fake(b, "pdflatex", "exit 0\n")
    if with_tlmgr:
        _fake(b, "tlmgr", 'case "$1" in\n search) printf "foopkg:\\n\\ttexmf-dist/tex/latex/foopkg/foo.sty\\n";;\n'
                          ' install) [ "$2" = foopkg ] && touch .pkg_ok;;\nesac\nexit 0\n')
    return str(b)


def test_missing_file_parsing():
    assert paper.missing_file("! LaTeX Error: File `iclr2027_conference.sty' not found.") == "iclr2027_conference.sty"
    assert paper.missing_file("! I can't find file `foo.cls'.") == "foo.cls"
    assert paper.missing_file("all good") is None


def test_build_installs_missing_package_and_retries(tmp_path):
    env = {"PATH": _fakes(tmp_path)}
    paper_dir = tmp_path / "paper"; paper_dir.mkdir()
    (paper_dir / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
    code, msg = paper.build(paper_dir, env=env)
    assert code == 0, msg
    assert (paper_dir / "main.pdf").exists() and "foopkg" in msg


def test_build_without_tlmgr_reports_missing_file(tmp_path):
    env = {"PATH": _fakes(tmp_path, with_tlmgr=False)}
    paper_dir = tmp_path / "paper"; paper_dir.mkdir()
    (paper_dir / "main.tex").write_text("x")
    code, msg = paper.build(paper_dir, env=env)
    assert code == 1 and "foo.sty" in msg and "not found" in msg


def test_build_without_latexmk_but_with_tlmgr(tmp_path):
    env = {"PATH": _fakes(tmp_path, with_latexmk=False)}
    paper_dir = tmp_path / "paper"; paper_dir.mkdir()
    (paper_dir / "main.tex").write_text("x")
    code, msg = paper.build(paper_dir, env=env)
    assert code == 2 and "tlmgr install latexmk" in msg


def test_build_gives_up_after_max_rounds_installs(tmp_path):
    b = Path(_fakes(tmp_path))
    _fake(b, "tlmgr", 'case "$1" in\n search) printf "foopkg:\\n\\ttexmf-dist/tex/latex/foopkg/foo.sty\\n";;\nesac\nexit 0\n')
    paper_dir = tmp_path / "paper"; paper_dir.mkdir()
    (paper_dir / "main.tex").write_text("x")
    code, msg = paper.build(paper_dir, env={"PATH": str(b)}, max_rounds=5)
    assert code == 1 and msg == "gave up after installing 5 package(s): " + ", ".join(["foopkg"] * 5)


def test_build_without_engine(tmp_path):
    b = tmp_path / "empty"; b.mkdir()
    paper_dir = tmp_path / "paper"; paper_dir.mkdir()
    code, msg = paper.build(paper_dir, env={"PATH": str(b)})
    assert code == 2 and "TinyTeX" in msg and "Overleaf" in msg
    code, msg = paper.build(tmp_path / "nope", env={"PATH": str(b)})
    assert code == 2 and "paper/" in msg


def test_build_uses_make_when_makefile_present(tmp_path):
    b = Path(_fakes(tmp_path))
    _fake(b, "make", 'printf "%%PDF-1.5 make" > main.pdf; exit 0\n')
    paper_dir = tmp_path / "paper"; paper_dir.mkdir()
    (paper_dir / "Makefile").write_text("all:\n\ttrue\n")
    code, msg = paper.build(paper_dir, env={"PATH": str(b)})
    assert code == 0 and (paper_dir / "main.pdf").read_text().endswith("make")


def test_cli_paper_build_and_venue_check_build(ws, tmp_path, home):
    from venue_helpers import venue_index_repo, point_workspace_at, make_project
    env, index, repo = venue_index_repo(tmp_path)
    point_workspace_at(ws, index)
    p = make_project(ws)
    path = _fakes(tmp_path) + os.pathsep + os.environ["PATH"]
    code, out, err = run_cli(["paper", "build"], cwd=p, env={"PATH": path})
    assert code == 0, err
    assert (p / "paper" / "main.pdf").exists() and "built" in out
    code, out, err = run_cli(["venue", "add", "testconf2026"], cwd=p, env=dict(env, PATH=path))
    assert code == 0, err
    code, out, err = run_cli(["venue", "check", "--build"], cwd=p, env=dict(env, PATH=path))
    assert code == 1  # findings exist (style not loaded)
    assert "does not load testconf2026" in out
    code, out, err = run_cli(["paper", "build", "--project", "seam"], cwd=ws, env={"PATH": path})
    assert code == 0, err


def test_scaffold_has_marker_makefile_prereqs_and_gitignore(ws):
    from venue_helpers import make_project
    p = make_project(ws)
    assert "% rharness:venue-style" in (p / "paper" / "main.tex").read_text()
    mk = (p / "paper" / "Makefile").read_text()
    assert "$(wildcard *.sty)" in mk and "$(wildcard *.cls)" in mk
    assert "paper/main.pdf" in (p / ".gitignore").read_text()

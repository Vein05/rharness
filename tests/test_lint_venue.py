"""`rharness lint --venue <name> [dir]` on a bare LaTeX directory with no rharness files."""
import json
import os
import subprocess

import pytest

from conftest import run_cli
from test_pdfutil import _plain_pdf
from venue_helpers import INDEX_SHORTHAND, point_workspace_at, venue_index_repo

MAIN = r"""\documentclass{article}
\usepackage{testconf2026}
\author{Anonymous}
\begin{document}
\begin{abstract}A\end{abstract}
\input{sections/intro}
\bibliography{refs}
\end{document}
"""
INTRO = r"""\section{Introduction}
We cite \cite{good2020} and \cite{missing2021}.
"""
OTHER = r"""\documentclass{article}
\author{Jane Realname}
\begin{document}\cite{elsewhere}\end{document}
"""


@pytest.fixture
def index_env(tmp_path, home, monkeypatch):
    env, index, repo = venue_index_repo(tmp_path)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return env


def _bare(d, main=MAIN):
    (d / "sections").mkdir(parents=True)
    (d / "main.tex").write_text(main)
    (d / "sections" / "intro.tex").write_text(INTRO)
    (d / "refs.bib").write_text("@article{good2020, title={x}}\n")
    (d / "notes").mkdir()
    (d / "notes" / "draft.tex").write_text(OTHER)  # not \input from main.tex: never scanned
    return d


def _rows(out):
    return [json.loads(l) for l in out.splitlines() if l.startswith("{")]


def _full(name="testconf2026"):
    return f"{INDEX_SHORTHAND}/{name}"


def test_foreign_source_needs_yes(index_env, tmp_path):
    d = _bare(tmp_path / "paper-repo")
    code, out, err = run_cli(["lint", "--venue", _full(), str(d)], cwd=tmp_path)
    assert code == 1
    assert "--yes" in out and "checks.py" in out
    assert not _rows(out)


def test_bare_repo_findings(index_env, tmp_path):
    d = _bare(tmp_path / "paper-repo")
    code, out, err = run_cli(["--yes", "lint", "--json", "--venue", _full(), str(d)], cwd=tmp_path)
    rows = _rows(out)
    msgs = [r["message"] for r in rows]
    assert code == 1, (out, err)
    assert all(r["project"] == "paper-repo" for r in rows)
    hit = [r for r in rows if "missing2021" in r["message"]]
    assert len(hit) == 1 and hit[0]["severity"] == "error", rows
    assert "refs.bib" in hit[0]["message"] and hit[0]["path"] == "main.tex"
    assert not any("good2020" in m for m in msgs)
    assert not any("elsewhere" in m or "Realname" in m for m in msgs), msgs
    assert not any("references.bib" in m for m in msgs), msgs
    assert not any("required section" in m for m in msgs), msgs
    assert not any("does not load" in m for m in msgs), msgs
    assert any(r["path"] == "main.pdf" and "missing" in r["message"] for r in rows), rows
    assert not any("rharness paper build" in m for m in msgs), msgs


def test_bare_repo_text_output_and_fail_on(index_env, tmp_path):
    d = _bare(tmp_path / "paper-repo")
    code, out, err = run_cli(["--yes", "lint", "--venue", _full(), str(d)], cwd=tmp_path)
    assert "error paper-repo/main.tex: citation key missing2021" in out
    assert out.strip().splitlines()[-1].startswith("Summary:")
    (d / "sections" / "intro.tex").write_text(INTRO.replace(" and \\cite{missing2021}", ""))
    code, out, err = run_cli(["--yes", "lint", "--venue", _full(), "--fail-on", "error", str(d)], cwd=tmp_path)
    assert code == 0, out


def test_bare_repo_anonymity_and_sections(index_env, tmp_path):
    d = _bare(tmp_path / "paper-repo", main=MAIN.replace(r"\author{Anonymous}", r"\author{Jane Realname}")
              .replace(r"\begin{abstract}A\end{abstract}", ""))
    code, out, err = run_cli(["--yes", "lint", "--json", "--venue", _full(), str(d)], cwd=tmp_path)
    rows = _rows(out)
    assert any(r["severity"] == "error" and "author block" in r["message"] and r["path"] == "main.tex"
               for r in rows), rows
    assert any("required section 'abstract'" in r["message"] and r["path"] == "" for r in rows), rows


def test_bare_repo_page_count_reads_stem_pdf(index_env, tmp_path):
    d = _bare(tmp_path / "paper-repo")
    os.rename(d / "main.tex", d / "paper.tex")
    (d / "notes" / "draft.tex").unlink()  # paper.tex is then the only \documentclass file
    (d / "paper.pdf").write_bytes(_plain_pdf(5))
    code, out, err = run_cli(["--yes", "lint", "--json", "--venue", _full(), str(d)], cwd=tmp_path)
    rows = _rows(out)
    assert any(r["path"] == "paper.pdf" and "5 pages" in r["message"] for r in rows), rows
    assert not any("missing" in r["message"] and r["path"] == "paper.pdf" for r in rows), rows


def test_bare_name_resolves_against_workspace_index(index_env, ws):
    point_workspace_at(ws, INDEX_SHORTHAND)
    d = _bare(ws / "drafts" / "paper-repo")
    code, out, err = run_cli(["lint", "--json", "--venue", "testconf2026", str(d)], cwd=ws)
    assert "--yes" not in out
    assert any("missing2021" in r["message"] for r in _rows(out)), (out, err)


def test_dir_defaults_to_cwd(index_env, tmp_path):
    d = _bare(tmp_path / "paper-repo")
    code, out, err = run_cli(["--yes", "lint", "--json", "--venue", _full()], cwd=d)
    assert any("missing2021" in r["message"] for r in _rows(out)), (out, err)


def test_ambiguous_main_needs_main_flag(index_env, tmp_path):
    d = _bare(tmp_path / "paper-repo")
    os.rename(d / "main.tex", d / "a.tex")
    (d / "b.tex").write_text(OTHER)
    code, out, err = run_cli(["--yes", "lint", "--venue", _full(), str(d)], cwd=tmp_path)
    assert code == 2
    assert "a.tex" in err and "b.tex" in err and "--main" in err
    code, out, err = run_cli(["--yes", "lint", "--json", "--venue", _full(), "--main", "a.tex", str(d)],
                             cwd=tmp_path)
    assert any("missing2021" in r["message"] for r in _rows(out)), (out, err)
    assert not any("elsewhere" in r["message"] for r in _rows(out))


def test_no_tex_is_a_usage_error(index_env, tmp_path):
    d = tmp_path / "empty"; d.mkdir()
    code, out, err = run_cli(["--yes", "lint", "--venue", _full(), str(d)], cwd=tmp_path)
    assert code == 2 and "\\documentclass" in err


def test_unknown_venue_is_a_usage_error(index_env, tmp_path):
    d = _bare(tmp_path / "paper-repo")
    code, out, err = run_cli(["--yes", "lint", "--venue", _full("nosuch2026"), str(d)], cwd=tmp_path)
    assert code == 2 and "nosuch2026" in err


def test_git_author_in_bare_repo(index_env, tmp_path):
    d = _bare(tmp_path / "paper-repo")
    (d / "sections" / "intro.tex").write_text(INTRO + "Thanks to rharness-test for help.\n")
    subprocess.run(["git", "init", "-q"], cwd=str(d), check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(d), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=str(d), check=True)
    code, out, err = run_cli(["--yes", "lint", "--json", "--venue", _full(), str(d)], cwd=tmp_path)
    assert any("git author name 'rharness-test'" in r["message"] for r in _rows(out)), out


def test_project_lint_messages_unchanged(index_env, ws):
    """The project path keeps its paper/ paths and references.bib wording."""
    from venue_helpers import make_project
    point_workspace_at(ws, INDEX_SHORTHAND)
    p = make_project(ws)
    code, out, err = run_cli(["venue", "add", "testconf2026", "--project", p.name], cwd=ws)
    assert code == 0, err
    (p / "paper" / "main.tex").write_text(MAIN.replace(r"\input{sections/intro}", INTRO)
                                          .replace(r"\bibliography{refs}", r"\bibliography{references}"))
    (p / "paper" / "references.bib").write_text("@article{good2020, title={x}}\n")
    code, out, err = run_cli(["lint", "--json"], cwd=ws)
    rows = _rows(out)
    assert any(r["path"] == "paper/main.tex" and "missing2021 is not in references.bib" in r["message"]
               for r in rows), rows
    assert any(r["path"] == "paper/main.pdf" and "rharness paper build" in r["message"] for r in rows), rows


def test_stale_cache_used_when_refetch_fails(index_env, tmp_path, monkeypatch):
    from rharness.venuestate import package_dir
    d = _bare(tmp_path / "paper-repo")
    assert run_cli(["--yes", "lint", "--venue", _full(), str(d)], cwd=tmp_path)[0] == 1
    src = package_dir("testconf2026") / ".rharness-source.json"
    info = json.loads(src.read_text()); info["fetched"] = "2020-01-01T00:00:00+00:00"
    src.write_text(json.dumps(info))
    code, out, err = run_cli(["--yes", "lint", "--json", "--venue", _full(), str(d)], cwd=tmp_path,
                             env={"RHARNESS_GITHUB_BASE": f"file://{tmp_path}/nowhere/"})
    assert any("missing2021" in r["message"] for r in _rows(out)), (out, err)


def test_main_without_venue_is_a_usage_error(ws):
    code, out, err = run_cli(["lint", "--main", "main.tex"], cwd=ws)
    assert code == 2 and "--venue" in err


def test_input_outside_dir_is_ignored(index_env, tmp_path):
    (tmp_path / "outside.tex").write_text("\\author{Jane Realname}\n")
    d = _bare(tmp_path / "paper-repo", main=MAIN.replace(r"\input{sections/intro}",
                                                          r"\input{sections/intro}\input{../outside}"))
    code, out, err = run_cli(["--yes", "lint", "--json", "--venue", _full(), str(d)], cwd=tmp_path)
    rows = _rows(out)
    assert any("missing2021" in r["message"] for r in rows), (out, err)
    assert not any("Realname" in r["message"] for r in rows), rows

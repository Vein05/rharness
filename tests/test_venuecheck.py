import json
import os
import subprocess
from pathlib import Path

import pytest

from venue_helpers import venue_index_repo, make_project
from rharness import venue as V, venuecheck as VC
from rharness.plugin import Plugin, fetch_plugin
from rharness.workspace import Workspace

TEX = r"""\documentclass{article}
% rharness:venue-style
\usepackage{testconf2026}
\author{Anonymous}
\begin{document}
\begin{abstract}A\end{abstract}
\section{Introduction}
We cite \cite{good2020} and \cite{missing2021}.
\bibliography{references}
\end{document}
"""
BIB = "@article{good2020, title={x}}\n@misc{dup2019, title={y}}\n@misc{dup2019, title={z}}\n"


@pytest.fixture
def venue_project(ws, tmp_path, home, monkeypatch):
    env, index, repo = venue_index_repo(tmp_path)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    p = make_project(ws)
    d = fetch_plugin(f"{index}/testconf2026")
    plugin = Plugin("testconf2026", d)
    venue = V.load_venue(d)
    V.install_package(Workspace.open(override=ws), p, plugin, venue, f"{index}/testconf2026", None)
    (p / "paper" / "main.tex").write_text(TEX)
    (p / "paper" / "references.bib").write_text(BIB)
    return p, venue, d


def _msgs(findings):
    return [f"{s} {p}: {m}" for s, p, m in findings]


def test_generic_checks_sections_cites_style(venue_project):
    p, venue, _ = venue_project
    f = VC.check_generic(p, venue, env={"PATH": "/nonexistent"})
    msgs = _msgs(f)
    assert any("missing2021" in m and m.startswith("error") for m in msgs)
    assert any("dup2019" in m and "duplicate" in m for m in msgs)
    assert not any("does not load" in m for m in msgs)
    assert not any("required section" in m for m in msgs)
    (p / "paper" / "main.tex").write_text(TEX.replace(r"\usepackage{testconf2026}", "").replace(r"\section{Introduction}", ""))
    msgs = _msgs(VC.check_generic(p, venue, env={"PATH": "/nonexistent"}))
    assert any("does not load testconf2026" in m for m in msgs)
    assert any("required section" in m and "introduction" in m for m in msgs)


def test_anonymity_findings(venue_project):
    p, venue, _ = venue_project
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/sugam-lab/seam-paper.git"], cwd=p, check=True)
    t = TEX.replace(r"\author{Anonymous}", r"\author{Jane Q. Researcher\thanks{funded}}")
    t = t.replace("We cite", "Thanks to rharness-test. Acknowledgments below. We cite")
    t += "\n\\section*{Acknowledgements}\nsugam-lab/seam-paper\n"
    (p / "paper" / "main.tex").write_text(t)
    msgs = _msgs(VC.check_generic(p, venue, env={"PATH": "/nonexistent"}))
    anon = [m for m in msgs if "anonymity" in m]
    assert any("git author" in m and "rharness-test" in m for m in anon)
    assert any("author block" in m for m in anon)
    assert any("thanks" in m for m in anon)
    assert any("acknowledg" in m.lower() for m in anon)
    assert any("remote" in m and "sugam-lab/seam-paper" in m for m in anon)
    # every tex-derived finding names the string it matched
    assert any("author block" in m and "Jane Q. Researcher" in m for m in anon), anon
    assert any("thanks" in m and "funded" in m for m in anon), anon
    assert any("acknowledgements section present" in m and "Acknowledgements}" in m for m in anon), anon


def test_author_block_brace_and_eof_cases(venue_project):
    p, venue, _ = venue_project
    main = p / "paper" / "main.tex"
    # no trailing newline and nothing after the closing brace
    main.write_text(TEX.replace(r"\author{Anonymous}", "") + r"\author{Jane Doe}")
    msgs = _msgs(VC.check_generic(p, venue, env={"PATH": "/nonexistent"}))
    assert any("author block is not anonymous" in m and "Jane Doe" in m for m in msgs), msgs
    # a nested \thanks{} group must not truncate the block; the affiliation after \\ still leaks
    main.write_text(TEX.replace(r"\author{Anonymous}", r"\author{Anonymous\thanks{x} \\ MIT}"))
    msgs = _msgs(VC.check_generic(p, venue, env={"PATH": "/nonexistent"}))
    assert any("author block is not anonymous" in m and "MIT" in m for m in msgs), msgs
    assert any("thanks" in m for m in msgs), msgs
    # placeholder words everywhere, including after \\: anonymous
    main.write_text(TEX.replace(r"\author{Anonymous}",
                                r"\author{Anonymous Authors\thanks{x} \\ Anonymous Institution}"))
    msgs = _msgs(VC.check_generic(p, venue, env={"PATH": "/nonexistent"}))
    assert not any("author block is not anonymous" in m for m in msgs), msgs
    assert any("thanks" in m for m in msgs), msgs


def test_page_count_paths(venue_project, tmp_path):
    from test_pdfutil import _plain_pdf
    p, venue, _ = venue_project
    pdf = p / "paper" / "main.pdf"
    pdf.write_bytes(_plain_pdf(3))  # limit is 2
    msgs = _msgs(VC.check_generic(p, venue, env={"PATH": "/nonexistent"}))
    assert any("3 pages" in m and m.startswith("warning") and "main body" in m for m in msgs)
    b = tmp_path / "bin"; b.mkdir()
    (b / "pdftotext").write_text("#!/bin/sh\nprintf 'body\\n\\fbody 2\\n\\fmore body\\nReferences\\n'\n"); (b / "pdftotext").chmod(0o755)
    msgs = _msgs(VC.check_generic(p, venue, env={"PATH": str(b)}))
    # body text continues onto page 3 before References: 3 > 2 is an error
    assert any("main body is 3 pages" in m and m.startswith("error") for m in msgs), msgs
    (b / "pdftotext").write_text("#!/bin/sh\nprintf 'body\\n\\fbody 2\\n\\f017\\n\\nReferences\\n'\n")
    msgs = _msgs(VC.check_generic(p, venue, env={"PATH": str(b)}))
    # References opens page 3 (after a line number): the body is pages 1-2, within the limit
    assert not any("main body" in m for m in msgs), msgs
    (b / "pdftotext").write_text("#!/bin/sh\nprintf 'body\\n\\fReferences\\n\\fAppendix\\n'\n")
    msgs = _msgs(VC.check_generic(p, venue, env={"PATH": str(b)}))
    assert not any("main body" in m for m in msgs), msgs  # body ends on page 2: within the limit
    venue2 = dict(venue, page_limit={"main": 2})
    msgs = _msgs(VC.check_generic(p, venue2, env={"PATH": "/nonexistent"}))
    assert any("3 pages" in m and "limit is 2" in m and m.startswith("error") for m in msgs)


def test_lint_findings_downgrade_and_base_checks(venue_project):
    p, venue, d = venue_project
    f = VC.lint_findings(p, env={"PATH": "/nonexistent"})
    msgs = _msgs(f)
    assert all(m.startswith("warning") for m in msgs), msgs
    assert any("paper/main.pdf" in m and "missing" in m for m in msgs)
    assert not any("package check" in m for m in msgs)  # TEX has no TODO yet
    (p / "paper" / "main.tex").write_text(TEX + "% TODO\n")
    msgs = _msgs(VC.lint_findings(p, env={"PATH": "/nonexistent"}))
    assert any("package check" in m for m in msgs)
    blk = V.read_block(p); blk["state"] = "locked"; blk["locked_on"] = "2026-09-10"; V.write_block(p, blk)
    msgs = _msgs(VC.lint_findings(p, env={"PATH": "/nonexistent"}))
    assert any(m.startswith("error") and "missing2021" in m for m in msgs)


def test_deadline_base_checks(venue_project):
    import datetime as dt
    p, venue, d = venue_project
    blk = V.read_block(p); blk["state"] = "locked"; V.write_block(p, blk)
    near = dt.datetime(2027, 6, 1, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=-12)))
    msgs = _msgs(VC.lint_findings(p, env={"PATH": "/nonexistent"}, now=near))
    assert any("7 days" in m and "NOT YET" in m for m in msgs), msgs
    late = dt.datetime(2027, 7, 1, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=-12)))
    msgs = _msgs(VC.lint_findings(p, env={"PATH": "/nonexistent"}, now=late))
    assert sum("deadline" in m and "passed" in m for m in msgs) == 2


def test_malformed_package_finding_is_one_warning(venue_project):
    p, venue, d = venue_project
    (d / "checks.py").write_text(
        "def check(project_dir, venue):\n"
        "    return [('warning', 'paper/main.tex')]\n")
    msgs = _msgs(VC.lint_findings(p, env={"PATH": "/nonexistent"}))
    bad = [m for m in msgs if "malformed finding" in m]
    assert len(bad) == 1 and bad[0].startswith("warning checks.py:"), msgs


def test_lint_cli_includes_venue_rows_and_workspace_brief_skips_them(venue_project, ws):
    from conftest import run_cli
    from rharness.lint import lint_project, writing_template_region
    from rharness.lintcfg import load_lint_config
    p, venue, d = venue_project
    code, out, err = run_cli(["lint", "seam"], cwd=ws, env={"PATH": "/usr/bin:/bin"})
    assert code == 1, (code, out, err)  # the fixture project has findings
    assert "missing2021" in out

    cfg = load_lint_config(ws / "lint.toml")
    region = writing_template_region()
    off = lint_project(p, cfg, region, venue_checks=False)
    on = lint_project(p, cfg, region)
    assert len(on) > len(off)  # the fixture does produce venue findings

    def cell(findings):
        errors = sum(1 for f in findings if f.severity == "error")
        return f"{errors}E/{len(findings) - errors}W"

    code, out, err = run_cli(["brief"], cwd=ws)
    assert code == 0, err
    row = [l for l in out.splitlines() if l.startswith("| seam |")]
    assert len(row) == 1, out
    got = [c.strip() for c in row[0].strip().strip("|").split("|")][-1]
    assert got == cell(off), (got, cell(off), cell(on))
    assert got != cell(on)


def test_missing_package_dir_is_one_warning(venue_project):
    import shutil
    p, venue, d = venue_project
    shutil.rmtree(d)
    msgs = _msgs(VC.lint_findings(p))
    assert len(msgs) == 1 and "venue update" in msgs[0]


def test_style_message_wording_follows_the_marker(tmp_path):
    venue = {"template": {"files": ["testconf2026.sty"]}}
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.tex").write_text("\\documentclass{article}\n% rharness:venue-style\n")
    msg = VC._check_style(tmp_path, venue, "\\documentclass{article}\n")[0][2]
    assert "% rharness:venue-style line" in msg
    (paper / "main.tex").write_text("\\documentclass{article}\n")
    msg = VC._check_style(tmp_path, venue, "\\documentclass{article}\n")[0][2]
    assert "in the preamble" in msg and "rharness:venue-style" not in msg


def test_fail_on_error_separates_targeted_from_locked(venue_project, ws):
    from conftest import run_cli
    p, venue, d = venue_project
    ch = (p / "CHARTER.md").read_text().replace(
        "<!-- The negative result that means stop spending. State a threshold. -->",
        "Stop if the pilot AUC is below 0.55 on the held-out split.")
    (p / "CHARTER.md").write_text(ch)
    subprocess.run(["git", "add", "-A"], cwd=str(p), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "paper"], cwd=str(p), check=True, capture_output=True)
    code, out, err = run_cli(["lint", "--json", "--fail-on", "error"], cwd=ws)
    rows = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    assert any("missing2021" in r["message"] for r in rows), out
    assert all(r["severity"] == "warning" for r in rows), out
    assert code == 0, out
    blk = V.read_block(p); blk["state"] = "locked"; blk["locked_on"] = "2026-09-10"; V.write_block(p, blk)
    code, out, err = run_cli(["lint", "--json", "--fail-on", "error"], cwd=ws)
    assert code == 1, out
    assert any(json.loads(l)["severity"] == "error" and "missing2021" in l
               for l in out.splitlines() if l.startswith("{")), out


def _anon_msgs(p, venue, tex):
    (p / "paper" / "main.tex").write_text(tex)
    return [m for m in _msgs(VC.check_generic(p, venue, env={"PATH": "/nonexistent"})) if "anonymity" in m]


def test_author_block_hidden_if_style_option(venue_project):
    p, venue, _ = venue_project
    v = dict(venue, author_block={"hidden_if": r"\\usepackage\[[^\]]*\breview\b[^\]]*\]\{testconf2026\}"})
    named = TEX.replace(r"\author{Anonymous}", r"\author{rharness-test\thanks{funded} \\ MIT}")
    review = named.replace(r"\usepackage{testconf2026}", r"\usepackage[review]{testconf2026}")
    assert _anon_msgs(p, v, review) == []
    anon = _anon_msgs(p, v, named)
    assert any("author block" in m for m in anon) and any("thanks" in m for m in anon), anon
    assert any("git author name 'rharness-test'" in m for m in anon), anon
    leak = review.replace("We cite", "Work by rharness-test. We cite")
    assert any("git author name 'rharness-test'" in m for m in _anon_msgs(p, v, leak))


def test_author_block_hidden_unless_final_copy(venue_project):
    p, venue, _ = venue_project
    v = dict(venue, author_block={"hidden_unless": r"\\iclrfinalcopy\b"})
    named = TEX.replace(r"\author{Anonymous}", r"\author{Jane Realname}")
    assert _anon_msgs(p, v, named) == []
    final = named.replace(r"\begin{document}", "\\iclrfinalcopy\n\\begin{document}")
    assert any("author block" in m for m in _anon_msgs(p, v, final))
    commented = named.replace(r"\begin{document}", "% \\iclrfinalcopy\n\\begin{document}")
    assert _anon_msgs(p, v, commented) == []



def test_style_line_names_the_venue_preamble_line(tmp_path):
    from rharness.venuemeta import style_line, validate
    venue = {"template": {"repo": "x/y", "ref": "main", "files": ["acl.sty"]}}
    assert style_line(venue, "acl") == r"\usepackage{acl}"
    venue["style_line"] = r"\usepackage[review]{acl}"
    msg = VC._check_style(tmp_path, venue, "\\documentclass{article}\n")[0][2]
    assert r"add \usepackage[review]{acl}" in msg
    assert VC._check_style(tmp_path, venue, "\\usepackage[review]{acl}\n") == []
    assert any("style_line" in e for e in validate({"style_line": ""}))

"""Bibliography checks: parser, malformed entries, duplicate DOIs, uncited entries."""
import json
import subprocess

import pytest

from conftest import run_cli
from rharness import bibcheck as B

GOOD = """@article{smith2020,
  author = {Smith, A. and {Jones}, B.},
  title = {A {Title} with braces},
  journal = "J. of Things",
  year = 2020,
  doi = {10.1000/ABC.1}
}
"""


def test_parse_fields_and_lines():
    text = "% header\n@string{jt = \"J. Things\"}\n\n" + GOOD + "@misc(lee2021, title = {x} # \" y\")\n"
    entries = B.parse(text)
    assert [e.key for e in entries] == ["smith2020", "lee2021"]
    e = entries[0]
    assert e.type == "article" and e.line == 4 and e.problem is None
    assert e.fields["title"] == "A {Title} with braces"
    assert e.fields["journal"] == "J. of Things" and e.fields["year"] == "2020"
    assert entries[1].fields["title"] == "x y"


def test_parse_reports_unclosed_entry_and_stops():
    entries = B.parse("@article{a, title={x}\n@article{b, title={y}}\n")
    assert len(entries) == 1
    assert entries[0].key == "a" and "not closed" in entries[0].problem


def test_parse_reports_missing_key_and_bad_fields():
    entries = B.parse("@article{title = {x}}\n@book{k, title = {x} year = 2020}\n")
    assert "no citation key" in entries[0].problem
    assert entries[1].key == "k" and "field" in entries[1].problem


def test_normalize_doi():
    assert B.normalize_doi("https://doi.org/10.1000/ABC.1") == "10.1000/abc.1"
    assert B.normalize_doi("doi:10.1000/abc.1 ") == "10.1000/abc.1"
    assert B.normalize_doi("http://dx.doi.org/10.1000/abc.1") == "10.1000/abc.1"
    assert B.normalize_doi("not a doi") is None


def _check(tmp_path, bib, tex):
    f = tmp_path / "refs.bib"
    f.write_text(bib)
    return B.check(tex, [(f, "refs.bib")], main_rel="main.tex")


def test_check_duplicate_doi(tmp_path):
    bib = GOOD + GOOD.replace("smith2020", "smith2020b").replace("{10.1000/ABC.1}", "{https://doi.org/10.1000/abc.1}")
    rows = _check(tmp_path, bib, r"\cite{smith2020,smith2020b}")
    hit = [r for r in rows if "DOI" in r[2]]
    assert len(hit) == 1 and hit[0][0] == "warning" and hit[0][1] == "refs.bib"
    assert "smith2020" in hit[0][2] and "smith2020b" in hit[0][2] and "10.1000/abc.1" in hit[0][2]


def test_check_malformed_and_no_title(tmp_path):
    rows = _check(tmp_path, GOOD + "@misc{notitle, year = 2020}\n@article{broken, title={x}\n",
                  r"\cite{smith2020}\nocite{notitle}")
    msgs = [r[2] for r in rows]
    assert any("line 8" in m and "notitle" in m and "no title" in m for m in msgs), msgs
    assert any("line 9" in m and "broken" in m and "not closed" in m for m in msgs), msgs
    assert all(r[0] == "warning" for r in rows if "line" in r[2])


def test_check_uncited_is_one_summary(tmp_path):
    bib = "".join(f"@misc{{k{i}, title={{t}}}}\n" for i in range(8))
    rows = _check(tmp_path, bib, r"\citep[p.~2]{k0} \citet{k1}")
    unc = [r for r in rows if "never cited" in r[2]]
    assert len(unc) == 1 and unc[0][0] == "warning"
    assert unc[0][2].startswith("6 bib entries are never cited: k2, k3, k4, k5, k6, …")
    assert not any("never cited" in r[2] for r in _check(tmp_path, bib, r"\cite{k0}\nocite{*}"))


def test_check_unresolved_and_duplicate_keys_keep_messages(tmp_path):
    rows = _check(tmp_path, GOOD + GOOD, r"\cite{smith2020} \parencite{gone2019}")
    assert ("warning", "refs.bib", "duplicate bib key smith2020") in rows
    assert ("error", "main.tex", "citation key gone2019 is not in refs.bib") in rows


def test_check_clean_bib_has_no_findings(tmp_path):
    assert _check(tmp_path, GOOD, r"\cite{smith2020}") == []


def _lint_rows(ws):
    code, out, err = run_cli(["lint", "--json"], cwd=ws)
    return code, [json.loads(l) for l in out.splitlines() if l.startswith("{")]


def _commit(p):
    subprocess.run(["git", "add", "-A"], cwd=str(p), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=str(p), check=True, capture_output=True)


def test_project_without_venue_gets_bib_warnings(ws):
    run_cli(["new", "p"], cwd=ws)
    p = ws / "p"
    main = (p / "paper" / "main.tex").read_text().replace(r"\bibliographystyle", r"\cite{smith2020,gone}" + "\n\\bibliographystyle")
    (p / "paper" / "main.tex").write_text(main)
    (p / "paper" / "references.bib").write_text(GOOD + "@misc{spare, title={s}}\n")
    _commit(p)
    code, rows = _lint_rows(ws)
    bib = [r for r in rows if r["path"].startswith("paper/")]
    assert all(r["severity"] == "warning" for r in bib), bib
    msgs = [r["message"] for r in bib]
    assert "citation key gone is not in references.bib" in msgs, msgs
    assert any("never cited: spare" in m for m in msgs), msgs


def test_venue_project_reports_bib_findings_once(ws, tmp_path, home, monkeypatch):
    from venue_helpers import INDEX_SHORTHAND, make_project, point_workspace_at, venue_index_repo
    env, index, repo = venue_index_repo(tmp_path)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    point_workspace_at(ws, INDEX_SHORTHAND)
    p = make_project(ws)
    assert run_cli(["venue", "add", "testconf2026", "--project", p.name], cwd=ws)[0] == 0
    (p / "paper" / "main.tex").write_text("\\documentclass{article}\\cite{gone}\\bibliography{references}\n")
    (p / "paper" / "references.bib").write_text(GOOD)
    code, rows = _lint_rows(ws)
    msgs = [r["message"] for r in rows]
    assert msgs.count("citation key gone is not in references.bib") == 1, msgs
    assert sum("never cited: smith2020" in m for m in msgs) == 1, msgs

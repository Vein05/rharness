import re
from pathlib import Path
from conftest import REPO
from rharness.templates import PLACEHOLDERS
from rharness.regions import get_region

BASE = REPO / "base"
ALLOWED = re.compile(r"\{\{(" + "|".join(PLACEHOLDERS) + r")\}\}")
ANY = re.compile(r"\{\{[^{}]*\}\}")

REQUIRED_PROJECT_FILES = [
    "CHARTER.md", "AGENTS.md", "CLAUDE.md", "README.md", ".gitignore", ".gitattributes", "requirements.txt",
    "spec/README.md", "spec/scoring.md", "research/README.md",
    "paper/writing.md", "paper/Makefile", "paper/main.tex", "paper/references.bib",
    "data/README.md", "papers/INDEX.md", "handoff/README.md", "changelog/README.md",
    "tests/.gitkeep", "tools/.gitkeep",
]
ARCHETYPES = ["A-method-spec", "B-experiment-report", "C-survey-registry", "D-audit-log",
              "E-novelty-positioning", "F-cost-planning", "G-runbook", "H-results-ledger",
              "I-taxonomy-theory", "J-audit-guidance-pair", "K-so-what-playbook"]


def _text_files(root):
    for p in root.rglob("*"):
        if p.is_file():
            try:
                yield p, p.read_text()
            except UnicodeDecodeError:
                continue


def test_required_project_files_exist():
    for rel in REQUIRED_PROJECT_FILES:
        assert (BASE / "project" / rel).exists(), rel


def test_archetypes_exist_and_start_with_heading():
    for name in ARCHETYPES:
        p = BASE / "archetypes" / f"{name}.md"
        assert p.exists(), name
        assert p.read_text().lstrip().startswith("# "), name


def test_only_allowed_placeholders():
    for p, text in _text_files(BASE):
        for m in ANY.finditer(text):
            assert ALLOWED.fullmatch(m.group(0)), f"{p}: {m.group(0)}"


def test_charter_has_kill_criterion_section():
    t = (BASE / "project" / "CHARTER.md").read_text()
    assert "## Kill Criterion" in t and "**Status:**" in t


def test_spec_files_open_with_status():
    for name in ("README.md", "scoring.md"):
        t = (BASE / "project" / "spec" / name).read_text()
        assert re.search(r"^Status: (proposed|frozen|superseded)", t, re.M), name


def test_writing_guide_has_base_region():
    t = (BASE / "project" / "paper" / "writing.md").read_text()
    body = get_region(t, "base")
    assert body and "three-reader" in body.lower()


def test_gitattributes_has_lfs_rules():
    t = (BASE / "project" / ".gitattributes").read_text()
    for rule in ("data/*.jsonl", "papers/*.pdf", "traces/**"):
        assert rule in t and "filter=lfs" in t


def test_no_stripped_content_leaks():
    banned = re.compile(r"(arXiv[: ]?\d{4}\.\d{4,5}|\$\d|@[a-z0-9.-]+\.(edu|com)|Best exemplar)", re.I)
    for p, text in _text_files(BASE):
        m = banned.search(text)
        assert not m, f"{p}: {m.group(0) if m else ''}"


def test_no_leaks_in_plugins():
    terms = [t.strip() for t in (REPO / "tests" / "banned_terms.txt").read_text().splitlines() if t.strip()]
    for p, text in _text_files(REPO / "plugins"):
        low = text.lower()
        for t in terms:
            assert t.lower() not in low, f"{p}: {t}"


def test_project_agents_has_base_region_with_workspace_rules():
    t = (BASE / "project" / "AGENTS.md").read_text()
    body = get_region(t, "base")
    assert body and "rharness brief" in body and "Workspace rules" in body

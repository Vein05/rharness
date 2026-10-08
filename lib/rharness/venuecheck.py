"""Venue checks: the generic set parameterised by venue.json, plus a package's checks.py."""
import importlib.util
import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import bibcheck, gitutil, pdfutil
from .venue import load_venue, package_dir, read_block, VenueError
from .venuemeta import days_until

SECTION_RE = r"\\(?:section|chapter|subsection)\*?\s*\{[^}]*%s"
INPUT_RE = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
BIBRES_RE = re.compile(r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\]\s*)?\{([^}]+)\}")
NEAR_DAYS = 14
ANON_WORDS = {"anonymous", "author", "authors", "submission", "institution", "institutions",
              "affiliation", "affiliations", "and", "paper", "under", "review", "double",
              "blind", "anon"}


def tex_files(pdir: Path):
    paper = Path(pdir) / "paper"
    return sorted(paper.rglob("*.tex")) if paper.is_dir() else []


def tex_text(pdir: Path) -> str:
    return "\n".join(f.read_text(errors="replace") for f in tex_files(pdir))


@dataclass
class Layout:
    """Where a paper's files are. Finding paths are relative to root.

    A project keeps its paper under paper/ with fixed names. A bare LaTeX directory
    (`lint --venue`) has its main file found, its tex followed through \\input, and its
    bib files read from \\bibliography.
    """
    root: Path
    paper: Path
    main: Path
    tex: list
    bibs: list
    pdf: Path
    bare: bool = False

    def rel(self, path) -> str:
        r = Path(path).relative_to(self.root).as_posix()
        return "" if r == "." else r

    @property
    def paper_rel(self) -> str:
        r = self.rel(self.paper)
        return r + "/" if r else ""

    def sources(self):
        """Files whose change makes the PDF stale."""
        if not self.bare:
            return [f for pat in ("*.tex", "*.bib", "*.sty", "*.cls") for f in self.paper.rglob(pat)]
        styles = [f for pat in ("*.sty", "*.cls") for f in _visible(self.root, pat)]
        return list(self.tex) + [b for b in self.bibs if b.exists()] + styles


def project_layout(pdir) -> Layout:
    pdir = Path(pdir)
    paper = pdir / "paper"
    return Layout(pdir, paper, paper / "main.tex", tex_files(pdir), [paper / "references.bib"],
                  paper / "main.pdf")


def _visible(root: Path, pattern: str):
    """rglob without hidden directories (.git, .venv, ...)."""
    return sorted(f for f in root.rglob(pattern)
                  if not any(part.startswith(".") for part in f.relative_to(root).parts[:-1]))


def find_main(root: Path) -> Path:
    """main.tex if it has \\documentclass, else the one .tex file that does."""
    docs = [f for f in _visible(root, "*.tex")
            if "\\documentclass" in _strip_comments(f.read_text(errors="replace"))]
    if not docs:
        raise VenueError(f"no .tex file under {root} has \\documentclass; pass --main FILE")
    named = [f for f in docs if f.name == "main.tex"]
    if len(named) == 1:
        return named[0]
    if len(docs) == 1:
        return docs[0]
    names = ", ".join(f.relative_to(root).as_posix() for f in docs)
    raise VenueError(f"several .tex files under {root} have \\documentclass ({names}); pass --main FILE")


def _resolve_in(root: Path, base: Path, name: str, suffix: str):
    """LaTeX lookup of name relative to base: name+suffix first, then name. None outside root."""
    for cand in ((base / (name + suffix)), base / name):
        try:
            cand.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if cand.is_file():
            return cand
    return None


def bare_layout(root, main=None) -> Layout:
    root = Path(root)
    if main is None:
        main = find_main(root)
    else:
        main = Path(main) if Path(main).is_absolute() else root / main
        if not main.is_file():
            raise VenueError(f"--main {main} is not a file")
    tex, queue = [], [main]
    while queue:
        f = queue.pop(0)
        if f in tex:
            continue
        tex.append(f)
        for m in INPUT_RE.finditer(_strip_comments(f.read_text(errors="replace"))):
            got = _resolve_in(root, main.parent, m.group(1).strip(), ".tex")
            if got is not None:
                queue.append(got)
    bibs = []
    for f in tex:
        for m in BIBRES_RE.finditer(_strip_comments(f.read_text(errors="replace"))):
            for name in m.group(1).split(","):
                name = name.strip()
                if name:
                    b = main.parent / (name if name.endswith(".bib") else name + ".bib")
                    if b not in bibs:
                        bibs.append(b)
    return Layout(root, root, main, tex, bibs, main.with_suffix(".pdf"), bare=True)


def _as_layout(where) -> Layout:
    return where if isinstance(where, Layout) else project_layout(where)


def style_stem(venue: dict):
    tpl = venue.get("template") or {}
    for rel in tpl.get("files", []) + tpl.get("extract", []):
        if rel.endswith((".sty", ".cls")):
            return Path(rel).stem
    return None


def _strip_comments(tex: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", tex)


def _snippet(text: str, limit: int = 80) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[:limit - 1] + "…"


def _group_at(text: str, i: int):
    """The balanced {...} group starting at the first non-space char at or after i.

    Returns (content, end_index) or None when there is no brace group there.
    """
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] != "{":
        return None
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    return None


def _macro_group(text: str, macro: str):
    """Content of the first \\<macro>{...} group, brace-balanced, or None."""
    for m in re.finditer(r"\\" + macro + r"(?![A-Za-z])", text):
        got = _group_at(text, m.end())
        if got is not None:
            return got[0]
    return None


def _strip_groups(text: str, macro: str) -> str:
    """Remove every \\<macro>{...} (balanced) from text."""
    out = text
    while True:
        m = re.search(r"\\" + macro + r"(?![A-Za-z])", out)
        if not m:
            return out
        got = _group_at(out, m.end())
        end = got[1] if got is not None else m.end()
        out = out[:m.start()] + out[end:]


def _check_style(pdir, venue, tex):
    stem = style_stem(venue)
    if not stem:
        return []
    pat = re.compile(r"\\(usepackage|documentclass)(\[[^\]]*\])?\{[^}]*\b" + re.escape(stem) + r"\b[^}]*\}")
    if pat.search(tex):
        return []
    lay = _as_layout(pdir)
    main = lay.main
    marker = main.exists() and "% rharness:venue-style" in main.read_text(errors="replace")
    where = "at the % rharness:venue-style line" if marker else "in the preamble"
    return [("error", lay.rel(main),
             f"{main.name} does not load {stem}; add \\usepackage{{{stem}}} {where}")]


def _check_sections(venue, tex, paper_rel="paper/"):
    out = []
    for name in venue.get("required_sections", []):
        low = name.lower()
        if low == "abstract":
            ok = re.search(r"\\begin\{abstract\}", tex) is not None
        else:
            ok = re.search(SECTION_RE % re.escape(low), tex, re.I) is not None
        if not ok:
            out.append(("error", paper_rel, f"required section '{name}' not found in the tex sources"))
    return out


def project_bib_findings(pdir):
    """Bib checks for a project with no venue: every finding a warning, silent without a bib."""
    lay = project_layout(pdir)
    if not all(b.exists() for b in lay.bibs):
        return []
    return [("warning", path, msg) for _, path, msg in _check_cites(lay, _strip_comments(
        "\n".join(f.read_text(errors="replace") for f in lay.tex)))]


def _check_cites(pdir, tex):
    lay = _as_layout(pdir)
    if not lay.bibs:
        return [("warning", lay.rel(lay.main), "no \\bibliography{} in the tex sources; citation keys cannot be checked")]
    missing = [b for b in lay.bibs if not b.exists()]
    if missing:
        return [("warning", lay.rel(b), f"{b.name} missing; citation keys cannot be checked") for b in missing]
    return bibcheck.check(tex, [(b, lay.rel(b)) for b in lay.bibs], lay.rel(lay.main))


def _check_pages(pdir, venue, env):
    pl = venue.get("page_limit")
    lay = _as_layout(pdir)
    pdf = lay.pdf
    rel = lay.rel(pdf)
    if not pl or not pdf.exists():
        return []
    total = pdfutil.page_count(pdf, env=env)
    if total is None:
        return [("warning", rel, f"could not count pages in {rel}")]
    limit = pl["main"]
    excludes = pl.get("excludes") or []
    if not excludes:
        if total > limit:
            return [("error", rel, f"paper is {total} pages; limit is {limit}")]
        return []
    body_end = pdfutil.body_end(pdf, excludes, env=env)
    if body_end is None:
        if pdfutil.have_tool("pdftotext", env=env):
            body_end = total
        else:
            return [("warning", rel,
                     f"paper is {total} pages total; the limit of {limit} applies to the main body and the "
                     f"{'/'.join(excludes)} page could not be located (install pdftotext)")]
    if body_end > limit:
        return [("error", rel, f"main body is {body_end} pages; limit is {limit} (excluding {', '.join(excludes)})")]
    return []


def _git_authors(pdir):
    r = gitutil.git(["log", "--format=%an"], pdir)
    names = set()
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            n = line.strip()
            if len(n) >= 3:
                names.add(n)
    return sorted(names)


def _git_remotes(pdir):
    r = gitutil.git(["remote", "-v"], pdir)
    out = set()
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            m = re.search(r"[:/]([\w.-]+/[\w.-]+?)(?:\.git)?\s", line + " ")
            if m:
                out.add(m.group(1))
    return sorted(out)


def _is_anonymous_author(block: str) -> bool:
    """True when every word left in the \\author{...} body is a placeholder.

    \\thanks{} groups and LaTeX control sequences are removed first; what remains is
    split into words on non-letters. An empty word list counts as anonymous.
    """
    body = _strip_groups(block, "thanks")
    body = re.sub(r"\\\\|\\[a-zA-Z]+", " ", body)
    words = [w.lower() for w in re.split(r"[^A-Za-z]+", body) if w]
    return all(w in ANON_WORDS for w in words)


def author_block_hidden(venue, plain_tex: str) -> bool:
    """True when the venue's style hides \\author and \\thanks in this build (venue.json author_block)."""
    rule = venue.get("author_block") or {}
    if "hidden_if" in rule:
        return re.search(rule["hidden_if"], plain_tex) is not None
    if "hidden_unless" in rule:
        return re.search(rule["hidden_unless"], plain_tex) is None
    return False


def _check_anonymity(pdir, venue, tex, env):
    if not venue.get("anonymous"):
        return []
    out = []
    lay = _as_layout(pdir)
    pdir, pdf, main_rel = lay.root, lay.pdf, lay.rel(lay.main)
    plain = _strip_comments(tex)
    hidden = author_block_hidden(venue, plain)
    scanned = pdfutil.pdf_text(pdf, env=env) if pdf.exists() else None
    where = lay.rel(pdf) if scanned is not None else lay.paper_rel
    source = _strip_groups(_strip_groups(plain, "author"), "thanks") if hidden else plain
    haystack = (scanned if scanned is not None else source).lower()
    for name in _git_authors(pdir):
        if name.lower() in haystack:
            out.append(("error", where, f"anonymity: git author name '{name}' appears in the paper text"))
    for remote in _git_remotes(pdir):
        if remote.lower() in haystack:
            out.append(("error", where, f"anonymity: git remote '{remote}' appears in the paper text"))
    block = None if hidden else _macro_group(plain, "author")
    if block is not None:
        if not _is_anonymous_author(block):
            out.append(("error", main_rel,
                        f"anonymity: author block is not anonymous: {_snippet(block)}"))
    thanks = None if hidden else _macro_group(plain, "thanks")
    if thanks is not None:
        out.append(("error", main_rel, f"anonymity: \\thanks{{}} present: {_snippet(thanks)}"))
    ack = re.search(r"\\section\*?\{\s*acknowledg", plain, re.I)
    if ack:
        line = plain[plain.rfind("\n", 0, ack.start()) + 1:]
        line = line.split("\n", 1)[0]
        out.append(("error", main_rel,
                    f"anonymity: acknowledgements section present: {_snippet(line)}"))
    return out


def check_generic(pdir, venue, env=None, layout=None):
    lay = layout or project_layout(pdir)
    tex = "\n".join(f.read_text(errors="replace") for f in lay.tex)
    out = []
    out += _check_style(lay, venue, _strip_comments(tex))
    out += _check_sections(venue, _strip_comments(tex), lay.paper_rel)
    out += _check_cites(lay, _strip_comments(tex))
    out += _check_pages(lay, venue, env)
    out += _check_anonymity(lay, venue, tex, env)
    return out


def load_package_checks(pkg_dir):
    f = Path(pkg_dir) / "checks.py"
    if not f.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"rharness_venue_checks_{Path(pkg_dir).name}", f)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # a broken package must not take lint down
        return lambda pdir, venue, _e=e: [("warning", "checks.py", f"package checks failed to load: {_e}")]
    return getattr(mod, "check", None)


def pdf_state(pdir, layout=None):
    lay = layout or project_layout(pdir)
    pdf, rel = lay.pdf, lay.rel(lay.pdf)
    if not pdf.exists():
        if lay.bare:
            return "missing", f"{rel} missing; compile {lay.rel(lay.main)} so page count and PDF text can be checked"
        return "missing", "paper/main.pdf missing; run `rharness paper build` or download the compiled PDF from Overleaf into paper/main.pdf"
    newest = max((f.stat().st_mtime for f in lay.sources()), default=0.0)
    if newest > pdf.stat().st_mtime:
        if lay.bare:
            return "stale", f"{rel} is older than the tex, bib, or style sources; recompile it before trusting page counts"
        return "stale", "paper/main.pdf is older than the tex, bib, or style sources; rebuild it (or re-download from Overleaf) before trusting page counts"
    return "ok", ""


def _success_not_yet(pdir) -> bool:
    ch = Path(pdir) / "CHARTER.md"
    if not ch.exists():
        return True
    m = re.search(r"^## Primary Success Criterion\s*$(.*?)(?=^## |\Z)", ch.read_text(errors="replace"), re.M | re.S)
    return bool(m) and "NOT YET" in m.group(1)


def lint_findings(pdir, env=None, now=None):
    pdir = Path(pdir)
    block = read_block(pdir)
    if not block:
        return []
    name = block["name"]
    pkg = package_dir(name)
    try:
        venue = load_venue(pkg)
    except VenueError as e:
        return [("warning", ".rharness/project.json",
                 f"venue {name}: package not usable ({e}); run `rharness venue update`")]
    locked = block.get("state") == "locked"
    out = []
    state, msg = pdf_state(pdir)
    if state != "ok":
        out.append(("warning", "paper/main.pdf", msg))
    out += _passed_deadlines(name, venue, now, "CHARTER.md", "; `rharness venue change` or `unlock`")
    if locked:
        d = days_until(venue["deadlines"][venue["primary"]], now=now)
        if 0 <= d <= NEAR_DAYS and _success_not_yet(pdir):
            out.append(("warning", "CHARTER.md", f"venue {name} locked and the {venue['primary']} deadline is in {d} days but the success criterion is still NOT YET"))
    findings = check_generic(pdir, venue, env=env) + _package_findings(pkg, pdir, venue)
    for sev, path, m in findings:
        out.append((sev if locked else "warning", path, m))
    return out


def _passed_deadlines(name, venue, now, path, hint=""):
    out = []
    for key, iso in venue["deadlines"].items():
        d = days_until(iso, now=now)
        if d < 0:
            out.append(("warning", path, f"venue {name} {key} deadline {iso[:10]} passed {-d} days ago{hint}"))
    return out


def _package_findings(pkg, pdir, venue):
    findings = []
    fn = load_package_checks(pkg)
    if fn is not None:
        try:
            returned = list(fn(pdir, venue) or [])
        except Exception as e:
            returned = []
            findings.append(("warning", "checks.py", f"package checks raised: {e}"))
        for item in returned:
            if isinstance(item, (list, tuple)) and len(item) == 3 and item[0] in ("error", "warning"):
                findings.append(tuple(item))
            else:
                findings.append(("warning", "checks.py",
                                 f"package checks returned a malformed finding: {repr(item)[:80]}"))
    return findings


def bare_findings(root, venue, pkg, main=None, env=None, now=None):
    """Venue checks on a LaTeX directory with no rharness files, severity as returned.

    Raises VenueError when no main file can be chosen.
    """
    root = Path(root)
    lay = bare_layout(root, main)
    out = []
    state, msg = pdf_state(root, lay)
    if state != "ok":
        out.append(("warning", lay.rel(lay.pdf), msg))
    out += _passed_deadlines(venue["name"], venue, now, "")
    return out + check_generic(root, venue, env=env, layout=lay) + _package_findings(pkg, root, venue)

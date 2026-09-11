"""Venue checks: the generic set parameterised by venue.json, plus a package's checks.py."""
import importlib.util
import os
import re
from pathlib import Path

from . import gitutil, pdfutil
from .venue import load_venue, package_dir, read_block, VenueError
from .venuemeta import days_until

CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}")
BIBKEY_RE = re.compile(r"^@\w+\s*\{\s*([^,\s]+)\s*,", re.M)
SECTION_RE = r"\\(?:section|chapter|subsection)\*?\s*\{[^}]*%s"
NEAR_DAYS = 14


def tex_files(pdir: Path):
    paper = Path(pdir) / "paper"
    return sorted(paper.rglob("*.tex")) if paper.is_dir() else []


def tex_text(pdir: Path) -> str:
    return "\n".join(f.read_text(errors="replace") for f in tex_files(pdir))


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
    return [("error", "paper/main.tex",
             f"main.tex does not load {stem}; add \\usepackage{{{stem}}} at the % rharness:venue-style line")]


def _check_sections(venue, tex):
    out = []
    for name in venue.get("required_sections", []):
        low = name.lower()
        if low == "abstract":
            ok = re.search(r"\\begin\{abstract\}", tex) is not None
        else:
            ok = re.search(SECTION_RE % re.escape(low), tex, re.I) is not None
        if not ok:
            out.append(("error", "paper/", f"required section '{name}' not found in the tex sources"))
    return out


def _check_cites(pdir, tex):
    out = []
    bib = Path(pdir) / "paper" / "references.bib"
    if not bib.exists():
        return [("warning", "paper/references.bib", "references.bib missing; citation keys cannot be checked")]
    keys = BIBKEY_RE.findall(bib.read_text(errors="replace"))
    dups = sorted({k for k in keys if keys.count(k) > 1})
    for k in dups:
        out.append(("warning", "paper/references.bib", f"duplicate bib key {k}"))
    cited = set()
    for group in CITE_RE.findall(tex):
        cited.update(x.strip() for x in group.split(",") if x.strip())
    for k in sorted(cited - set(keys)):
        out.append(("error", "paper/main.tex", f"citation key {k} is not in references.bib"))
    return out


def _check_pages(pdir, venue, env):
    pl = venue.get("page_limit")
    pdf = Path(pdir) / "paper" / "main.pdf"
    if not pl or not pdf.exists():
        return []
    total = pdfutil.page_count(pdf, env=env)
    if total is None:
        return [("warning", "paper/main.pdf", "could not count pages in paper/main.pdf")]
    limit = pl["main"]
    excludes = pl.get("excludes") or []
    if not excludes:
        if total > limit:
            return [("error", "paper/main.pdf", f"paper is {total} pages; limit is {limit}")]
        return []
    body_end = pdfutil.heading_page(pdf, excludes, env=env)
    if body_end is None:
        if pdfutil.have_tool("pdftotext", env=env):
            body_end = total
        else:
            return [("warning", "paper/main.pdf",
                     f"paper is {total} pages total; the limit of {limit} applies to the main body and the "
                     f"{'/'.join(excludes)} page could not be located (install pdftotext)")]
    if body_end > limit:
        return [("error", "paper/main.pdf", f"main body is {body_end} pages; limit is {limit} (excluding {', '.join(excludes)})")]
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


def _check_anonymity(pdir, venue, tex, env):
    if not venue.get("anonymous"):
        return []
    out = []
    pdf = Path(pdir) / "paper" / "main.pdf"
    scanned = pdfutil.pdf_text(pdf, env=env) if pdf.exists() else None
    where = "paper/main.pdf" if scanned is not None else "paper/"
    haystack = (scanned if scanned is not None else _strip_comments(tex)).lower()
    for name in _git_authors(pdir):
        if name.lower() in haystack:
            out.append(("error", where, f"anonymity: git author name '{name}' appears in the paper text"))
    for remote in _git_remotes(pdir):
        if remote.lower() in haystack:
            out.append(("error", where, f"anonymity: git remote '{remote}' appears in the paper text"))
    plain = _strip_comments(tex)
    block = _macro_group(plain, "author")
    if block is not None:
        body = _strip_groups(block, "thanks").split("\\\\", 1)[0]
        letters = re.sub(r"[^A-Za-z]", "", body)
        if letters and letters.lower() not in ("anonymous", "anonymousauthors", "anonymoussubmission"):
            out.append(("error", "paper/main.tex",
                        f"anonymity: author block is not anonymous: {_snippet(block)}"))
    thanks = _macro_group(plain, "thanks")
    if thanks is not None:
        out.append(("error", "paper/main.tex", f"anonymity: \\thanks{{}} present: {_snippet(thanks)}"))
    ack = re.search(r"\\section\*?\{\s*acknowledg", plain, re.I)
    if ack:
        line = plain[plain.rfind("\n", 0, ack.start()) + 1:]
        line = line.split("\n", 1)[0]
        out.append(("error", "paper/main.tex",
                    f"anonymity: acknowledgements section present: {_snippet(line)}"))
    return out


def check_generic(pdir, venue, env=None):
    pdir = Path(pdir)
    tex = tex_text(pdir)
    out = []
    out += _check_style(pdir, venue, _strip_comments(tex))
    out += _check_sections(venue, _strip_comments(tex))
    out += _check_cites(pdir, _strip_comments(tex))
    out += _check_pages(pdir, venue, env)
    out += _check_anonymity(pdir, venue, tex, env)
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


def pdf_state(pdir):
    paper = Path(pdir) / "paper"
    pdf = paper / "main.pdf"
    if not pdf.exists():
        return "missing", "paper/main.pdf missing; run `rharness paper build` or download the compiled PDF from Overleaf into paper/main.pdf"
    newest = 0.0
    for pat in ("*.tex", "*.bib", "*.sty", "*.cls"):
        for f in paper.rglob(pat):
            newest = max(newest, f.stat().st_mtime)
    if newest > pdf.stat().st_mtime:
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
    for key, iso in venue["deadlines"].items():
        d = days_until(iso, now=now)
        if d < 0:
            out.append(("warning", "CHARTER.md", f"venue {name} {key} deadline {iso[:10]} passed {-d} days ago; `rharness venue change` or `unlock`"))
    if locked:
        d = days_until(venue["deadlines"][venue["primary"]], now=now)
        if 0 <= d <= NEAR_DAYS and _success_not_yet(pdir):
            out.append(("warning", "CHARTER.md", f"venue {name} locked and the {venue['primary']} deadline is in {d} days but the success criterion is still NOT YET"))
    findings = check_generic(pdir, venue, env=env)
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
    for sev, path, m in findings:
        out.append((sev if locked else "warning", path, m))
    return out

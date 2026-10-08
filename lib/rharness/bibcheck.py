"""Bibliography checks: citation keys, duplicate keys and DOIs, malformed and uncited entries.

Local and deterministic: no network, no metadata lookup. Findings are
(severity, path, message) like the venue checks.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

CITE_RE = re.compile(r"\\(?:no|paren|text|foot|auto|super|smart|full)?[Cc]ite[a-zA-Z]*\*?\s*"
                     r"(?:\[[^\]]*\]\s*)*\{([^}]*)\}")
ENTRY_RE = re.compile(r"@\s*([A-Za-z]+)\s*([{(])")
FIELD_RE = re.compile(r"\s*([A-Za-z][\w:.+-]*)\s*=\s*")
DOI_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/\S+)$", re.I)
SKIP_TYPES = {"comment", "string", "preamble"}
UNCITED_SHOWN = 5


@dataclass
class Entry:
    type: str
    key: str
    line: int
    fields: dict = field(default_factory=dict)
    problem: str = None


def _close(text: str, i: int, opener: str):
    """Index of the delimiter closing the entry opened at text[i], or None."""
    closer = "}" if opener == "{" else ")"
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if closer == "}" and depth == 0:
                return j
        elif closer == ")" and c == ")" and depth == 0:
            return j
        j += 1
    return None


def _value(body: str, i: int):
    """Read one field value (pieces joined by #) from body[i:]. Returns (text, end) or None."""
    parts = []
    while True:
        while i < len(body) and body[i].isspace():
            i += 1
        if i >= len(body):
            return None
        c = body[i]
        if c == "{":
            depth, j = 0, i
            while j < len(body):
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            else:
                return None
            parts.append(body[i + 1:j])
            i = j + 1
        elif c == '"':
            depth, j = 0, i + 1
            while j < len(body) and not (body[j] == '"' and depth == 0):
                depth += {"{": 1, "}": -1}.get(body[j], 0)
                j += 1
            if j >= len(body):
                return None
            parts.append(body[i + 1:j])
            i = j + 1
        else:
            m = re.match(r"[^\s,#{}\"]+", body[i:])
            if not m:
                return None
            parts.append(m.group(0))
            i += m.end()
        while i < len(body) and body[i].isspace():
            i += 1
        if i < len(body) and body[i] == "#":
            i += 1
            continue
        return "".join(parts), i


def _fields(body: str):
    """(fields, problem) for the text after the citation key's comma."""
    out = {}
    i = 0
    last = None
    while True:
        while i < len(body) and (body[i].isspace() or body[i] == ","):
            i += 1
        if i >= len(body):
            return out, None
        m = FIELD_RE.match(body, i)
        if not m:
            where = f"after field {last}" if last else "at the first field"
            return out, f"cannot read the fields {where}"
        name = m.group(1).lower()
        got = _value(body, m.end())
        if got is None:
            return out, f"cannot read the value of field {name}"
        out[name], i = got
        last = name
        while i < len(body) and body[i].isspace():
            i += 1
        if i < len(body) and body[i] != ",":
            return out, f"cannot read the fields after field {name} (missing comma?)"


def parse(text: str):
    """Entries in a .bib file, in order. An entry that is not closed ends the parse."""
    out = []
    pos = 0
    while True:
        m = ENTRY_RE.search(text, pos)
        if not m:
            return out
        typ = m.group(1).lower()
        line = text.count("\n", 0, m.start()) + 1
        end = _close(text, m.end() - 1, m.group(2))
        if typ in SKIP_TYPES:
            if end is None:
                return out
            pos = end + 1
            continue
        if end is None:
            key = text[m.end():].split(",", 1)[0].strip()
            key = key if key and "=" not in key and "\n" not in key else ""
            out.append(Entry(typ, key, line, problem="entry is not closed; check its braces"))
            return out
        body = text[m.end():end]
        head, sep, rest = body.partition(",")
        key = head.strip()
        if not sep or not key or "=" in key or re.search(r"\s", key):
            out.append(Entry(typ, "", line, problem="entry has no citation key"))
        else:
            fields, problem = _fields(rest)
            out.append(Entry(typ, key, line, fields, problem))
        pos = end + 1


def normalize_doi(value: str):
    m = DOI_RE.match(value.strip())
    return m.group(1).lower() if m else None


def cited_keys(tex: str):
    keys = set()
    for group in CITE_RE.findall(tex):
        keys.update(x.strip() for x in group.split(",") if x.strip())
    return keys


def check(tex: str, bibs, main_rel: str):
    """Findings for comment-stripped tex against bibs, a list of (path, rel) that exist."""
    out = []
    keys, dup_keys, dois = set(), {}, {}
    names = ", ".join(Path(p).name for p, _ in bibs)
    for path, rel in bibs:
        for e in parse(Path(path).read_text(errors="replace")):
            label = f"line {e.line}: @{e.type}" + (f" {e.key}" if e.key else "")
            if e.problem:
                out.append(("warning", rel, f"{label}: {e.problem}"))
            elif "title" not in e.fields:
                out.append(("warning", rel, f"{label} has no title field"))
            if not e.key:
                continue
            if e.key in keys:
                dup_keys.setdefault(e.key, rel)
            keys.add(e.key)
            doi = normalize_doi(e.fields.get("doi", ""))
            if doi:
                first = dois.setdefault(doi, (e.key, rel))
                if first[0] != e.key:
                    out.append(("warning", rel, f"DOI {doi} appears in entries {first[0]} and {e.key}"))
    for k in sorted(dup_keys):
        out.append(("warning", dup_keys[k], f"duplicate bib key {k}"))
    cited = cited_keys(tex)
    for k in sorted(cited - keys - {"*"}):
        out.append(("error", main_rel, f"citation key {k} is not in {names}"))
    if "*" not in cited:
        uncited = sorted(keys - cited)
        if uncited:
            shown = ", ".join(uncited[:UNCITED_SHOWN]) + (", …" if len(uncited) > UNCITED_SHOWN else "")
            noun = "entry is" if len(uncited) == 1 else "entries are"
            out.append(("warning", bibs[0][1], f"{len(uncited)} bib {noun} never cited: {shown}"))
    return out

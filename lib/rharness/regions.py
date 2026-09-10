"""Marked regions inside user-owned markdown files (AGENTS.md, CLAUDE.md, writing.md)."""
import re


def begin_marker(name: str) -> str:
    return f"<!-- rharness:begin {name} -->"


def end_marker(name: str) -> str:
    return f"<!-- rharness:end {name} -->"


def _pattern(name: str):
    return re.compile(re.escape(begin_marker(name)) + r"\n(.*?)" + re.escape(end_marker(name)) + r"\n?",
                      re.DOTALL)


def get_region(text: str, name: str):
    m = _pattern(name).search(text)
    return m.group(1) if m else None


def upsert_region(text: str, name: str, body: str) -> str:
    if not body.endswith("\n"):
        body += "\n"
    block = f"{begin_marker(name)}\n{body}{end_marker(name)}\n"
    pat = _pattern(name)
    if pat.search(text):
        return pat.sub(lambda _m: block, text, count=1)
    if text and not text.endswith("\n"):
        text += "\n"
    if text:
        text += "\n"
    return text + block


def remove_region(text: str, name: str) -> str:
    pat = _pattern(name)
    if not pat.search(text):
        return text
    out = pat.sub("", text, count=1)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def list_regions(text: str):
    return re.findall(r"<!-- rharness:begin ([^ ]+) -->", text)

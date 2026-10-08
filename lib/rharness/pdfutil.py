"""Read PDFs without a TeX install: page count, text, and heading location."""
import os
import re
import shutil
import subprocess
import zlib
from pathlib import Path

_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
_PAGE_RE = re.compile(rb"/Type\s*/Page(?![sA-Za-z])")
_PAGES_COUNT_RE = re.compile(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", re.S)


def have_tool(name: str, env=None) -> bool:
    env = env or os.environ
    return shutil.which(name, path=env.get("PATH")) is not None


def _run(cmd, env=None, timeout=30):
    env = env or os.environ
    exe = shutil.which(cmd[0], path=env.get("PATH"))
    if exe is None:
        return None
    try:
        return subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout,
                              env=dict(os.environ, PATH=env.get("PATH", os.environ.get("PATH", ""))))
    except (OSError, subprocess.TimeoutExpired):
        return None


def _count_pure(data: bytes):
    if not data.startswith(b"%PDF"):
        return None
    chunks = [data]
    for m in _STREAM_RE.finditer(data):
        try:
            chunks.append(zlib.decompress(m.group(1)))
        except zlib.error:
            continue
    text = b"\n".join(chunks)
    n = len(_PAGE_RE.findall(text))
    if n:
        return n
    m = _PAGES_COUNT_RE.search(text)
    return int(m.group(1)) if m else None


def page_count(path, use_tools: bool = True, env=None):
    path = Path(path)
    if not path.exists():
        return None
    if use_tools:
        r = _run(["pdfinfo", str(path)], env=env)
        if r is not None and r.returncode == 0:
            m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
            if m:
                return int(m.group(1))
    try:
        return _count_pure(path.read_bytes())
    except OSError:
        return None


def pdf_text(path, env=None):
    path = Path(path)
    if not path.exists():
        return None
    r = _run(["pdftotext", "-layout", str(path), "-"], env=env, timeout=60)
    if r is None or r.returncode != 0:
        return None
    return r.stdout


def heading_page(path, headings, env=None):
    text = pdf_text(path, env=env)
    if text is None:
        return None
    wanted = {h.strip().lower() for h in headings}
    for i, page in enumerate(text.split("\f"), start=1):
        for line in page.splitlines():
            s = re.sub(r"^\s*(\d+(\.\d+)*\s+)?", "", line).strip().lower()
            if s in wanted:
                return i
    return None

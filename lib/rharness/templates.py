"""Placeholder rendering and template-tree copying."""
import re
import shutil
from pathlib import Path

PLACEHOLDERS = ("slug", "title", "date", "workspace")
_PATTERN = re.compile(r"\{\{(" + "|".join(PLACEHOLDERS) + r")\}\}")


def render(text: str, ctx: dict) -> str:
    def sub(m):
        key = m.group(1)
        return str(ctx[key]) if key in ctx else m.group(0)
    return _PATTERN.sub(sub, text)


def _is_text(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return b"\x00" not in data


def copy_tree(src: Path, dst: Path, ctx: dict, overwrite: bool = False):
    """Copy every file under src into dst, rendering text files.

    Returns (written, skipped) as lists of POSIX relative paths, sorted.
    """
    written, skipped = [], []
    for path in sorted(p for p in Path(src).rglob("*") if p.is_file()):
        rel = path.relative_to(src).as_posix()
        target = Path(dst) / rel
        if target.exists() and not overwrite:
            skipped.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        if _is_text(data):
            target.write_text(render(data.decode("utf-8"), ctx))
        else:
            target.write_bytes(data)
        shutil.copymode(path, target)
        written.append(rel)
    return written, skipped

"""Thin, non-raising wrappers around git."""
import datetime as _dt
import shutil
import subprocess
from pathlib import Path


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def init_repo(path):
    """git init with an initial branch of main; falls back for git < 2.28."""
    r = git(["init", "-q", "-b", "main"], path)
    if r.returncode != 0:
        r = git(["init", "-q"], path)
    return r


def is_repo(path) -> bool:
    return (Path(path) / ".git").exists()


def commit_count(path) -> int:
    if not is_repo(path):
        return 0
    r = git(["rev-list", "--all", "--count"], path)
    return int(r.stdout.strip() or 0) if r.returncode == 0 else 0


def dirty_count(path) -> int:
    if not is_repo(path):
        return 0
    r = git(["status", "--porcelain"], path)
    return len([l for l in r.stdout.splitlines() if l.strip()]) if r.returncode == 0 else 0


def newest_commit_date(path):
    if not is_repo(path):
        return None
    r = git(["log", "-1", "--format=%cs"], path)
    out = r.stdout.strip()
    return out if r.returncode == 0 and out else None


def commit_days(path, since_days: int):
    if not is_repo(path):
        return set()
    since = (_dt.date.today() - _dt.timedelta(days=since_days)).isoformat()
    r = git(["log", f"--since={since}", "--format=%cs"], path)
    return set(l.strip() for l in r.stdout.splitlines() if l.strip()) if r.returncode == 0 else set()


def has_lfs() -> bool:
    return shutil.which("git-lfs") is not None


def is_ignored(path, rel) -> bool:
    r = git(["check-ignore", "-q", rel], path)
    return r.returncode == 0

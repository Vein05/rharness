"""`rharness paper build`: latexmk (via make when a Makefile exists) with a tlmgr missing-package loop."""
import os
import re
import shutil
import subprocess
from pathlib import Path

from .venue import TINYTEX

MISSING_RE = re.compile(r"! LaTeX Error: File `([^']+)' not found|! I can't find file `([^']+)'")
# tlmgr output becomes argv for `tlmgr install`, so only plain package names are accepted
PKG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
TAIL = 40


def find_engine(env=None) -> dict:
    env = env or os.environ
    path = env.get("PATH")
    return {n: shutil.which(n, path=path) for n in ("latexmk", "pdflatex", "tlmgr", "make")}


def missing_file(log_text: str):
    m = MISSING_RE.search(log_text or "")
    return (m.group(1) or m.group(2)) if m else None


def _run(cmd, cwd, env, timeout):
    full = dict(os.environ)
    # Engines are invoked by absolute path; a caller-supplied PATH goes first so the
    # tools it names win, with the ambient PATH behind it for the shell utilities
    # latexmk, make and tlmgr shell out to.
    given = (env or {}).get("PATH")
    if given:
        full["PATH"] = given + os.pathsep + full.get("PATH", "")
    try:
        return subprocess.run(cmd, cwd=str(cwd), env=full, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", f"{cmd[0]} timed out after {timeout}s")
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))


def tlmgr_package_for(filename: str, env=None):
    eng = find_engine(env)
    if not eng["tlmgr"]:
        return None
    r = _run([eng["tlmgr"], "search", "--file", "--global", "/" + filename], Path.cwd(), env, 120)
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        line = line.rstrip()
        if line.endswith(":") and not line.startswith(("\t", " ")):
            name = line[:-1].strip()
            return name if PKG_NAME_RE.match(name) else None
    return None


def _tail(*texts):
    lines = "\n".join(t for t in texts if t).splitlines()
    return "\n".join(lines[-TAIL:])


def build(paper_dir, env=None, max_rounds=5, timeout=600):
    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        return 2, f"no paper/ directory at {paper_dir}"
    eng = find_engine(env)
    if not eng["latexmk"]:
        if eng["tlmgr"]:
            return 2, "latexmk is missing; install it with `tlmgr install latexmk`"
        return 2, (f"no TeX engine on PATH. Install TinyTeX with `{TINYTEX}`, or download the compiled PDF from "
                   "Overleaf into paper/main.pdf")
    if (paper_dir / "Makefile").exists() and eng["make"]:
        cmd = [eng["make"]]
    else:
        cmd = [eng["latexmk"], "-pdf", "-interaction=nonstopmode", "main.tex"]
    installed = []
    while True:
        r = _run(cmd, paper_dir, env, timeout)
        log = paper_dir / "main.log"
        log_text = log.read_text(errors="replace") if log.exists() else ""
        if r.returncode == 0 and (paper_dir / "main.pdf").exists():
            note = f" (installed {', '.join(installed)})" if installed else ""
            return 0, f"built {paper_dir.name}/main.pdf{note}"
        missing = missing_file(r.stdout + "\n" + r.stderr + "\n" + log_text)
        if missing is None:
            return 1, f"build failed ({' '.join(Path(c).name for c in cmd)} exited {r.returncode}):\n" + _tail(r.stdout, r.stderr, log_text)
        if not eng["tlmgr"]:
            return 1, f"{missing} not found and tlmgr is not on PATH; install the package that provides it and rebuild:\n" + _tail(r.stdout, r.stderr, log_text)
        if len(installed) >= max_rounds:
            return 1, f"gave up after installing {len(installed)} package(s): {', '.join(installed)}"
        pkg = tlmgr_package_for(missing, env)
        if pkg is None:
            return 1, f"{missing} not found; tlmgr could not find a package for it (offline?)"
        ins = _run([eng["tlmgr"], "install", pkg], paper_dir, env, 600)
        if ins.returncode != 0:
            return 1, f"{missing} not found; `tlmgr install {pkg}` failed (offline?):\n" + _tail(ins.stdout, ins.stderr)
        installed.append(pkg)

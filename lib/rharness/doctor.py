"""Machine and workspace health checks."""
import json
import os
import shutil
import sys
from pathlib import Path


def _hook_present(settings_path: Path) -> bool:
    if not settings_path.exists():
        return False
    try:
        data = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return False
    for entry in data.get("hooks", {}).get("PreToolUse", []):
        if entry.get("matcher") == "Bash":
            for h in entry.get("hooks", []):
                if "rtk-rewrite" in str(h.get("command", "")):
                    return True
    return False


def _session_hooks_present(settings_path: Path) -> bool:
    if not settings_path.exists():
        return False
    try:
        data = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return False
    hooks = data.get("hooks", {})
    has_start = any("rharness brief" in str(h.get("command", ""))
                    for e in hooks.get("SessionStart", []) for h in e.get("hooks", []))
    has_stop = any("session-check" in str(h.get("command", ""))
                   for e in hooks.get("Stop", []) for h in e.get("hooks", []))
    return has_start and has_stop


def doctor_checks(ws, env=None):
    env = env or os.environ

    def which(n):
        return shutil.which(n, path=env.get("PATH"))

    checks = []
    v = sys.version_info
    checks.append(("python >= 3.9", v >= (3, 9), f"{v.major}.{v.minor}.{v.micro}"))
    checks.append(("git on PATH", bool(which("git")), which("git") or "missing"))
    checks.append(("git-lfs on PATH", bool(which("git-lfs")),
                   which("git-lfs") or "missing (LFS rules will not apply)"))
    if ws is None:
        checks.append(("workspace", False,
                       "not inside a workspace (run `rharness init` or pass --workspace)"))
        return checks
    checks.append(("workspace manifest", True, str(ws.manifest.path)))
    if ws.wants("claude"):
        ok = _session_hooks_present(ws.settings_path)
        checks.append(("session hooks registered", ok,
                       str(ws.settings_path) if ok else "missing; run `rharness adopt .` to re-register"))
    if "rtk" in ws.manifest.plugins:
        checks.append(("rtk binary on PATH", bool(which("rtk")),
                       which("rtk") or "missing; see plugins/rtk/setup.sh"))
        checks.append(("jq on PATH", bool(which("jq")), which("jq") or "missing; the hook needs jq"))
        if ws.wants("claude"):
            home_settings = Path(env.get("HOME", str(Path.home()))) / ".claude" / "settings.json"
            ok = _hook_present(ws.settings_path) or _hook_present(home_settings)
            checks.append(("rtk hook registered", ok,
                           str(ws.settings_path) if ok else "missing; run `rharness add rtk`"))
    return checks

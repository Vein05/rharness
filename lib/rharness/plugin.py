"""Plugins: directories with plugin.json, agents.md, files/, project-files/, claude/, setup.sh."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .manifest import Manifest, today
from .paths import BASE_DIR, PLUGINS_DIR, rharness_home
from .regions import remove_region, upsert_region
from .templates import copy_tree
from .workspace import PROJECT_MANIFEST_REL


class PluginNotFound(Exception):
    pass


def plugins_dir():
    """Built-in plugins (or the test override)."""
    return Path(os.environ.get("RHARNESS_PLUGINS_DIR") or PLUGINS_DIR)


def user_plugins_dir():
    """Plugins fetched from outside the release: ~/.rharness/plugins/<name>/."""
    return rharness_home() / "plugins"


def search_dirs():
    return [plugins_dir(), user_plugins_dir()]


NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
GITHUB_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(?:/(.+))?$")


def split_ref(spec: str):
    """'owner/repo/sub@v1' -> ('owner/repo/sub', 'v1'); a git@host: prefix is not a ref."""
    tail = spec.rsplit("/", 1)[-1]
    if "@" in tail and not spec.startswith("git@"):
        base, ref = spec.rsplit("@", 1)
        return base, ref
    if spec.startswith("git@") and spec.count("@") > 1:
        base, ref = spec.rsplit("@", 1)
        return base, ref
    return spec, None


def classify_source(spec: str):
    """Return (kind, payload): builtin | path | git | github. payload carries the ref for git kinds."""
    base, ref = split_ref(spec)
    if base.startswith(("./", "../", "/", "~")) or ("/" in base and (Path(base) / "plugin.json").exists()):
        return "path", str(Path(base).expanduser().resolve())
    if base.startswith(("http://", "https://", "git@", "ssh://", "file://")) or base.endswith(".git"):
        return "git", (base, ref)
    m = GITHUB_RE.match(base)
    if m and "/" in base:
        return "github", (m.group(1), m.group(2), m.group(3), ref)
    return "builtin", spec


def _copy_plugin_dir(src: Path, dest_root: Path) -> Path:
    if not (src / "plugin.json").exists():
        raise PluginNotFound(f"{src} has no plugin.json; a plugin directory must contain one")
    meta = json.loads((src / "plugin.json").read_text())
    name = meta.get("name", "")
    if not NAME_RE.match(name):
        raise PluginNotFound(f"plugin.json in {src} has an invalid name {name!r}")
    dest = dest_root / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))
    return dest


def fetch_plugin(spec: str, dest_root=None) -> Path:
    """Materialise an external plugin under the user plugins dir. Returns its directory."""
    dest_root = Path(dest_root or user_plugins_dir())
    dest_root.mkdir(parents=True, exist_ok=True)
    kind, payload = classify_source(spec)
    if kind == "path":
        return _copy_plugin_dir(Path(payload), dest_root)
    if kind == "builtin":
        raise PluginNotFound(f"no plugin named {spec}; use a built-in name, a local path, "
                             f"a git URL, or owner/repo[/subdir] on GitHub")
    if kind == "github":
        owner, repo, subdir, ref = payload
        base = os.environ.get("RHARNESS_GITHUB_BASE", "https://github.com/")
        url = f"{base}{owner}/{repo}"
        if base.startswith("https://"):
            url += ".git"
    else:
        (url, ref), subdir = payload, None
    tmp = Path(tempfile.mkdtemp(prefix="rharness-plugin-"))
    try:
        repo_dir = tmp / "repo"
        args = ["git", "clone", "-q", "--depth", "1"] + (["--branch", ref] if ref else []) + [url, str(repo_dir)]
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0 and ref:
            # not a branch or tag: full clone, then check out the commit
            r = subprocess.run(["git", "clone", "-q", url, str(repo_dir)], capture_output=True, text=True)
            if r.returncode == 0:
                r = subprocess.run(["git", "checkout", "-q", ref], cwd=str(repo_dir), capture_output=True, text=True)
        if r.returncode != 0:
            raise PluginNotFound(f"git clone of {url}" + (f"@{ref}" if ref else "") + f" failed: {r.stderr.strip()}")
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_dir),
                                capture_output=True, text=True).stdout.strip()
        src = repo_dir / subdir if subdir else repo_dir
        if not src.is_dir():
            raise PluginNotFound(f"{subdir} is not a directory in {url}")
        dest = _copy_plugin_dir(src, dest_root)
        (dest / ".rharness-source.json").write_text(json.dumps(
            {"spec": spec, "commit": commit, "ref": ref, "fetched": today()}, indent=2) + "\n")
        return dest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def fetched_commit(plugin_dir: Path):
    f = Path(plugin_dir) / ".rharness-source.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text()).get("commit")
    except json.JSONDecodeError:
        return None


def capability_summary(plugin, ws) -> str:
    """What installing this plugin would do on this machine."""
    n_files = sum(1 for x in plugin.files_dir.rglob("*") if x.is_file()) if plugin.files_dir.exists() else 0
    n_proj = sum(1 for x in plugin.project_files_dir.rglob("*") if x.is_file()) if plugin.project_files_dir.exists() else 0
    snippet = plugin.agents_snippet()
    lines = [f"Plugin {plugin.name} from {plugin.dir}"]
    commit = fetched_commit(plugin.dir)
    if commit:
        lines[0] += f" (commit {commit[:12]})"
    lines.append(f"  {n_files} file(s) into the workspace root; {n_proj} file(s) into every project")
    lines.append(f"  AGENTS.md section: {'yes, ' + str(len(snippet.splitlines())) + ' lines' if snippet else 'no'}"
                 " (the agent will follow it)")
    claude = ws.wants("claude") and "claude" in plugin.harness
    n_skills = sum(1 for x in plugin.skills_dir.rglob("SKILL.md")) if plugin.skills_dir.exists() else 0
    lines.append(f"  Claude Code skills: {n_skills if claude else 'none (not applied to this workspace)'}")
    if claude and plugin.hooks_path.exists():
        try:
            hooks = json.loads(plugin.hooks_path.read_text())
        except json.JSONDecodeError:
            hooks = {}
        for event, entries in hooks.items():
            for entry in entries:
                for h in entry.get("hooks", []):
                    lines.append(f"  hook {event}: runs `{h.get('command', '')}`")
    else:
        lines.append("  hooks: none")
    lines.append(f"  setup.sh: {'yes, a shell script will run on this machine' if plugin.setup_path.exists() else 'no'}")
    req = plugin.meta.get("requires", {})
    if req.get("env") or req.get("binaries"):
        lines.append(f"  requires: env {', '.join(req.get('env', [])) or '-'}; binaries {', '.join(req.get('binaries', [])) or '-'}")
    return "\n".join(lines)


def confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        return input(prompt + " [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


class Plugin:
    def __init__(self, name, directory):
        self.name = name
        self.dir = Path(directory)
        self.meta = json.loads((self.dir / "plugin.json").read_text())

    @classmethod
    def load(cls, name, base=None):
        dirs = [Path(base)] if base else search_dirs()
        for root in dirs:
            d = root / name
            if (d / "plugin.json").exists():
                return cls(name, d)
        raise PluginNotFound(f"no plugin named {name}; use a built-in name, a local path, "
                             f"a git URL, or owner/repo[/subdir] on GitHub")

    @property
    def origin(self):
        return "builtin" if self.dir.parent == plugins_dir() else "user"

    @property
    def harness(self):
        return list(self.meta.get("harness", []))

    @property
    def files_dir(self):
        return self.dir / "files"

    @property
    def project_files_dir(self):
        return self.dir / "project-files"

    @property
    def skills_dir(self):
        return self.dir / "claude" / "skills"

    @property
    def hooks_path(self):
        return self.dir / "claude" / "hooks.json"

    @property
    def setup_path(self):
        return self.dir / "setup.sh"

    def agents_snippet(self):
        p = self.dir / "agents.md"
        return p.read_text() if p.exists() else None


def list_available(base=None):
    return sorted(available_plugins(base))


def available_plugins(base=None):
    """name -> Plugin for every discoverable plugin; built-ins win on name clashes."""
    out = {}
    dirs = [Path(base)] if base else search_dirs()
    for root in dirs:
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if (d / "plugin.json").exists() and d.name not in out:
                out[d.name] = Plugin(d.name, d)
    return out


def template_path(source: str):
    """Resolve a manifest 'source' (e.g. plugins/<name>/files/x) to a file on disk."""
    from .paths import STORE_ROOT
    parts = source.split("/", 2)
    if len(parts) == 3 and parts[0] == "plugins":
        try:
            return Plugin.load(parts[1]).dir / parts[2]
        except PluginNotFound:
            return None
    return STORE_ROOT / source


# ----- hooks merging -----
def merge_hooks(settings: dict, hooks: dict):
    """Append hook entries into settings['hooks'][event]. Returns [(event, entry), ...] added."""
    added = []
    dest = settings.setdefault("hooks", {})
    for event, entries in hooks.items():
        lst = dest.setdefault(event, [])
        for entry in entries:
            if entry not in lst:
                lst.append(entry)
                added.append((event, entry))
    return added


def unmerge_hooks(settings: dict, added):
    dest = settings.get("hooks", {})
    for event, entry in added:
        lst = dest.get(event, [])
        if entry in lst:
            lst.remove(entry)


def _load_settings(path: Path):
    return json.loads(path.read_text()) if path.exists() else {}


def _save_settings(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


# ----- project files -----
def apply_project_files(ws, plugin: Plugin, project_dir: Path):
    if not plugin.project_files_dir.exists():
        return []
    pm_path = project_dir / PROJECT_MANIFEST_REL
    pm = Manifest.load(pm_path) if pm_path.exists() else None
    ctx = dict(pm.ctx) if pm else {"slug": project_dir.name, "title": project_dir.name}
    ctx.update({"workspace": str(ws.root), "date": today()})
    written, _ = copy_tree(plugin.project_files_dir, project_dir, ctx)
    if pm is not None:
        for rel in written:
            pm.record(rel, f"plugin:{plugin.name}", source=f"plugins/{plugin.name}/project-files/{rel}")
        pm.save()
    return written


def apply_all_project_files(ws, project_dir: Path):
    out = []
    for name in ws.manifest.plugins:
        try:
            out += apply_project_files(ws, Plugin.load(name), project_dir)
        except PluginNotFound:
            continue
    return out


# ----- base hooks (Claude Code session hooks shipped with the release) -----
def install_base_hooks(ws):
    """Merge base/claude/hooks.json into the workspace settings; idempotent."""
    hooks_file = BASE_DIR / "claude" / "hooks.json"
    if not ws.wants("claude") or not hooks_file.exists():
        return []
    settings = _load_settings(ws.settings_path)
    added = merge_hooks(settings, json.loads(hooks_file.read_text()))
    _save_settings(ws.settings_path, settings)
    existing = ws.manifest.hooks.get("base", [])
    for e, entry in added:
        if [e, entry] not in existing:
            existing.append([e, entry])
    ws.manifest.hooks["base"] = existing
    return added


# ----- install / uninstall -----
def install_plugin(ws, spec, dry_run=False, base=None, refresh=False, yes=False):
    kind, _ = classify_source(spec)
    if kind == "builtin":
        plugin = Plugin.load(spec, base)
        source = None
    else:
        source = spec
        plugin = None
        if not refresh:
            # reuse a previously fetched copy whose recorded source matches
            for cached_name, src in ws.manifest.plugin_sources.items():
                if src == spec and (user_plugins_dir() / cached_name / "plugin.json").exists():
                    plugin = Plugin.load(cached_name, user_plugins_dir())
                    break
        if plugin is None:
            fetched = fetch_plugin(spec)
            plugin = Plugin(fetched.name, fetched)
        if not dry_run:
            print(capability_summary(plugin, ws))
            if not yes and not confirm("Install this plugin?"):
                print("Not installed. Re-run with --yes to accept, or inspect the directory above first.")
                return 1
    name = plugin.name
    owner = f"plugin:{name}"
    ctx = {"workspace": str(ws.root), "date": today()}
    if dry_run:
        for src in (plugin.files_dir, plugin.skills_dir):
            if src.exists():
                for p in sorted(x for x in src.rglob("*") if x.is_file()):
                    print(f"would write {p.relative_to(plugin.dir)}")
        print(f"would update AGENTS.md region plugin:{name}")
        return 0
    written = []
    if plugin.files_dir.exists():
        w, _ = copy_tree(plugin.files_dir, ws.root, ctx)
        written += w
        for rel in w:
            ws.manifest.record(rel, owner, source=f"plugins/{name}/files/{rel}")
    snippet = plugin.agents_snippet()
    if snippet is not None:
        text = ws.agents_path.read_text() if ws.agents_path.exists() else ""
        ws.agents_path.write_text(upsert_region(text, f"plugin:{name}", snippet))
        prev = ws.manifest.entry("AGENTS.md") or {}
        ws.manifest.record("AGENTS.md", prev.get("owner", "base"),
                           source="base/workspace/AGENTS.md", region=True)
    if ws.wants("claude") and "claude" in plugin.harness:
        if plugin.skills_dir.exists():
            dest = ws.root / ".claude" / "skills"
            w, _ = copy_tree(plugin.skills_dir, dest, ctx, overwrite=True)
            for rel in w:
                rel_ws = f".claude/skills/{rel}"
                ws.manifest.record(rel_ws, owner, source=f"plugins/{name}/claude/skills/{rel}")
                written.append(rel_ws)
        if plugin.hooks_path.exists():
            settings = _load_settings(ws.settings_path)
            added = merge_hooks(settings, json.loads(plugin.hooks_path.read_text()))
            _save_settings(ws.settings_path, settings)
            existing = ws.manifest.hooks.get(name, [])
            for e, entry in added:
                if [e, entry] not in existing:
                    existing.append([e, entry])
            ws.manifest.hooks[name] = existing
        if not ws.claude_md_path.exists():
            ws.claude_md_path.write_text("@AGENTS.md\n")
            ws.manifest.record("CLAUDE.md", "base", source="base/workspace/CLAUDE.md", region=True)
    for project in ws.projects():
        apply_project_files(ws, plugin, project)
    ws.manifest.add_plugin(name)
    if source:
        ws.manifest.plugin_sources[name] = source
    ws.manifest.save()
    if plugin.setup_path.exists() and not os.environ.get("RHARNESS_SKIP_SETUP"):
        env = dict(os.environ, RHARNESS_WORKSPACE=str(ws.root))
        r = subprocess.run(["sh", str(plugin.setup_path)], cwd=str(ws.root), env=env)
        if r.returncode != 0:
            print(f"rharness: setup for {name} exited {r.returncode}; files are installed, "
                  f"rerun `rharness add {name}` after fixing")
    print(f"Installed plugin {name}")
    for rel in written:
        print(f"  wrote {rel}")
    req = plugin.meta.get("requires", {})
    missing_env = [v for v in req.get("env", []) if not os.environ.get(v)]
    missing_bin = [b for b in req.get("binaries", []) if shutil.which(b) is None]
    if missing_env:
        print(f"  needs environment variable(s) not set in this shell: {', '.join(missing_env)}")
    if missing_bin:
        print(f"  needs binary(ies) not on PATH: {', '.join(missing_bin)}")
    return 0


def uninstall_plugin(ws, name, dry_run=False):
    owner = f"plugin:{name}"
    files = ws.manifest.files_owned_by(owner)
    if dry_run:
        for rel in files:
            print(f"would remove {rel}")
        return 0
    for rel in files:
        p = ws.root / rel
        if not p.exists():
            ws.manifest.forget(rel)
            continue
        if ws.manifest.is_unmodified(rel):
            p.unlink()
            ws.manifest.forget(rel)
            print(f"  removed {rel}")
            parent = p.parent
            while parent != ws.root and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        else:
            ws.manifest.forget(rel)
            print(f"  kept {rel} (modified; now untracked)")
    if ws.agents_path.exists():
        ws.agents_path.write_text(remove_region(ws.agents_path.read_text(), f"plugin:{name}"))
        prev = ws.manifest.entry("AGENTS.md") or {}
        ws.manifest.record("AGENTS.md", prev.get("owner", "base"),
                           source="base/workspace/AGENTS.md", region=True)
    added = ws.manifest.hooks.pop(name, [])
    if added and ws.settings_path.exists():
        settings = _load_settings(ws.settings_path)
        unmerge_hooks(settings, [tuple(a) for a in added])
        _save_settings(ws.settings_path, settings)
    ws.manifest.remove_plugin(name)
    ws.manifest.plugin_sources.pop(name, None)
    ws.manifest.save()
    print(f"Removed plugin {name}")
    return 0


# ----- authoring -----
def scaffold_plugin(dest: Path, name: str) -> list:
    """Write a starter plugin at dest/<name>. Returns the relative paths written."""
    if not NAME_RE.match(name):
        raise ValueError("plugin name must be lowercase letters, digits, and hyphens")
    root = dest / name
    if root.exists():
        raise FileExistsError(str(root))
    files = {
        "plugin.json": json.dumps({
            "name": name,
            "description": "One line: what this plugin adds to a workspace.",
            "version": "0.1.0",
            "harness": ["claude", "codex"],
            "requires": {"binaries": [], "python": ">=3.9"},
        }, indent=2) + "\n",
        "agents.md": (
            f"## {name}\n\n"
            "<!-- This section is inserted into the workspace AGENTS.md between\n"
            f"     rharness:begin plugin:{name} / rharness:end markers. Write the rules\n"
            "     an agent must follow when this plugin is installed. Keep it short. -->\n\n"
            f"- Files for this plugin live in `{name}/`.\n"
        ),
        f"files/{name}/README.md": (
            f"# {name}\n\n"
            "Files under `files/` are copied into the workspace root with paths preserved.\n"
            "Text files may use {{slug}}, {{title}}, {{date}}, and {{workspace}}.\n"
        ),
        "project-files/.gitkeep": "",
        f"claude/skills/{name}/SKILL.md": (
            "---\n"
            f"name: {name}\n"
            f"description: When to use the {name} plugin. Claude Code reads this line to decide.\n"
            "---\n\n"
            f"# {name}\n\n"
            "Step-by-step instructions for the agent. Delete this directory if the plugin\n"
            "has no Claude Code skill.\n"
        ),
        "README.md": (
            f"# {name} (rharness plugin)\n\n"
            "## What it adds\n\n<!-- One paragraph. -->\n\n"
            "## Install\n\n"
            "From a local checkout:\n\n"
            f"    rharness add /path/to/{name}\n\n"
            "From GitHub once pushed (replace owner/repo; add /subdir if the plugin is\n"
            "not at the repository root):\n\n"
            f"    rharness add owner/{name}\n\n"
            "Re-fetch after you publish a change:\n\n"
            f"    rharness add owner/{name} --refresh\n\n"
            "## Layout\n\n"
            "    plugin.json        name, description, version, harness, requires\n"
            "    agents.md          section inserted into the workspace AGENTS.md\n"
            "    files/             copied into the workspace root\n"
            "    project-files/     copied into every project, existing and future\n"
            "    claude/skills/     Claude Code skills (Claude only)\n"
            "    claude/hooks.json  hook entries merged into .claude/settings.json (Claude only)\n"
            "    setup.sh           optional; runs after install, may install binaries\n"
        ),
    }
    written = []
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        written.append(rel)
    return written

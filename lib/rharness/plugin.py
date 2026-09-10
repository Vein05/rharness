"""Plugins: directories with plugin.json, agents.md, files/, project-files/, claude/, setup.sh."""
import json
import os
import subprocess
from pathlib import Path

from .manifest import Manifest, today
from .paths import PLUGINS_DIR
from .regions import remove_region, upsert_region
from .templates import copy_tree
from .workspace import PROJECT_MANIFEST_REL


class PluginNotFound(Exception):
    pass


def plugins_dir():
    return Path(os.environ.get("RHARNESS_PLUGINS_DIR") or PLUGINS_DIR)


class Plugin:
    def __init__(self, name, directory):
        self.name = name
        self.dir = Path(directory)
        self.meta = json.loads((self.dir / "plugin.json").read_text())

    @classmethod
    def load(cls, name, base=None):
        d = Path(base or plugins_dir()) / name
        if not (d / "plugin.json").exists():
            raise PluginNotFound(f"no plugin named {name} in {d.parent}")
        return cls(name, d)

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
    base = Path(base or plugins_dir())
    if not base.exists():
        return []
    return sorted(d.name for d in base.iterdir() if (d / "plugin.json").exists())


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


# ----- install / uninstall -----
def install_plugin(ws, name, dry_run=False, base=None):
    plugin = Plugin.load(name, base)
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
    ws.manifest.save()
    print(f"Removed plugin {name}")
    return 0

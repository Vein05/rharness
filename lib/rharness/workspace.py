"""Workspace discovery and project detection."""
from pathlib import Path

from .manifest import Manifest

MANIFEST_REL = Path(".rharness") / "manifest.json"
PROJECT_MANIFEST_REL = Path(".rharness") / "project.json"


class NotAWorkspace(Exception):
    pass


def find_root(start: Path):
    p = Path(start).resolve()
    for cand in [p, *p.parents]:
        if (cand / MANIFEST_REL).exists():
            return cand
    return None


def detect_projects(root: Path):
    out = []
    for d in sorted(Path(root).iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        if (d / "CHARTER.md").exists() or (d / "AGENTS.md").exists() or (d / ".git").exists():
            out.append(d)
    return out


class Workspace:
    def __init__(self, root: Path, manifest: Manifest):
        self.root = Path(root)
        self.manifest = manifest

    @classmethod
    def open(cls, start=None, override=None):
        root = Path(override).resolve() if override else find_root(start or Path.cwd())
        if root is None or not (root / MANIFEST_REL).exists():
            raise NotAWorkspace("not inside an rharness workspace (no .rharness/manifest.json); "
                                "run `rharness init` or pass --workspace")
        return cls(root, Manifest.load(root / MANIFEST_REL))

    @property
    def agents_path(self):
        return self.root / "AGENTS.md"

    @property
    def claude_md_path(self):
        return self.root / "CLAUDE.md"

    @property
    def settings_path(self):
        return self.root / ".claude" / "settings.json"

    def wants(self, harness: str) -> bool:
        return harness in self.manifest.harness

    def projects(self):
        return detect_projects(self.root)

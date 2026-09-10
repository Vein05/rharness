"""The .rharness/manifest.json (workspace) and .rharness/project.json (project) files."""
import datetime as _dt
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def today() -> str:
    return _dt.date.today().isoformat()


class Manifest:
    def __init__(self, path: Path, data: dict):
        self.path = Path(path)
        self.data = data

    # ----- construction -----
    @classmethod
    def new(cls, path, version, harness=("claude", "codex"), ctx=None):
        data = {
            "rharness_version": version,
            "created": today(),
            "harness": list(harness),
            "plugins": [],
            "projects": [],
            "files": {},
            "hooks": {},
            "plugin_sources": {},
            "ctx": dict(ctx or {}),
        }
        return cls(path, data)

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        return cls(path, json.loads(path.read_text()))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n")

    # ----- properties -----
    @property
    def root(self) -> Path:
        return self.path.parent.parent

    @property
    def version(self) -> str:
        return self.data["rharness_version"]

    @version.setter
    def version(self, v):
        self.data["rharness_version"] = v

    @property
    def harness(self):
        return self.data["harness"]

    @property
    def plugins(self):
        return self.data["plugins"]

    @property
    def projects(self):
        return self.data.setdefault("projects", [])

    @property
    def hooks(self):
        return self.data.setdefault("hooks", {})

    @property
    def plugin_sources(self):
        return self.data.setdefault("plugin_sources", {})

    @property
    def ctx(self):
        return self.data.setdefault("ctx", {})

    @property
    def files(self):
        return self.data["files"]

    # ----- files -----
    def record(self, rel, owner, source=None, region=False):
        entry = {"sha256": sha256_file(self.root / rel), "owner": owner}
        if source:
            entry["source"] = source
        if region:
            entry["region"] = True
        self.files[rel] = entry

    def entry(self, rel):
        return self.files.get(rel)

    def is_unmodified(self, rel) -> bool:
        e = self.entry(rel)
        p = self.root / rel
        return bool(e) and p.exists() and sha256_file(p) == e["sha256"]

    def forget(self, rel):
        self.files.pop(rel, None)

    def files_owned_by(self, owner):
        return sorted(k for k, v in self.files.items() if v.get("owner") == owner)

    # ----- plugins -----
    def add_plugin(self, name):
        if name not in self.plugins:
            self.plugins.append(name)

    def remove_plugin(self, name):
        if name in self.plugins:
            self.plugins.remove(name)

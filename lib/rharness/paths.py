import os
from pathlib import Path

STORE_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = STORE_ROOT / "base"
PLUGINS_DIR = STORE_ROOT / "plugins"


def rharness_home() -> Path:
    return Path(os.environ.get("RHARNESS_HOME") or Path.home() / ".rharness")

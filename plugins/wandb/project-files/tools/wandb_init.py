"""Start a W&B run with the fields the workspace rules require.

Usage:
    from tools.wandb_init import start
    run = start(project="{{slug}}", group="pilot", name="seed-0", config={"seed": 0})
"""
import os
import subprocess


def git_commit() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def start(project: str, group: str, name: str, config: dict):
    import wandb  # not a dependency of rharness; pip install wandb
    cfg = dict(config, git_commit=git_commit())
    return wandb.init(project=project, group=group, name=name, config=cfg,
                      mode=os.environ.get("WANDB_MODE", "online"))

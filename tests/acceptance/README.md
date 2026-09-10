# Acceptance run against a real workspace

Not collected by pytest. Run by hand before a release, against a copy of a
real research workspace, never the original.

## 1. Copy the workspace (small files only, shared git objects)

    rm -rf /tmp/rh-accept && mkdir -p /tmp/rh-accept && cd ~/research
    rsync -a --max-size=512k --exclude '.git' --exclude '.venv' --exclude 'wandb' \
      --exclude 'traces' --exclude 'data' --exclude 'node_modules' --exclude '*.zip' \
      --exclude '.env' --exclude 'runs' --exclude '__pycache__' --exclude 'build' \
      ./ /tmp/rh-accept/research/
    for d in */; do d=${d%/}; [ -d "$d/.git" ] || continue
      git clone -q --shared --no-checkout "$d" "/tmp/rh-accept/.g-$d"
      mv "/tmp/rh-accept/.g-$d/.git" "/tmp/rh-accept/research/$d/.git"; rm -rf "/tmp/rh-accept/.g-$d"
      (cd "/tmp/rh-accept/research/$d" && git config core.bare false && git reset -q)
    done

## 2. Adopt and lint

    RHARNESS_SKIP_SETUP=1 rharness adopt /tmp/rh-accept/research
    rharness lint /tmp/rh-accept/research

## 3. Expected

- `adopt` exits 0 and prints `kept` for every file that already existed.
- `diff -rq --exclude=.git --exclude=.rharness ~/research/<p> /tmp/rh-accept/research/<p>`
  shows no `Files ... differ` lines for files that were copied.
- `lint` exits 1 and reports: `no commits` for repos never committed,
  `uncommitted changes` for dirty trees, `LFS rules missing` where
  `.gitattributes` lacks them, `writing.md` findings for hand-edited guides,
  root clutter (`.zip`, `.pdf`, `tmp*`), and table rows without a project.

Record of the 2026-09-09 run on the source workspace (18 projects): adopt
exit 0, lint 30 errors and 42 warnings, all in the expected categories.

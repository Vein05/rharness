# changelog/ — append-only per-day logs

One file per day: `YYYY-MM-DD.md`. Each entry is a timestamped checkpoint.
Never rewrite past entries; append corrections that cite the entry they
correct.

    # Changelog — YYYY-MM-DD
    ## YYYY-MM-DD HH:MM TZ — checkpoint N
    - What changed.
    - What was learned.
    - What is not yet done.

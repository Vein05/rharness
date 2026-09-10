# Provenance ledger

Frozen artifacts and their hashes. Every number in the paper points at a row
here. Add rows with `rharness hash <path> [--note "..."]`; `rharness lint`
fails when a recorded file changes or disappears. sha16 is the first 16 hex
characters of the file's SHA-256.

| path | sha16 | bytes | recorded | code commit | note |
|---|---|---:|---|---|---|

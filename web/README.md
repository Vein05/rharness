# web/ — the rharness site

A single static page, no build step: `index.html`, `logo.svg`, `favicon.svg`.
Nothing is fetched from anywhere.

`logo.svg` is the cover's compass mark in monochrome, generated from the same
geometry as `assets/cover/build.py`.

## Deploy

`.github/workflows/pages.yml` publishes `web/` to GitHub Pages on every push
to `main` that touches `web/`. Enable it once under Settings, Pages, Source:
GitHub Actions. For a custom domain, add it there and put the bare domain
name in `web/CNAME` on one line. Pages on a private repository needs a paid
GitHub plan; on a public one it is free.

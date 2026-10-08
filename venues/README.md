# Venue packages

A venue package attaches one submission target to one paper project:
`rharness venue add iclr 2027`. Packages live here, not in the release
tarball (`venues/ export-ignore` in the root `.gitattributes`), because they
change through a cycle. `rharness` fetches `venues/<name>/` on demand and
refreshes it when the cache is older than 24 hours.

## Layout

```
venues/
  INDEX.json         generated: python scripts/venues-index.py  (CI checks it is current)
  schema.json        the shape of venue.json; python scripts/venues-validate.py enforces it
  <name>/
    plugin.json      {"scope": "project", "kind": "venue", ...}
    venue.json       metadata: deadlines, page limit, anonymity, template pointer, sources
    agents.md        section inserted into the project AGENTS.md
    checks.py        optional; only for rules the generic set cannot express
    sources.lock.json  page hashes for the staleness watch
    project-files/   copied into the project; usually research/venue-<name>.md (archetype K)
```

## Naming

`<venue><cycle>`, lowercase: `iclr2027`, `aaai2027`, `acl2027`. Never an
unversioned name; deadlines, limits, and style files differ per cycle.

## Sources policy

Every value in `venue.json` comes from a page listed in `sources`, with the
date it was read. `scripts/venues-watch.py` hashes each source page weekly
(`.github/workflows/venues-watch.yml`) and opens an issue when one changes.
It parses nothing; a maintainer reads the page and updates `venue.json` and
`revision`.

## Template policy

Point at the venue's own distribution: a GitHub repository at a pinned
commit (`template.repo`, `template.ref`, `template.files`) or a zip with a
sha256 (`template.url`, `template.sha256`, `template.extract`). Vendor a copy
under `project-files/paper/` only when the upstream has no stable URL and
its license permits redistribution; record the license check here.

| venue | template source | vendored | license note |
|---|---|---|---|
| iclr2027 | github.com/ICLR/Master-Template @ pinned commit | no | official repository |

## Adding a venue

1. `mkdir venues/<name>`; write `plugin.json`, `venue.json`, `agents.md`.
2. `python scripts/venues-validate.py`
3. `python scripts/venues-watch.py --update` to write `sources.lock.json`.
4. `python scripts/venues-index.py` to regenerate `INDEX.json`.
5. Test locally: `rharness venue add <owner>/<fork>/venues/<name>` in a scratch workspace.

## Known gaps

Checked 2026-09-10 for `iclr2027`. Nothing in `venue.json` is carried over
from 2026; each value below was read on that date from the page named.

- Template: `github.com/ICLR/Master-Template` has a 2027 directory, so
  `template.files` are the real `iclr2027/iclr2027_conference.sty` and
  `.bst`, pinned at the default branch head
  `46ed6f4c6cef5b175dde23639e77d44c3463b230`. That head is the whole
  repository, not a 2027-only tag; the repository publishes no tags, so a
  later commit touching another year still changes the pin.
- Call for papers: the page is up. It gives the two deadlines used here
  (abstract Sep 18 2026, paper Sep 25 2026, both 11:59 PM AoE = UTC-12) and
  states double-blind review. It does not state a page limit.
- Page limit: `page_limit.main` is 9, from the author guidelines
  (`Conferences/2027/AuthorGuidelines`: "the main text should be 9 pages or
  fewer"), which is why that page is a source. The same 9 appears in the
  2027 template's `iclr2027_conference.tex`. The limit rises to 10 pages for
  rebuttal and camera ready; `venue.json` records the submission limit only,
  so a camera-ready check would read high by one page.
- Reviewer guide: the URL is `Conferences/2027/ReviewerGuidelines`, the link
  the call for papers itself uses. `Conferences/2027/ReviewerGuide` returns
  404.
- Review form scales in `project-files/research/venue-iclr2027.md` come from
  the review-panel plugin's `prompts/iclr-form.md`, which is written against
  the ICLR 2026 form. They were not re-checked against a published 2027
  reviewer form; the reviewer guide page above is the place to confirm them
  once ICLR publishes the 2027 form.

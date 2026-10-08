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
| naacl2027 | github.com/acl-org/acl-style-files @ pinned commit | no | official ACL repository, linked from the ARR call |
| acl2027 | github.com/acl-org/acl-style-files @ pinned commit | no | official ACL repository, linked from the ARR call |

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
- Author block: `author_block.hidden_unless` is `\\iclrfinalcopy`, from
  `iclr2027_conference.sty`, which prints "Anonymous authors" unless
  `\iclrfinalcopy` is set (checked 2026-10-07). Without it, lint flagged the
  `\author{}` of every correctly anonymized submission.

Checked 2026-10-07 for `naacl2027` and `acl2027`. Each value was read on that
date from the page named, at least twice: the conference call, the ARR call
(`aclrollingreview.org/cfp`, also read from its source in
`github.com/acl-org/aclrollingreview`), and the ARR dates table.

- Reviewing: both use ACL Rolling Review. NAACL 2027 takes the October 2026
  cycle (shared with COLING 2027; authors pick one at commitment). ACL 2027
  takes the January 2027 cycle.
- Deadlines, all 11:59 PM AoE (UTC-12): NAACL ARR submission 2026-10-12 and
  commitment 2026-12-23 (NAACL call, ACL portal copy of the call, and the ARR
  venues table agree). ACL ARR submission 2027-01-04 (ACL call and the ACL
  2027 home page); the commitment date is "TBA" there and blank in the ARR
  table, so `acl2027` has one deadline until it is announced.
- Disagreements between official pages, recorded in the NAACL playbook and
  `agents.md`, not in `venue.json`: reviewer registration is 2026-10-12 in the
  NAACL call and 2026-10-14 in the ARR table; meta-reviews are 2026-12-18 in
  the NAACL call and 2026-12-17 in the ARR table. Camera-ready is 2027-03-03 on
  2027.naacl.org and "to be determined" on the ACL portal copy.
- Page limit: `page_limit.main` is 8, the long-paper limit ("up to eight (8)
  pages of content"). Short papers have 4; `venue.json` holds one limit, so a
  short paper is not checked against 4. Limitations, ethical considerations,
  references, and appendices do not count, which is `page_limit.excludes`.
  Camera ready adds one page; not recorded.
- Required sections: abstract, introduction, and "Limitations" ("Papers
  without a limitations section will be desk rejected").
- Template: `acl.sty` and `acl_natbib.bst` from `github.com/acl-org/acl-style-files`,
  pinned at `d5adc823ff0f80f98c80405ca0ab66c68e684409` (default branch head,
  2026-06-29). The ARR call links this repository and forbids modified styles.
  `acl.sty` defaults to `final`; `[review]` anonymizes the author block and
  adds line numbers, which is `author_block.hidden_if`. `checks.py` warns when
  `acl` is loaded without `[review]`.
- Review form scales in the playbooks come from `aclrollingreview.org/reviewform`
  and its source `reviewform.md`; Soundness, Excitement, and Overall
  Assessment allow half steps.

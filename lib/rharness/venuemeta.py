"""venue.json: names, schema validation, deadlines."""
import datetime as _dt
import re

from .plugin import split_ref

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*\d{4}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def normalize_name(tokens) -> str:
    joined = "".join(str(t) for t in tokens).lower()
    return re.sub(r"[^a-z0-9-]", "", joined)


def is_source_spec(s: str) -> bool:
    return "/" in s


def split_pin(spec: str):
    return split_ref(spec)


def validate(v) -> list:
    errs = []
    if not isinstance(v, dict):
        return ["venue.json must be a JSON object"]
    for key in ("venue", "cycle", "name", "revision", "deadlines", "primary", "anonymous"):
        if key not in v:
            errs.append(f"{key} is required")
    name = v.get("name", "")
    if isinstance(name, str) and v.get("venue") and v.get("cycle") and name != f"{v['venue']}{v['cycle']}":
        errs.append(f"name must be venue+cycle ({v['venue']}{v['cycle']}), got {name!r}")
    if isinstance(name, str) and name and not NAME_RE.match(name):
        errs.append(f"name {name!r} must be lowercase letters/digits ending in a four-digit cycle")
    if "revision" in v and not (isinstance(v["revision"], str) and DATE_RE.match(v["revision"])):
        errs.append("revision must be YYYY-MM-DD")
    dl = v.get("deadlines")
    if dl is not None:
        if not isinstance(dl, dict) or not dl:
            errs.append("deadlines must be a non-empty object")
        else:
            for k, val in dl.items():
                if not isinstance(val, str) or not TS_RE.match(val):
                    errs.append(f"deadlines.{k} must be ISO-8601 with seconds and offset, e.g. 2026-09-25T23:59:00-12:00"
                                + ("" if isinstance(val, str) and "T" not in val else " (seconds required)"))
    if "primary" in v and (not isinstance(dl, dict) or v["primary"] not in dl):
        errs.append("primary must name one key of deadlines")
    if "anonymous" in v and not isinstance(v["anonymous"], bool):
        errs.append("anonymous must be true or false")
    pl = v.get("page_limit")
    if pl is not None:
        if not isinstance(pl, dict) or not isinstance(pl.get("main"), int) or pl["main"] <= 0:
            errs.append("page_limit.main must be a positive integer")
        if "excludes" in pl and not (isinstance(pl["excludes"], list) and all(isinstance(x, str) for x in pl["excludes"])):
            errs.append("page_limit.excludes must be a list of headings")
    ab = v.get("author_block")
    if ab is not None:
        keys = set(ab) if isinstance(ab, dict) else set()
        if not isinstance(ab, dict) or len(keys & {"hidden_if", "hidden_unless"}) != 1 or keys - {"hidden_if", "hidden_unless"}:
            errs.append("author_block needs exactly one of hidden_if or hidden_unless")
        else:
            pat = ab.get("hidden_if", ab.get("hidden_unless"))
            try:
                re.compile(pat)
            except (re.error, TypeError) as e:
                errs.append(f"author_block pattern does not compile: {e}")
    tpl = v.get("template")
    if tpl is not None:
        if not isinstance(tpl, dict):
            errs.append("template must be an object")
        elif "repo" in tpl:
            if not tpl.get("ref") or not isinstance(tpl.get("files"), list) or not tpl["files"]:
                errs.append("template with repo needs ref and a non-empty files list")
        elif "url" in tpl:
            if not (isinstance(tpl.get("sha256"), str) and SHA_RE.match(tpl["sha256"])):
                errs.append("template with url needs a 64-hex sha256")
            if not isinstance(tpl.get("extract"), list) or not tpl["extract"]:
                errs.append("template with url needs a non-empty extract list")
        else:
            errs.append("template needs repo+ref+files or url+sha256+extract")
    rs = v.get("required_sections", [])
    if not (isinstance(rs, list) and all(isinstance(x, str) for x in rs)):
        errs.append("required_sections must be a list of strings")
    for i, s in enumerate(v.get("sources", []) or []):
        if not isinstance(s, dict) or not s.get("kind") or not s.get("url"):
            errs.append(f"sources[{i}] needs kind and url")
        elif not (isinstance(s.get("retrieved"), str) and DATE_RE.match(s["retrieved"])):
            errs.append(f"sources[{i}].retrieved must be YYYY-MM-DD")
    return errs


def parse_deadline(iso: str) -> _dt.datetime:
    d = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.astimezone()
    return d


def days_until(iso: str, now=None) -> int:
    d = parse_deadline(iso)
    now = now or _dt.datetime.now(tz=d.tzinfo)
    now = now.astimezone(d.tzinfo)
    return (d.date() - now.date()).days


def primary_deadline(venue: dict):
    key = venue["primary"]
    return key, venue["deadlines"][key]

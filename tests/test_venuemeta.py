import datetime as dt
import pytest

from rharness import venuemeta as vm

GOOD = {
    "venue": "iclr", "cycle": "2027", "name": "iclr2027", "revision": "2026-09-10",
    "deadlines": {"abstract": "2026-09-18T23:59:00-12:00", "full": "2026-09-25T23:59:00-12:00"},
    "primary": "full",
    "page_limit": {"main": 9, "excludes": ["references", "appendix"]},
    "anonymous": True,
    "template": {"repo": "ICLR/Master-Template", "ref": "abc123", "files": ["iclr2027_conference.sty"]},
    "required_sections": ["abstract", "introduction"],
    "sources": [{"kind": "cfp", "url": "https://iclr.cc/x", "retrieved": "2026-09-10"}],
}


def test_normalize_name():
    assert vm.normalize_name(["iclr", "2027"]) == "iclr2027"
    assert vm.normalize_name(["ICLR2027"]) == "iclr2027"
    assert vm.normalize_name(["aaai", "2027"]) == "aaai2027"
    assert vm.is_source_spec("lab/repo/venues/iclr2027@v1") and not vm.is_source_spec("iclr2027")


def test_validate_good():
    assert vm.validate(GOOD) == []


@pytest.mark.parametrize("mutate,needle", [
    (lambda v: v.pop("primary"), "primary"),
    (lambda v: v.update(primary="nope"), "primary"),
    (lambda v: v["deadlines"].update(full="2026-09-25T23:59-12:00"), "seconds"),
    (lambda v: v["deadlines"].update(full="2026-09-25"), "deadlines.full"),
    (lambda v: v.update(name="iclr27"), "name"),
    (lambda v: v.update(revision="last week"), "revision"),
    (lambda v: v.update(anonymous="yes"), "anonymous"),
    (lambda v: v["page_limit"].update(main=0), "page_limit.main"),
    (lambda v: v.update(template={"repo": "x/y", "files": []}), "template"),
    (lambda v: v.update(template={"url": "https://a/b.zip", "extract": ["a.sty"]}), "sha256"),
    (lambda v: v.update(sources=[{"kind": "cfp", "url": "https://x"}]), "retrieved"),
    (lambda v: v.update(deadlines={}), "deadlines"),
])
def test_validate_rejects(mutate, needle):
    import copy
    v = copy.deepcopy(GOOD)
    mutate(v)
    errs = vm.validate(v)
    assert errs and any(needle in e for e in errs), errs


def test_deadline_math():
    now = dt.datetime(2026, 9, 10, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=-12)))
    assert vm.days_until("2026-09-25T23:59:00-12:00", now=now) == 15
    assert vm.days_until("2026-09-10T23:59:00-12:00", now=now) == 0
    assert vm.days_until("2026-09-01T23:59:00-12:00", now=now) == -9
    key, iso = vm.primary_deadline(GOOD)
    assert key == "full" and iso.startswith("2026-09-25")
    assert vm.parse_deadline("2026-09-25T23:59:00").tzinfo is not None

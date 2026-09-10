from rharness.regions import (begin_marker, end_marker, get_region,
                              upsert_region, remove_region, list_regions)


def test_markers():
    assert begin_marker("base") == "<!-- rharness:begin base -->"
    assert end_marker("plugin:rtk") == "<!-- rharness:end plugin:rtk -->"


def test_upsert_appends_when_absent():
    out = upsert_region("# Title\n\nuser text\n", "base", "rule 1\n")
    assert out == ("# Title\n\nuser text\n\n"
                   "<!-- rharness:begin base -->\nrule 1\n<!-- rharness:end base -->\n")
    assert get_region(out, "base") == "rule 1\n"


def test_upsert_replaces_in_place_keeping_surroundings():
    text = ("before\n<!-- rharness:begin base -->\nold\n<!-- rharness:end base -->\nafter\n")
    out = upsert_region(text, "base", "new\n")
    assert out == "before\n<!-- rharness:begin base -->\nnew\n<!-- rharness:end base -->\nafter\n"


def test_upsert_normalises_body_newline():
    out = upsert_region("", "base", "no newline")
    assert get_region(out, "base") == "no newline\n"


def test_remove_region_drops_markers_and_body():
    text = "a\n\n<!-- rharness:begin plugin:rtk -->\nbody\n<!-- rharness:end plugin:rtk -->\n\nb\n"
    assert remove_region(text, "plugin:rtk") == "a\n\nb\n"
    assert remove_region("a\n", "plugin:rtk") == "a\n"


def test_list_regions_in_order():
    text = upsert_region(upsert_region("", "base", "x"), "plugin:rtk", "y")
    assert list_regions(text) == ["base", "plugin:rtk"]
    assert get_region(text, "missing") is None

import zlib
from pathlib import Path

from rharness import pdfutil


def _plain_pdf(n_pages: int) -> bytes:
    """Uncompressed PDF with n page objects. Not xref-correct; enough for the scanner."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [" + " ".join(f"{i} 0 R" for i in range(3, 3 + n_pages)) + f"] /Count {n_pages} >>"]
    objs += ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>" for _ in range(n_pages)]
    body = "%PDF-1.4\n" + "".join(f"{i+1} 0 obj\n{o}\nendobj\n" for i, o in enumerate(objs)) + "trailer\n<< /Root 1 0 R >>\n%%EOF\n"
    return body.encode()


def _objstm_pdf(n_pages: int) -> bytes:
    """Page objects hidden inside a FlateDecode object stream, as pdfTeX writes them."""
    inner_objs = [(3 + i, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>") for i in range(n_pages)]
    inner_objs.append((2, "<< /Type /Pages /Kids [" + " ".join(f"{n} 0 R" for n, _ in inner_objs) + f"] /Count {n_pages} >>"))
    offsets, data, pos = [], "", 0
    for num, text in inner_objs:
        offsets.append(f"{num} {pos}")
        data += text + "\n"
        pos = len(data)
    header = " ".join(offsets) + "\n"
    payload = zlib.compress((header + data).encode())
    stm = (f"100 0 obj\n<< /Type /ObjStm /N {len(inner_objs)} /First {len(header)} /Length {len(payload)} "
           f"/Filter /FlateDecode >>\nstream\n").encode() + payload + b"\nendstream\nendobj\n"
    return b"%PDF-1.5\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n" + stm + b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"


def test_page_count_plain(tmp_path):
    f = tmp_path / "a.pdf"; f.write_bytes(_plain_pdf(4))
    assert pdfutil.page_count(f, use_tools=False) == 4


def test_page_count_object_streams(tmp_path):
    f = tmp_path / "b.pdf"; f.write_bytes(_objstm_pdf(7))
    assert pdfutil.page_count(f, use_tools=False) == 7


def test_page_count_not_a_pdf_is_none(tmp_path):
    f = tmp_path / "c.pdf"; f.write_bytes(b"hello")
    assert pdfutil.page_count(f, use_tools=False) is None


def test_page_count_uses_pdfinfo_when_present(tmp_path, monkeypatch):
    b = tmp_path / "bin"; b.mkdir()
    fake = b / "pdfinfo"; fake.write_text("#!/bin/sh\necho 'Title: x'\necho 'Pages:          12'\n"); fake.chmod(0o755)
    f = tmp_path / "d.pdf"; f.write_bytes(_plain_pdf(1))
    assert pdfutil.page_count(f, env={"PATH": str(b)}) == 12


def test_pdf_text_and_heading_page_with_fake_pdftotext(tmp_path):
    b = tmp_path / "bin"; b.mkdir()
    fake = b / "pdftotext"
    fake.write_text("#!/bin/sh\n# args: ... file -\nprintf 'Intro text\\n\\fMore body\\n7 References\\n[1] a\\n\\fAppendix\\n'\n")
    fake.chmod(0o755)
    f = tmp_path / "e.pdf"; f.write_bytes(_plain_pdf(3))
    env = {"PATH": str(b)}
    text = pdfutil.pdf_text(f, env=env)
    assert text is not None and text.count("\f") == 2
    assert pdfutil.heading_page(f, ["references", "appendix"], env=env) == 2
    assert pdfutil.heading_page(f, ["appendix"], env=env) == 3
    assert pdfutil.heading_page(f, ["bibliography"], env=env) is None


def test_pdf_text_none_without_tool(tmp_path):
    f = tmp_path / "f.pdf"; f.write_bytes(_plain_pdf(1))
    assert pdfutil.pdf_text(f, env={"PATH": str(tmp_path)}) is None
    assert pdfutil.heading_page(f, ["references"], env={"PATH": str(tmp_path)}) is None


def _fake_text(tmp_path, text):
    b = tmp_path / "bin"; b.mkdir(exist_ok=True)
    (b / "pdftotext").write_text("#!/bin/sh\nprintf '" + text + "'\n"); (b / "pdftotext").chmod(0o755)
    f = tmp_path / "e.pdf"; f.write_bytes(_plain_pdf(3))
    return f, {"PATH": str(b)}


def test_body_end_heading_opening_a_page_ends_the_body_before_it(tmp_path):
    f, env = _fake_text(tmp_path, "body\\n\\fbody\\n\\f\\n 042 \\nLimitations\\ntext\\n")
    assert pdfutil.body_end(f, ["limitations", "references"], env=env) == 2
    f, env = _fake_text(tmp_path, "body\\n\\fbody\\n\\fmore body\\nLimitations\\n")
    assert pdfutil.body_end(f, ["limitations"], env=env) == 3
    f, env = _fake_text(tmp_path, "Limitations\\n\\fbody\\n")
    assert pdfutil.body_end(f, ["limitations"], env=env) == 1
    assert pdfutil.body_end(f, ["appendix"], env=env) is None


def test_headings_read_in_reading_order_not_layout(tmp_path):
    """-layout puts ACL review line numbers and the other column on the heading's line."""
    b = tmp_path / "bin"; b.mkdir()
    (b / "pdftotext").write_text(
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  *-layout*) printf 'body\\n\\fbody\\n\\fLimitations      1665\\n' ;;\n"
        "  *) printf 'body\\n\\fbody\\n\\fLimitations\\n1665\\nSome limits.\\n' ;;\n"
        "esac\n")
    (b / "pdftotext").chmod(0o755)
    f = tmp_path / "e.pdf"; f.write_bytes(_plain_pdf(3))
    env = {"PATH": str(b)}
    assert pdfutil.body_end(f, ["limitations"], env=env) == 2
    assert pdfutil.heading_page(f, ["limitations"], env=env) == 3
    assert "1665" in pdfutil.pdf_text(f, env=env)  # the anonymity scan still reads the layout text

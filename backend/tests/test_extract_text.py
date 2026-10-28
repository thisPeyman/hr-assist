"""Pipeline seam: OSS text extraction (spec §7.3 layer 1).

PDFs go through a pypdf pre-pass (encryption/corruption) into pdfplumber;
DOCX through python-docx with a raw-XML strip fallback; TXT is trivial.
Every unusable document raises ExtractionError with a stable machine reason —
the pipeline maps that to an explicit `needs_review` terminal status.
"""

import io
import zipfile

import pytest
from docx import Document

from app.parsing.extract_text import ExtractionError, extract_text, sniff_kind

# --------------------------------------------------------------------------
# Helpers: build real PDF/DOCX fixtures in-memory
# --------------------------------------------------------------------------


def make_pdf(lines: list[str]) -> bytes:
    """A minimal, valid single-page PDF with the given text lines (ASCII)."""
    content = "BT /F1 12 Tf 72 720 Td\n" + "".join(
        f"({line}) Tj 0 -16 Td\n" for line in lines
    )
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(content)} >>\nstream\n{content}\nendstream".encode(),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for n, body in objects.items():
        offsets[n] = len(out)
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for n in range(1, len(objects) + 1):
        out += f"{offsets[n]:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode()
    return bytes(out)


def make_docx(paragraphs: list[str]) -> bytes:
    doc = Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_textbox_docx(text: str) -> bytes:
    """A DOCX whose only text lives where python-docx's paragraph.text does
    not look (text-box content) — exercises the raw-XML strip fallback."""
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p/><w:p>"
        "<w:pict><w:txbxContent><w:p><w:r><w:t>"
        f"{text}"
        "</w:t></w:r></w:p></w:txbxContent></w:pict>"
        "</w:p></w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels"'
            ' ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            "<Override PartName=\"/word/document.xml\""
            ' ContentType="application/vnd.openxmlformats-officedocument'
            '.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            "<Relationship Id=\"rId1\""
            ' Type="http://schemas.openxmlformats.org/officeDocument/2006'
            '/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        z.writestr("word/document.xml", document_xml)
    return buf.getvalue()


# --------------------------------------------------------------------------
# Sniffing (content wins, not the filename)
# --------------------------------------------------------------------------


def test_sniff_pdf_by_magic_bytes():
    assert sniff_kind(make_pdf(["hi"]), "upload.bin") == "pdf"


def test_sniff_docx_by_zip_contents():
    assert sniff_kind(make_docx(["سلام"]), "upload.bin") == "docx"


def test_sniff_txt():
    assert sniff_kind("مهندس نرم‌افزار".encode(), "upload.bin") == "txt"


def test_sniff_zip_without_document_xml_is_unsupported():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("not-a-doc.txt", "x")
    with pytest.raises(ExtractionError) as exc:
        sniff_kind(buf.getvalue(), "archive.zip")
    assert exc.value.reason == "unsupported_format"


def test_sniff_binary_junk_is_unsupported():
    with pytest.raises(ExtractionError) as exc:
        sniff_kind(b"\x00\xff\x80" + bytes(range(256)), "unknown.bin")
    assert exc.value.reason == "unsupported_format"


# --------------------------------------------------------------------------
# TXT — trivial, values verbatim
# --------------------------------------------------------------------------


def test_txt_mixed_persian_english_verbatim():
    resume = (
        "پیمان رضایی\n"
        "Senior Backend Engineer — مهندس ارشد نرم‌افزار\n"
        "مهارت‌ها: Python, Django, PostgreSQL, Docker\n"
        "تجربه کاری:\n"
        "شرکت فناور — ۱۳۹۸ تا ۱۴۰۲\n"
        "Digikala — 2022 to 2024"
    ).encode()
    extracted = extract_text(resume, "resume.txt")
    for fragment in (
        "پیمان رضایی",
        "Senior Backend Engineer",
        "مهارت‌ها: Python, Django, PostgreSQL, Docker",
        "شرکت فناور — ۱۳۹۸ تا ۱۴۰۲",
        "Digikala — 2022 to 2024",
    ):
        assert fragment in extracted.text


def test_txt_empty_raises_empty_text():
    with pytest.raises(ExtractionError) as exc:
        extract_text(b"   \n\t  ", "empty.txt")
    assert exc.value.reason == "empty_text"


# --------------------------------------------------------------------------
# DOCX — python-docx primary, raw-XML fallback
# --------------------------------------------------------------------------


def test_docx_paragraphs_and_persian_verbatim():
    data = make_docx(
        [
            "پیمان رضایی",
            "Senior Backend Engineer",
            "Skills: Python, PostgreSQL",
        ]
    )
    extracted = extract_text(data, "resume.docx")
    assert "پیمان رضایی" in extracted.text
    assert "Senior Backend Engineer" in extracted.text
    assert "Skills: Python, PostgreSQL" in extracted.text


def test_docx_textbox_falls_back_to_raw_xml_strip():
    data = make_textbox_docx("مهندس نرم‌افزار — Python Developer")
    extracted = extract_text(data, "textbox.docx")
    assert "مهندس نرم‌افزار — Python Developer" in extracted.text


def test_docx_with_no_text_anywhere_raises():
    data = make_docx(["", "   "])
    with pytest.raises(ExtractionError) as exc:
        extract_text(data, "blank.docx")
    assert exc.value.reason == "docx_empty"


# --------------------------------------------------------------------------
# PDF — pypdf pre-pass, pdfplumber extraction
# --------------------------------------------------------------------------


def test_pdf_extracts_text():
    data = make_pdf(
        [
            "John Doe",
            "Senior Backend Engineer",
            "Skills: Python, PostgreSQL, Docker",
        ]
    )
    extracted = extract_text(data, "resume.pdf")
    assert "John Doe" in extracted.text
    assert "Senior Backend Engineer" in extracted.text
    assert "Skills: Python, PostgreSQL, Docker" in extracted.text


def test_pdf_corrupt_raises_corrupt():
    with pytest.raises(ExtractionError) as exc:
        extract_text(b"%PDF-1.4\nthis is not really a pdf\n%%EOF", "broken.pdf")
    assert exc.value.reason == "corrupt_pdf"


def test_pdf_page_without_text_raises_scanned():
    """A page with no text layer is a scan — OCR arrives with ticket 21;
    for now it must land in needs_review, never silently pass."""
    with pytest.raises(ExtractionError) as exc:
        extract_text(make_pdf([]), "scanned.pdf")
    assert exc.value.reason == "scanned_or_empty"


# --------------------------------------------------------------------------
# Normalization + truncation (research 02 §5)
# --------------------------------------------------------------------------


def test_whitespace_is_collapsed_but_lines_kept():
    messy = "پیمان  رضایی\n\n\n\n   Senior   Engineer\n\n\nمهارت‌ها"
    extracted = extract_text(messy.encode(), "resume.txt")
    # 4-newline runs collapse to one paragraph break; runs of spaces collapse
    # to one; ZWNJ (مهارت‌ها) survives verbatim.
    assert extracted.text == "پیمان رضایی\n\nSenior Engineer\n\nمهارت\u200cها"


def test_long_text_truncated_at_cap_with_flag():
    from app.config import settings

    body = ("سطر رزومه مهندس نرم‌افزار\n" * 3000).encode()
    extracted = extract_text(body, "huge.txt")
    assert extracted.truncated is True
    assert len(extracted.text) <= settings.resume_text_cap_chars

"""Underline detection from vector strokes."""

import io

import pdfplumber
import pytest
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from pdf_converter.extraction.underline import (
    attach_underlines_from_strokes,
    word_has_underline_stroke,
    underline_strokes,
)
from pdf_converter.extraction.word_enrich import extract_words_styled
from pdf_converter.extraction.styling import spans_from_words


def _pdf_with_underline_line() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(100, 700, "Linked")
    c.setStrokeColorRGB(0, 0, 0)
    c.line(100, 693, 140, 693)
    c.drawString(100, 650, "Plain")
    c.save()
    buf.seek(0)
    return buf.read()


def test_word_has_underline_stroke():
    data = _pdf_with_underline_line()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page = pdf.pages[0]
        strokes = underline_strokes(page)
        words = page.extract_words(extra_attrs=["fontname", "size"])
        linked = next(w for w in words if w["text"] == "Linked")
        plain = next(w for w in words if w["text"] == "Plain")
        assert word_has_underline_stroke(linked, strokes)
        assert not word_has_underline_stroke(plain, strokes)


def test_attach_underlines_from_strokes():
    data = _pdf_with_underline_line()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(extra_attrs=["fontname", "size"])
        enriched = attach_underlines_from_strokes(page, words)
        by_text = {w["text"]: w for w in enriched}
        assert by_text["Linked"].get("underline")
        assert not by_text["Plain"].get("underline")


@pytest.mark.skipif(
    not __import__("pathlib").Path("resume.pdf").exists(),
    reason="resume.pdf not in repo",
)
def test_resume_contact_links_underlined():
    with pdfplumber.open("resume.pdf") as pdf:
        page = pdf.pages[0]
        words = extract_words_styled(page)
        underlined = [w["text"] for w in words if w.get("underline")]
        assert "Portfolio" in underlined or "Github" in underlined
        spans = spans_from_words(words)
        assert any(s.underline for s in spans)

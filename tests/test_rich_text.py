"""Rich text span extraction and rendering."""

from pdf_converter.extraction.styling import spans_from_words, style_from_fontname
from pdf_converter.models import TextBlock, TextSpan
from pdf_converter.rendering.rich_text import block_inline_html, spans_to_html, spans_to_markdown


def test_style_from_fontname_bold_italic():
    assert style_from_fontname("Arial-Bold") == (True, False, False, False)
    assert style_from_fontname("TimesNewRoman-Italic") == (False, True, False, False)
    assert style_from_fontname("Courier") == (False, False, True, False)
    assert style_from_fontname("Arial-BoldUnderline") == (True, False, False, True)


def test_spans_from_words_merges_runs():
    words = [
        {"text": "Hello", "fontname": "Arial-Bold", "size": 12, "top": 100},
        {"text": "World", "fontname": "Arial-Bold", "size": 12, "top": 100},
    ]
    spans = spans_from_words(words)
    assert len(spans) == 1
    assert spans[0].bold
    assert "Hello" in spans[0].text and "World" in spans[0].text


def test_spans_to_html_bold_and_link():
    spans = [
        TextSpan(text="Agreement", bold=True),
        TextSpan(text=" docs", link="https://example.com"),
    ]
    html_out = spans_to_html(spans)
    assert "<strong>Agreement</strong>" in html_out
    assert 'href="https://example.com"' in html_out


def test_spans_to_markdown():
    spans = [TextSpan(text="Title", bold=True)]
    assert spans_to_markdown(spans) == "**Title**"


def test_spans_to_html_and_markdown_underline():
    spans = [TextSpan(text="Portfolio", underline=True, link="https://example.com")]
    assert "<u>Portfolio</u>" in spans_to_html(spans)
    assert 'href="https://example.com"' in spans_to_html(spans)
    md = spans_to_markdown(spans)
    assert "<u>Portfolio</u>" in md
    assert "https://example.com" in md


def test_block_inline_html_uses_spans():
    block = TextBlock(
        text="DEVELOPMENT AGREEMENT",
        role="h1",
        spans=[TextSpan(text="DEVELOPMENT AGREEMENT", bold=True)],
    )
    assert "<strong>DEVELOPMENT AGREEMENT</strong>" in block_inline_html(block)

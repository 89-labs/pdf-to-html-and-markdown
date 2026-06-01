"""Layout structure extraction tests."""

from pdf_converter.extraction.layout_structure import (
    _merge_lines_to_paragraphs,
    _split_inline_bullets,
)


def test_merge_wraps_lowercase_continuation():
    lines = [
        {"text": "This Agreement (", "top": 0, "x0": 0, "size": 11},
        {"text": "Effective Date) continues.", "top": 1, "x0": 0, "size": 11},
    ]
    merged = _merge_lines_to_paragraphs(lines)
    assert len(merged) == 1
    assert "Effective Date" in merged[0]["text"]


def test_split_bullets():
    parts = _split_inline_bullets("● One ● Two")
    assert len(parts) >= 2
    assert parts[1][0] == "list_item"

"""Tests for validation."""

from pdf_converter.models import PageContent, PageStats, TextBlock
from pdf_converter.validation import (
    compute_coverage_ratio,
    has_critical,
    validate_output,
)


def test_coverage_ratio():
    pages = [
        PageContent(
            page_num=0,
            mode="native",
            text_blocks=[TextBlock(text="hello world", role="paragraph")],
            raw_text="hello world",
        )
    ]
    ratio = compute_coverage_ratio(pages, "hello world")
    assert ratio >= 0.9


def test_critical_short_output():
    issues = validate_output("short", page_count=10, fmt="markdown")
    assert has_critical(issues)

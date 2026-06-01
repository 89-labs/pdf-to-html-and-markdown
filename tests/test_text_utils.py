"""Tests for text utilities."""

from pdf_converter.text_utils import detect_role, sanitise_text, split_merged_block


def test_sanitise_cid_bullet():
    assert "•" in sanitise_text("Item (cid:127) more")


def test_detect_heading():
    assert detect_role("Chapter One", 24.0, 12.0) == "h1"
    assert detect_role("Section", 18.0, 12.0) == "h2"


def test_split_merged_bullets():
    parts = split_merged_block("Intro text • first • second", "paragraph")
    assert len(parts) == 3
    assert parts[1]["role"] == "list_item"


def test_split_merged_no_bullets():
    parts = split_merged_block("Plain paragraph only.", "paragraph")
    assert len(parts) == 1

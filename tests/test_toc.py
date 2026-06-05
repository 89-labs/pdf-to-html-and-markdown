"""Tests for table-of-contents detection and extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

from pdf_converter.extraction.toc import (
    extract_standard_toc_blocks,
    is_standard_toc_page,
    is_toc_page,
)
from pdf_converter.models import TextBlock


def _page_with_layout(text: str) -> MagicMock:
    page = MagicMock()
    page.chars = []
    page.extract_text.return_value = text
    return page


SAMPLE_TOC = """
                                        CONTENTS

                 PREFACE                                                 7

               1 MATHEMATICAL PRELIMINARIES

                1.1 Invariants                                          11
                1.2 Some geometrical invariants                         12
                1.3 Elements of differential geometry                   15
                1.4 Gaussian coordinates and the invariant line element  17
                1.5 Geometry and groups                                 20
                1.6 Vectors                                             23
"""


def test_is_standard_toc_page_with_contents_header():
    page = _page_with_layout(SAMPLE_TOC)
    assert is_standard_toc_page(page) is True
    assert is_toc_page(page) is True


def test_extract_standard_toc_blocks_structure():
    page = _page_with_layout(SAMPLE_TOC)
    blocks = extract_standard_toc_blocks(page)
    roles = [b.role for b in blocks]
    assert roles[0] == "h2"
    assert blocks[0].text == "Contents"
    assert any(b.role == "toc_chapter" and b.text.startswith("1 MATHEMATICAL") for b in blocks)
    inv = next(b for b in blocks if b.text.startswith("1.1 Invariants"))
    assert inv.role == "toc_item"
    assert inv.meta.get("page") == "11"
    preface = next(b for b in blocks if b.text == "PREFACE")
    assert preface.meta.get("page") == "7"


def test_toc_continuation_without_contents():
    text = """
4
4.2 Newton's laws of motion                              77
4.3 Many interacting particles: conservation of linear and angular momentum 77
4.4 Work and energy in Newtonian dynamics                84
4.5 Potential energy                                     86
4.6 Particle interactions                                89
4.7 The motion of rigid bodies                           94
4.8 Angular velocity and the instantaneous center of rotation 97
5 INVARIANCE PRINCIPLES AND CONSERVATION LAWS
5.1 Invariance of the potential under translations 105
"""
    page = _page_with_layout(text)
    assert is_standard_toc_page(page) is True
    blocks = extract_standard_toc_blocks(page)
    assert not any(b.text == "Contents" for b in blocks)
    assert len([b for b in blocks if b.role == "toc_item"]) >= 6

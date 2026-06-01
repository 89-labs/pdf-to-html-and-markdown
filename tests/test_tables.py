"""Table validation tests."""

from pdf_converter.extraction.tables import (
    filter_tables,
    is_valid_table,
    text_similarity,
)


class FakePage:
    width = 612
    height = 792
    lines = []


def test_text_similarity_high_for_duplicates():
    a = "Hello world this is a test document"
    b = "Hello world this is a test document with extra"
    assert text_similarity(a, b) > 0.7


def test_reject_single_row_table():
    page = FakePage()
    table = [["a", "b", "c"]]
    assert not is_valid_table(table, None, page)


def test_reject_text_inferred_without_lines():
    page = FakePage()
    table = [
        ["Front", "end", "Dev"],
        ["elop", "ment", "React"],
    ]
    assert not is_valid_table(table, (0, 0, 600, 700), page, allow_text_inferred=False)


def test_filter_drops_duplicate_of_body():
    page = FakePage()
    body = "Frontend Development React Native Next.js Vue"
    table = [
        ["Frontend", "Dev", "elopment"],
        ["React", "Native", "Next.js"],
    ]
    kept, _ = filter_tables([table], [(0, 0, 600, 700)], body, page)
    assert len(kept) == 0

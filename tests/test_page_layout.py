"""Page layout detection and column splitting."""

from pdf_converter.extraction.columns import (
    count_substantial_thirds,
    split_words_by_page_regions,
)
from pdf_converter.extraction.page_layout import (
    is_factor_sheet_page,
    is_index_page,
    is_photo_credits_page,
    should_use_text_inferred_tables,
)


def test_is_index_page():
    assert is_index_page("I-2 Index\nArchimedes")
    assert not is_index_page("Chapter 1 Introduction")


def test_is_factor_sheet_page():
    assert is_factor_sheet_page("APPENDIX E\nUNIT CONVERSION FACTORS")
    assert not is_factor_sheet_page("NUMERICAL CONSTANTS")


def test_is_photo_credits_page():
    text = "Chapter22Opener: NASA; Chapter23Opener: Getty"
    assert is_photo_credits_page(text)
    assert is_photo_credits_page("Chapter 22 Opener: NASA; Chapter 23 Opener: Getty")
    assert not is_photo_credits_page("Chapter 1 Introduction")


def test_should_use_text_inferred_tables():
    assert should_use_text_inferred_tables(
        book_mode=True, allow_text_tables=False, raw_text="NUMERICAL CONSTANTS"
    )
    assert not should_use_text_inferred_tables(
        book_mode=True,
        allow_text_tables=False,
        raw_text="I-2 Index\nVoltage, 761",
    )
    assert not should_use_text_inferred_tables(
        book_mode=True,
        allow_text_tables=False,
        raw_text="UNIT CONVERSION FACTORS\nLength",
    )
    assert not should_use_text_inferred_tables(
        book_mode=True,
        allow_text_tables=False,
        raw_text="Chapter 22 Opener: NASA; Chapter 23 Opener: Getty",
    )


def test_split_words_by_page_thirds():
    page_width = 600.0
    words = []
    for col in range(3):
        for i in range(30):
            x0 = col * 200 + 10
            words.append(
                {
                    "text": f"w{col}{i}",
                    "x0": x0,
                    "x1": x0 + 20,
                    "top": i * 10,
                    "bottom": i * 10 + 8,
                }
            )
    cols = split_words_by_page_regions(words, page_width, 3)
    assert len(cols) == 3
    assert count_substantial_thirds(words, page_width, min_words=20) == 3

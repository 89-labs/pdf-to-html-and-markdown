"""Document-level extraction orchestration."""

from __future__ import annotations

import logging

import pdfplumber

from pdf_converter.extraction.classifier import classify_page
from pdf_converter.extraction.native import extract_native_page
from pdf_converter.extraction.ocr import build_ocr_page, rasterize_pages
from pdf_converter.extraction.page_cleanup import detect_running_texts, filter_words_furniture

log = logging.getLogger(__name__)


def extract_document(
    pdf_path: str,
    *,
    prose_mode: bool = False,
    allow_text_tables: bool = False,
    book_mode: bool = False,
) -> list:
    """
    Extract all pages using pdfplumber + batched OCR fallback.
    Returns list of PageContent in page order.
    """
    pages: list = []
    ocr_page_indices: list[int] = []

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        log.info("Extracting %s pages with pdfplumber engine...", total)

        all_page_words: list[list[dict]] = []
        classifications: list[tuple[int, str]] = []
        for i, page in enumerate(pdf.pages):
            try:
                w = page.extract_words(
                    extra_attrs=["fontname", "size"],
                    use_text_flow=not (prose_mode or book_mode),
                )
            except Exception:
                w = page.extract_words()
            all_page_words.append(w)
            mode = classify_page(page)
            classifications.append((i, mode))
            if mode == "ocr":
                ocr_page_indices.append(i)

        running_texts = (
            detect_running_texts(all_page_words) if book_mode else set()
        )
        if running_texts:
            log.info("  Detected %s repeating header/footer patterns", len(running_texts))

        rasterized = rasterize_pages(pdf_path, ocr_page_indices)

        for i, page in enumerate(pdf.pages):
            log.info("  Page %s/%s", i + 1, total)
            mode = classifications[i][1]
            if mode == "native":
                content = extract_native_page(
                    page,
                    i,
                    prose_mode=prose_mode or book_mode,
                    allow_text_tables=allow_text_tables,
                    book_mode=book_mode,
                    running_texts=running_texts if book_mode else None,
                )
            else:
                img = rasterized.get(i)
                if img is None:
                    rasterized.update(rasterize_pages(pdf_path, [i]))
                    img = rasterized[i]
                content = build_ocr_page(i, img)
            pages.append(content)

    return pages

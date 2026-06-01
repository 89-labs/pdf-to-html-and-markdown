"""OCR extraction for scanned pages (batched rasterization)."""

from __future__ import annotations

import logging
from io import BytesIO

import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from pdf_converter.models import PageContent, PageImage, PageStats, TextBlock

log = logging.getLogger(__name__)

OCR_DPI = 300
MIN_CONFIDENCE = 30


def rasterize_pages(
    pdf_path: str,
    page_indices: list[int],
    dpi: int = OCR_DPI,
) -> dict[int, Image.Image]:
    """
    Rasterize multiple pages in minimal poppler calls.
    Groups consecutive page ranges for efficiency.
    """
    if not page_indices:
        return {}

    sorted_pages = sorted(set(page_indices))
    result: dict[int, Image.Image] = {}

    # Group into consecutive ranges
    ranges: list[tuple[int, int]] = []
    start = sorted_pages[0]
    end = start
    for p in sorted_pages[1:]:
        if p == end + 1:
            end = p
        else:
            ranges.append((start, end))
            start = end = p
    ranges.append((start, end))

    for first_idx, last_idx in ranges:
        images = convert_from_path(
            pdf_path,
            first_page=first_idx + 1,
            last_page=last_idx + 1,
            dpi=dpi,
            fmt="png",
        )
        for offset, img in enumerate(images):
            result[first_idx + offset] = img

    return result


def ocr_image(page_image: Image.Image) -> tuple[list[TextBlock], str, float | None]:
    """Run Tesseract on a page image; return blocks, raw text, mean confidence."""
    ocr_data = pytesseract.image_to_data(
        page_image,
        output_type=pytesseract.Output.DICT,
        config="--psm 6 --oem 3",
        lang="eng",
    )

    paragraphs: list[str] = []
    current_para: list[str] = []
    last_block = None
    last_par = None
    confidences: list[int] = []

    for i, word in enumerate(ocr_data["text"]):
        word = (word or "").strip()
        if not word:
            continue
        conf = int(ocr_data["conf"][i])
        if conf < MIN_CONFIDENCE:
            continue
        confidences.append(conf)
        block_num = ocr_data["block_num"][i]
        par_num = ocr_data["par_num"][i]

        if last_block is not None and (
            block_num != last_block or par_num != last_par
        ):
            if current_para:
                paragraphs.append(" ".join(current_para))
                current_para = []

        current_para.append(word)
        last_block = block_num
        last_par = par_num

    if current_para:
        paragraphs.append(" ".join(current_para))

    text_blocks = [
        TextBlock(text=p, role="paragraph", bbox=None, font_size=12.0)
        for p in paragraphs
        if p.strip()
    ]
    raw_text = "\n".join(paragraphs)
    mean_conf = sum(confidences) / len(confidences) if confidences else None
    return text_blocks, raw_text, mean_conf


def build_ocr_page(
    page_num: int,
    page_image: Image.Image,
) -> PageContent:
    """Build PageContent from a pre-rasterized image."""
    log.info("  Page %s: OCR mode (scanned page)", page_num + 1)
    text_blocks, raw_text, mean_conf = ocr_image(page_image)

    buf = BytesIO()
    page_image.save(buf, format="PNG")
    page_images = [
        PageImage(
            data=buf.getvalue(),
            ext="png",
            bbox=None,
            index=0,
            is_full_page=True,
        )
    ]

    all_text = raw_text or " ".join(b.text for b in text_blocks)
    stats = PageStats(
        page_num=page_num,
        mode="ocr",
        char_count=len(all_text),
        word_count=len(all_text.split()),
        table_count=0,
        image_count=1,
        ocr_mean_confidence=mean_conf,
    )

    return PageContent(
        page_num=page_num,
        mode="ocr",
        text_blocks=text_blocks,
        tables=[],
        images=page_images,
        raw_text=raw_text,
        stats=stats,
    )

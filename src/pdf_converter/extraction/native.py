"""Native (text-based) page extraction via pdfplumber."""

from __future__ import annotations

import logging
import re
from io import BytesIO

from pdf_converter.extraction.columns import detect_column_x0_peaks
from pdf_converter.extraction.page_layout import page_text_hint, should_use_text_inferred_tables
from pdf_converter.extraction.word_enrich import extract_words_styled
from pdf_converter.extraction.layout_structure import extract_blocks_from_layout
from pdf_converter.extraction.page_cleanup import filter_words_furniture
from pdf_converter.extraction.tables import filter_tables, page_has_ruling_lines
from pdf_converter.models import PageContent, PageImage, PageStats, TextBlock  # noqa: F401 — TextBlock used for diagram pages
from pdf_converter.text_utils import detect_role, sanitise_text, split_merged_block

log = logging.getLogger(__name__)

TABLE_OVERLAP_THRESHOLD = 0.15


def _expand_bbox(
    bbox: tuple[float, float, float, float],
    *,
    pad: float = 8.0,
) -> tuple[float, float, float, float]:
    """Expand a bbox slightly to avoid leaving edge fragments behind."""
    x0, top, x1, bottom = bbox
    return (x0 - pad, top - pad, x1 + pad, bottom + pad)


def _bbox_overlap_ratio(
    word_bbox: tuple[float, float, float, float],
    table_bbox: tuple[float, float, float, float],
) -> float:
    x0, top, x1, bottom = word_bbox
    tx0, ttop, tx1, tbottom = table_bbox
    ox = max(0, min(x1, tx1) - max(x0, tx0))
    oy = max(0, min(bottom, tbottom) - max(top, ttop))
    overlap = ox * oy
    word_area = max((x1 - x0) * (bottom - top), 1e-6)
    return overlap / word_area


def _in_table(
    bbox: tuple[float, float, float, float] | None,
    table_bboxes: list[tuple[float, float, float, float]],
) -> bool:
    if not bbox or not table_bboxes:
        return False
    return any(
        _bbox_overlap_ratio(bbox, tb) >= TABLE_OVERLAP_THRESHOLD for tb in table_bboxes
    )


def _sort_words_in_line(line: list) -> list:
    return sorted(line, key=lambda w: (w.get("top", 0), w.get("x0", 0)))


def _group_words_into_blocks(words: list, avg_font: float) -> list[TextBlock]:
    """Group words into lines/blocks with left-to-right reading order."""
    lines: list[list] = []
    for w in words:
        placed = False
        for line in lines:
            if abs(line[-1]["top"] - w["top"]) < 3:
                line.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])

    lines = [_sort_words_in_line(line) for line in lines]
    lines.sort(key=lambda ln: ln[0]["top"] if ln else 0)

    blocks: list[list] = []
    for line in lines:
        if not blocks:
            blocks.append([line])
            continue
        last_line = blocks[-1][-1]
        last_bottom = max(w["bottom"] for w in last_line)
        line_height = max(w["bottom"] - w["top"] for w in line) if line else 12
        gap = line[0]["top"] - last_bottom
        if gap > line_height * 1.5:
            blocks.append([line])
        else:
            blocks[-1].append(line)

    text_blocks: list[TextBlock] = []
    for block_lines in blocks:
        all_words = [w for line in block_lines for w in line]
        raw_text = " ".join(w["text"] for line in block_lines for w in line)
        block_text = sanitise_text(raw_text)
        if not block_text:
            continue
        avg_size = (
            sum(w.get("size", avg_font) or avg_font for w in all_words) / len(all_words)
        )
        bbox = (
            min(w["x0"] for w in all_words),
            min(w["top"] for w in all_words),
            max(w["x1"] for w in all_words),
            max(w["bottom"] for w in all_words),
        )
        role = detect_role(block_text, avg_size, avg_font)
        for sb in split_merged_block(block_text, role):
            text_blocks.append(
                TextBlock(
                    text=sb["text"],
                    role=sb["role"],
                    bbox=bbox,
                    font_size=round(avg_size, 1),
                )
            )
    return text_blocks


def _blocks_from_layout_text(raw_text: str, avg_font: float) -> list[TextBlock]:
    """Fallback: split layout-preserved text into paragraphs."""
    if not raw_text:
        return []
    blocks: list[TextBlock] = []
    for para in re.split(r"\n\s*\n+", raw_text):
        para = sanitise_text(para.replace("\n", " ").strip())
        if not para:
            continue
        role = detect_role(para, avg_font, avg_font)
        for sb in split_merged_block(para, role):
            blocks.append(
                TextBlock(text=sb["text"], role=sb["role"], bbox=None, font_size=avg_font)
            )
    return blocks


def _extract_tables(
    plumber_page,
    *,
    prose_mode: bool,
    allow_text_tables: bool,
) -> tuple[list, list]:
    """Extract tables using line-based detection only unless explicitly allowed."""
    if prose_mode:
        return [], []

    table_settings = {
        "vertical_strategy": "lines_strict",
        "horizontal_strategy": "lines_strict",
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "edge_min_length": 10,
        "min_words_vertical": 1,
        "min_words_horizontal": 1,
    }

    extracted: list = []
    table_bboxes: list = []

    try:
        if page_has_ruling_lines(plumber_page) or allow_text_tables:
            extracted = plumber_page.extract_tables(table_settings) or []
            for tbl_finder in plumber_page.find_tables(table_settings) or []:
                table_bboxes.append(tbl_finder.bbox)

            if not extracted and allow_text_tables:
                extracted = (
                    plumber_page.extract_tables(
                        {
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "snap_tolerance": 4,
                        }
                    )
                    or []
                )
                for tbl_finder in (
                    plumber_page.find_tables(
                        {
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                        }
                    )
                    or []
                ):
                    table_bboxes.append(tbl_finder.bbox)
    except Exception as e:
        log.debug("Table extraction failed: %s", e)

    return extracted, table_bboxes


def _extract_page_images(
    plumber_page,
    page_num: int,
    *,
    book_mode: bool = False,
    min_image_pt: float = 10,
) -> list[PageImage]:
    """Extract embedded images; in book mode also capture large figures."""
    images: list[PageImage] = []
    threshold = 5 if book_mode else min_image_pt
    try:
        for idx, img_meta in enumerate(plumber_page.images):
            try:
                bbox = (
                    img_meta["x0"],
                    img_meta["top"],
                    img_meta["x1"],
                    img_meta["bottom"],
                )
                w_pt = img_meta["x1"] - img_meta["x0"]
                h_pt = img_meta["bottom"] - img_meta["top"]
                if w_pt < threshold or h_pt < threshold:
                    continue
                res = 200 if book_mode else 150
                cropped = plumber_page.crop(bbox).to_image(resolution=res)
                buf = BytesIO()
                cropped.save(buf, format="PNG")
                images.append(
                    PageImage(data=buf.getvalue(), ext="png", bbox=bbox, index=idx)
                )
            except Exception as e:
                log.debug("Image crop failed p%s img%s: %s", page_num, idx, e)
    except Exception:
        pass
    return images


def _maybe_full_page_figure(
    plumber_page,
    page_num: int,
    word_count: int,
    existing_images: list[PageImage],
    *,
    force: bool = False,
) -> list[PageImage]:
    """For sparse mostly-visual pages, rasterize the full page."""
    if not force and (word_count > 120 or existing_images):
        return existing_images
    try:
        page_img = plumber_page.to_image(resolution=200)
        buf = BytesIO()
        page_img.save(buf, format="PNG")
        return [
            PageImage(
                data=buf.getvalue(),
                ext="png",
                bbox=None,
                index=0,
                is_full_page=True,
            )
        ]
    except Exception as e:
        log.debug("Full page raster failed p%s: %s", page_num, e)
        return existing_images


def extract_native_page(
    plumber_page,
    page_num: int,
    *,
    prose_mode: bool = False,
    allow_text_tables: bool = False,
    book_mode: bool = False,
    running_texts: set[str] | None = None,
) -> PageContent:
    """Extract structured content from a native PDF page."""
    font_sizes: list[float] = []
    try:
        for char in plumber_page.chars:
            if char.get("size"):
                font_sizes.append(float(char["size"]))
    except Exception:
        pass
    avg_font = sum(font_sizes) / len(font_sizes) if font_sizes else 12.0

    raw_lines = plumber_page.extract_text(layout=True) or ""
    raw_text = sanitise_text(raw_lines)

    hyperlinks: list = []
    try:
        hyperlinks = plumber_page.hyperlinks or []
    except Exception:
        pass

    words = extract_words_styled(
        plumber_page,
        use_text_flow=not prose_mode,
        hyperlinks=hyperlinks,
    )

    layout_hint = page_text_hint(plumber_page, words)
    effective_allow_text_tables = should_use_text_inferred_tables(
        book_mode=book_mode,
        allow_text_tables=allow_text_tables,
        raw_text=layout_hint or raw_text,
    )

    extracted, table_bboxes = _extract_tables(
        plumber_page,
        prose_mode=prose_mode,
        allow_text_tables=effective_allow_text_tables,
    )

    if book_mode and running_texts:
        words = filter_words_furniture(words, running_texts)

    pre_body = " ".join(w["text"] for w in words)
    tables, table_bboxes = filter_tables(
        extracted,
        table_bboxes,
        pre_body,
        plumber_page,
        allow_text_inferred=effective_allow_text_tables,
    )

    if table_bboxes:
        table_bboxes = [_expand_bbox(tb) for tb in table_bboxes]

    words = [
        w
        for w in words
        if not _in_table(
            (w.get("x0"), w.get("top"), w.get("x1"), w.get("bottom")),
            table_bboxes,
        )
    ]

    text_blocks = extract_blocks_from_layout(
        plumber_page, words, page_index=page_num, book_mode=book_mode
    )

    if len(text_blocks) < 2:
        text_blocks = _group_words_into_blocks(words, avg_font)
        if len(text_blocks) < 2 and raw_text:
            layout_blocks = _blocks_from_layout_text(raw_text, avg_font)
            if len(layout_blocks) > len(text_blocks):
                text_blocks = layout_blocks

    body_text = " ".join(b.text for b in text_blocks) or raw_text
    tables, table_bboxes = filter_tables(
        tables,
        table_bboxes,
        body_text,
        plumber_page,
        allow_text_inferred=effective_allow_text_tables,
    )

    images = _extract_page_images(plumber_page, page_num, book_mode=book_mode)
    if book_mode:
        anchors = detect_column_x0_peaks(words, float(plumber_page.width))
        fragmented = len(anchors) > 4 and len(words) > 200
        images = _maybe_full_page_figure(
            plumber_page,
            page_num,
            len(words),
            images,
            force=fragmented and len(images) < 2,
        )
        if fragmented and images and images[0].is_full_page:
            text_blocks = [
                TextBlock(
                    text=f"Figure: page {page_num + 1} (diagram — see image below)",
                    role="paragraph",
                    bbox=None,
                    font_size=11.0,
                )
            ] + text_blocks[:3]

    all_text = body_text
    stats = PageStats(
        page_num=page_num,
        mode="native",
        char_count=len(all_text),
        word_count=len(all_text.split()),
        table_count=len(tables),
        image_count=len(images),
    )

    return PageContent(
        page_num=page_num,
        mode="native",
        text_blocks=text_blocks,
        tables=tables,
        images=images,
        raw_text=raw_text,
        stats=stats,
    )

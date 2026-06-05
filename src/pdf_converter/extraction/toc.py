"""Table of contents page extraction."""

from __future__ import annotations

import re

from pdf_converter.models import TextBlock
from pdf_converter.text_utils import sanitise_text

_TOC_ENTRY_END = re.compile(r"\s(\d{1,3})\s*$")
_TOC_LINE_PAGE = re.compile(r"^(.+?)\s+(\d{1,3})\s*$")
_TOC_SECTION = re.compile(
    r"^(Preface|Introduction|Appendix|Strategic milestones|Implementation|Dialogue Forum)",
    re.I,
)
_SKIP_LINE = re.compile(
    r"^(Strategy for space|Cover photo|Contents$|of Arctic|AWS is a satellite)",
    re.I,
)
_LONE_PAGE_NUM = re.compile(r"^\d{1,3}$")
_TOC_CHAPTER = re.compile(r"^(\d+)\s+([A-Z].*)$")
_TOC_SECTION_NUM = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\s+")
_TOC_MAJOR = re.compile(r"^(PREFACE|APPENDIX|BIBLIOGRAPHY|INDEX)\b", re.I)
_CONTENTS = re.compile(r"\bCONTENTS\b", re.I)


def _layout_lines(page) -> list[str]:
    raw = page.extract_text(layout=True) or ""
    return [sanitise_text(line.strip()) for line in raw.split("\n") if line.strip()]


def _toc_like_line_count(lines: list[str]) -> int:
    count = 0
    for line in lines:
        if _LONE_PAGE_NUM.match(line) or _CONTENTS.search(line):
            continue
        if _TOC_ENTRY_END.search(line):
            count += 1
    return count


def is_standard_toc_page(page, words: list[dict] | None = None) -> bool:
    """
    Detect textbook TOC from layout text (title left, page number right).

    Used when PDFs omit backspace leader dots (common in older texts).
    """
    lines = _layout_lines(page)
    if not lines:
        return False

    if any(_CONTENTS.search(line) for line in lines):
        return _toc_like_line_count(lines) >= 5

    # Continuation pages: many section lines with trailing page numbers.
    non_footer = [ln for ln in lines if not _LONE_PAGE_NUM.match(ln)]
    if len(non_footer) < 6:
        return False
    toc_like = _toc_like_line_count(lines)
    if toc_like < 8:
        return False
    section_lines = sum(1 for ln in non_footer if _TOC_SECTION_NUM.match(ln))
    if section_lines < 5:
        return False
    return toc_like / max(len(non_footer), 1) >= 0.55


def is_toc_page(page, words: list[dict] | None = None) -> bool:
    """Detect TOC via backspace leaders or standard layout."""
    try:
        bs = sum(1 for c in page.chars if c.get("text") == "\x08")
        if bs >= 15:
            return True
    except Exception:
        pass
    if words:
        text = " ".join(w.get("text", "") for w in words)
        if text.count("\x08") >= 15:
            return True
    return is_standard_toc_page(page, words)


def _lines_from_chars(page) -> list[str]:
    """Rebuild lines from chars, skipping backspace leader dots."""
    if not page.chars:
        return []
    sorted_chars = sorted(page.chars, key=lambda c: (round(c["top"]), c["x0"]))
    lines: list[str] = []
    current_top = None
    buf: list[str] = []
    for c in sorted_chars:
        ch = c.get("text") or ""
        if ch == "\x08":
            continue
        top = round(c["top"])
        if current_top is not None and top != current_top:
            line = sanitise_text("".join(buf))
            if line:
                lines.append(line)
            buf = []
        current_top = top
        buf.append(ch)
    if buf:
        line = sanitise_text("".join(buf))
        if line:
            lines.append(line)
    return lines


def _merge_toc_lines(lines: list[str]) -> list[str]:
    """Join wrapped TOC lines into complete entries ending with a page number."""
    merged: list[str] = []
    buf = ""
    for line in lines:
        line = line.strip()
        if not line or _SKIP_LINE.match(line):
            continue
        if buf:
            buf = f"{buf} {line}"
        else:
            buf = line
        if _TOC_ENTRY_END.search(buf) or _TOC_SECTION.match(buf):
            merged.append(buf.strip())
            buf = ""
    if buf.strip():
        merged.append(buf.strip())
    return merged


def _classify_toc_line(title: str, page_num: str | None) -> TextBlock:
    meta: dict = {}
    if page_num:
        meta["page"] = page_num

    if _TOC_MAJOR.match(title) or _TOC_CHAPTER.match(title):
        return TextBlock(
            text=title,
            role="toc_chapter",
            bbox=None,
            font_size=12.0,
            meta=meta,
        )
    if _TOC_SECTION_NUM.match(title):
        return TextBlock(
            text=title,
            role="toc_item",
            bbox=None,
            font_size=11.0,
            meta=meta,
        )
    return TextBlock(
        text=title,
        role="toc_item",
        bbox=None,
        font_size=11.0,
        meta=meta,
    )


def extract_standard_toc_blocks(page) -> list[TextBlock]:
    """Parse layout-preserved TOC lines (Firk-style, no leader dots)."""
    lines = _layout_lines(page)
    if not lines:
        return []

    blocks: list[TextBlock] = []
    has_contents = any(_CONTENTS.search(line) for line in lines)
    if has_contents:
        blocks.append(
            TextBlock(text="Contents", role="h2", bbox=None, font_size=14.0, meta={"toc_page": True})
        )

    for line in lines:
        if _LONE_PAGE_NUM.match(line):
            continue
        if _CONTENTS.search(line) and line.strip().upper() == "CONTENTS":
            continue

        m = _TOC_LINE_PAGE.match(line)
        if m:
            blocks.append(_classify_toc_line(m.group(1).strip(), m.group(2)))
            continue

        if _TOC_CHAPTER.match(line) or _TOC_MAJOR.match(line):
            blocks.append(_classify_toc_line(line, None))

    return blocks


def extract_toc_blocks(page) -> list[TextBlock]:
    """Parse TOC page into structured blocks."""
    standard = extract_standard_toc_blocks(page)
    if standard:
        return standard

    raw_lines = _lines_from_chars(page)
    lines = _merge_toc_lines(raw_lines)
    if not lines:
        return []

    blocks: list[TextBlock] = [
        TextBlock(text="Contents", role="h2", bbox=None, font_size=14.0),
    ]

    for line in lines:
        if _TOC_SECTION.match(line):
            m = _TOC_ENTRY_END.search(line)
            if m:
                title = line[: m.start()].strip()
                page_num = m.group(1)
                blocks.append(TextBlock(text=title, role="h3", bbox=None, font_size=12.0))
                blocks.append(
                    TextBlock(
                        text=f"(see page {page_num})",
                        role="paragraph",
                        bbox=None,
                        font_size=10.0,
                    )
                )
            else:
                blocks.append(TextBlock(text=line, role="h3", bbox=None, font_size=12.0))
            continue

        m = _TOC_ENTRY_END.search(line)
        if m:
            title = line[: m.start()].strip().rstrip(".")
            page_num = m.group(1)
            blocks.append(
                TextBlock(
                    text=title,
                    role="toc_item",
                    bbox=None,
                    font_size=11.0,
                    meta={"page": page_num},
                )
            )
        elif len(line) < 120:
            blocks.append(TextBlock(text=line, role="list_item", bbox=None, font_size=11.0))

    return blocks

"""Table of contents page extraction."""

from __future__ import annotations

import re

from pdf_converter.models import TextBlock
from pdf_converter.text_utils import sanitise_text

_TOC_ENTRY_END = re.compile(r"\s(\d{1,3})\s*$")
_TOC_SECTION = re.compile(
    r"^(Preface|Introduction|Appendix|Strategic milestones|Implementation|Dialogue Forum)",
    re.I,
)
_SKIP_LINE = re.compile(
    r"^(Strategy for space|Cover photo|Contents$|of Arctic|AWS is a satellite)",
    re.I,
)


def is_toc_page(page, words: list[dict] | None = None) -> bool:
    """Detect TOC from backspace leader dots in PDF char stream."""
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
    return False


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


def extract_toc_blocks(page) -> list[TextBlock]:
    """Parse TOC page into heading + list entries."""
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
                    text=f"{title} — p. {page_num}",
                    role="list_item",
                    bbox=None,
                    font_size=11.0,
                )
            )
        elif len(line) < 120:
            blocks.append(TextBlock(text=line, role="list_item", bbox=None, font_size=11.0))

    return blocks

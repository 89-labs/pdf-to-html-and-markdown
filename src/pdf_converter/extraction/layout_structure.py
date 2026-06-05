"""Layout-aware structure extraction (headings, lists, paragraphs)."""

from __future__ import annotations

import re
import statistics
from typing import Any, Optional

from pdf_converter.extraction.columns import (
    count_substantial_thirds,
    is_multi_column_page,
    split_two_column_body,
    split_words_by_columns,
    split_words_by_page_regions,
)
from pdf_converter.extraction.page_layout import (
    is_factor_sheet_page,
    is_index_page,
    is_photo_credits_page,
    page_text_hint,
)
from pdf_converter.extraction.toc import extract_toc_blocks, is_toc_page
from pdf_converter.extraction.styling import plain_text_from_spans, spans_from_words
from pdf_converter.models import TextBlock
from pdf_converter.text_utils import sanitise_text

_BULLET_START = re.compile(r"^[\u2022\u2023\u25E6\u2043●○■\-\*\+•]\s*")
_ORDERED_START = re.compile(r"^(\d+[\.\)])\s+")
_SUB_BULLET = re.compile(r"^[\u25A0○■]\s*")
_SECTION_INLINE = re.compile(
    r"^([A-Z][A-Za-z0-9 &/\-]{2,50}?)\.\s+(.+)$",
)
_LEGAL_SECTION = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z][A-Za-z]{2,}(?:\s+[A-Za-z]{2,})*\.\s)",
)
_EMAIL = re.compile(r"@")
_DATE_RANGE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[-–—]",
    re.I,
)
_SECTION_LABELS = frozenset(
    {
        "SKILLS",
        "EDUCATION",
        "PROJECTS",
        "EXPERIENCE",
        "PROFESSIONAL EXPERIENCE",
        "WORK EXPERIENCE",
        "CERTIFICATIONS",
        "SUMMARY",
    }
)


def _group_words_into_lines(words: list[dict], y_tolerance: float = 3) -> list[dict[str, Any]]:
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w.get("top", 0), w.get("x0", 0)))
    lines: list[list] = []
    for w in sorted_words:
        placed = False
        for line in lines:
            if abs(line[-1]["top"] - w["top"]) < y_tolerance:
                line.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])

    result: list[dict[str, Any]] = []
    for line_words in lines:
        line_words = sorted(line_words, key=lambda w: w.get("x0", 0))
        text = sanitise_text(" ".join(w["text"] for w in line_words))
        if not text:
            continue
        sizes = [float(w["size"]) for w in line_words if w.get("size")]
        result.append(
            {
                "text": text,
                "words": line_words,
                "top": line_words[0].get("top", 0),
                "x0": line_words[0].get("x0", 0),
                "size": statistics.median(sizes) if sizes else 12.0,
            }
        )
    result.sort(key=lambda ln: ln["top"])
    return result


def _is_title_line(text: str) -> bool:
    t = text.strip()
    if len(t) > 85:
        return False
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio > 0.75 or t.isupper()


def _is_continuation(prev: dict, curr: dict) -> bool:
    pt, ct = prev["text"].strip(), curr["text"].strip()
    if not ct:
        return False
    # Table-like rows (e.g. "1 m = 100 cm = ...") should not be merged
    # into a single long paragraph; keep them as separate lines/blocks.
    if "=" in pt and "=" in ct:
        return False
    if _BULLET_START.match(ct) or _ORDERED_START.match(ct) or _SUB_BULLET.match(ct):
        return False
    if re.match(r"^\[[\sXx]?\]", ct):
        return False
    if _SECTION_INLINE.match(ct):
        return False
    if _is_title_line(pt) and len(ct) > 30:
        return False
    if re.match(r"^(This|In|The|Any|Whereas|Date)\b", ct):
        if _is_title_line(pt) or not pt.endswith((".", "?", "!")):
            return False
    if prev.get("size") and curr.get("size"):
        if curr["size"] >= prev["size"] * 1.12 and len(ct) < 85:
            return False
        if prev["size"] >= curr["size"] * 1.12 and len(pt) < 85:
            return False
    if _DATE_RANGE.search(ct) and len(ct) < 55:
        return False
    if pt.endswith((".", "?", "!")) and ct[0].isupper():
        if len(ct) < 100:
            return False
    if pt.endswith(":") and re.match(r"^[A-Z][A-Za-z /&\-]+\.", ct):
        return False
    if re.search(r";\s*$", pt) and re.match(r"^Chapter\s+\d+", ct, re.I):
        return False
    if re.search(r",\s*\d", pt) and re.match(r"^[A-Z]", ct):
        return False
    if re.match(r'^(Date|Effective|Provider|Client)\b', ct, re.I):
        return True
    if "(" in pt and ")" not in pt:
        return True
    if pt.endswith(("(", "“", '"')) or re.search(r"\(\s*$", pt):
        return True
    if ct[0].islower():
        return True
    if not pt.endswith((".", "?", "!", ":", ";")):
        return True
    if curr["x0"] > prev["x0"] + 12 and len(ct) < 120:
        return True
    return False


def _should_join_paragraphs(prev_text: str, next_text: str) -> bool:
    pt, nt = prev_text.strip(), next_text.strip()
    if not pt or not nt:
        return False
    # Avoid joining adjacent table-like rows.
    if "=" in pt and "=" in nt:
        return False
    if pt.count("(") > pt.count(")"):
        return True
    if re.match(r"^Date\)", nt):
        return True
    if not pt.endswith((".", "?", "!", ":", ";")) and nt[0].islower():
        return True
    if not pt.endswith((".", "?", "!", ":", ";")) and re.match(r'^["“(]', nt):
        return True
    return False


def _join_broken_paragraphs(paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join paragraphs split by layout gaps mid-sentence."""
    if not paragraphs:
        return []
    out: list[dict[str, Any]] = []
    buf = dict(paragraphs[0])
    for para in paragraphs[1:]:
        if _should_join_paragraphs(buf["text"], para["text"]):
            buf["text"] = f"{buf['text']} {para['text']}"
            buf["size"] = max(buf["size"], para["size"])
            buf["words"] = buf.get("words", []) + para.get("words", [])
        else:
            out.append(buf)
            buf = dict(para)
    out.append(buf)
    return out


def _merge_lines_to_paragraphs(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    buf: Optional[dict[str, Any]] = None
    for line in lines:
        text = line["text"].strip()
        if not text:
            if buf:
                merged.append(buf)
                buf = None
            continue
        if buf is None:
            buf = dict(line)
            continue
        if _is_continuation(buf, line):
            buf["text"] = f"{buf['text']} {text}"
            buf["size"] = max(buf["size"], line["size"])
            buf["words"] = buf.get("words", []) + line.get("words", [])
        else:
            merged.append(buf)
            buf = dict(line)
    if buf:
        merged.append(buf)
    return merged


def _split_inline_bullets(text: str) -> list[tuple[str, str]]:
    """Split on ● • ○ ■ mid-paragraph."""
    if not re.search(r"[●•○■]", text):
        return [("paragraph", text)]
    parts = re.split(r"\s*(?<=[.;:])\s*(?=[●•○■])|(?<=\s)[●•○■]\s*", text)
    out: list[tuple[str, str]] = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        part = re.sub(r"^[●•○■]\s*", "", part)
        if not part:
            continue
        role = "list_item" if i > 0 or _BULLET_START.match(text) else "paragraph"
        if _BULLET_START.match(text) and i == 0:
            role = "list_item"
        elif i > 0:
            role = "list_item"
        out.append((role, part))
    if not out:
        return [("paragraph", text)]
    return out


def _split_legal_sections(text: str) -> list[tuple[str, str]]:
    """Split 'Scope of Services. The Client...' into heading + body."""
    m = _SECTION_INLINE.match(text.strip())
    if m:
        title, body = m.group(1).strip(), m.group(2).strip()
        return [("h2", title + "."), ("paragraph", body)]
    return [("paragraph", text)]


def _classify_paragraph(
    text: str,
    font_size: float,
    avg_font: float,
    *,
    is_first: bool = False,
) -> str:
    stripped = text.strip()
    if not stripped:
        return "blank"
    if stripped.upper() in _SECTION_LABELS or stripped.upper().startswith("PROFESSIONAL "):
        return "h2"
    if _is_title_line(stripped) and len(stripped) < 70:
        return "h1"
    if _BULLET_START.match(stripped) or _SUB_BULLET.match(stripped):
        return "list_item"
    if _ORDERED_START.match(stripped):
        return "list_item"
    if re.match(r"^\[[\sXx]?\]", stripped):
        return "list_item"

    ratio = font_size / avg_font if avg_font else 1.0

    if is_first and ratio >= 1.35 and len(stripped) < 100:
        return "h1"
    if ratio >= 1.45 and len(stripped) < 90:
        return "h2"
    if ratio >= 1.35 and len(stripped) < 70:
        return "h3"
    if ratio >= 1.28 and len(stripped) < 55:
        return "h4"
    if ratio >= 1.22 and len(stripped) < 45:
        return "h5"
    if ratio >= 1.18 and len(stripped) < 40:
        return "h6"
    if ratio >= 1.25 and len(stripped) < 70 and not _EMAIL.search(stripped):
        if stripped.isupper() or re.match(r"^[A-Z][A-Za-z]+(\s+[A-Z][A-Za-z]+){0,4}$", stripped):
            return "h2"
        return "h3"
    if len(stripped) < 55 and stripped.isupper() and " " in stripped:
        return "h2"
    if len(stripped) < 50 and re.match(
        r"^[A-Z][A-Za-z0-9\-]+(\s+[A-Za-z0-9\-]+){0,5}$", stripped
    ):
        if not _DATE_RANGE.search(stripped):
            if not re.search(
                r"\b(Developer|Engineer|Manager|Analyst|Designer|Writer|Tester|contract|Present)\b",
                stripped,
                re.I,
            ):
                return "h3"
    return "paragraph"


def _split_document_title(text: str) -> list[tuple[str, str]]:
    m = re.match(
        r"^([A-Z][A-Za-z0-9\s&/\-]{2,60}?)\s+((?:This|In|The|Any|Whereas)\b.+)$",
        text.strip(),
        re.DOTALL,
    )
    if m:
        return [("h1", m.group(1).strip()), ("paragraph", m.group(2).strip())]
    return [("paragraph", text)]


def _split_resume_header(text: str) -> list[tuple[str, str]]:
    upper = text.upper()
    if " SKILLS" not in upper:
        return [("paragraph", text)]
    idx = upper.find(" SKILLS")
    before = text[:idx].strip()
    rest = text[idx:].strip()
    parts: list[tuple[str, str]] = []
    if before:
        em = _EMAIL.search(before)
        if em:
            name = before[: em.start()].strip()
            email_part = before[em.start() :].strip()
            if name:
                parts.append(("h1", name))
            if email_part:
                parts.append(("paragraph", email_part))
        else:
            parts.append(("h1", before))
    if rest.upper().startswith("SKILLS"):
        skill_body = rest[6:].strip()
        parts.append(("h2", "SKILLS"))
        if skill_body:
            parts.extend(_split_inline_bullets(skill_body))
    return parts or [("paragraph", text)]


def _build_text_block(
    text: str,
    role: str,
    words: list[dict] | None,
    *,
    font_size: float = 12.0,
    bbox=None,
) -> TextBlock:
    spans = spans_from_words(words) if words else []
    plain = plain_text_from_spans(spans) if spans else sanitise_text(text)
    if not plain:
        return None  # type: ignore[return-value]
    mono = words and all(
        "mono" in (w.get("fontname") or "").lower()
        or "courier" in (w.get("fontname") or "").lower()
        for w in words[:3]
    )
    if mono and role == "paragraph":
        role = "code_block"
    return TextBlock(
        text=plain,
        role=role,
        bbox=bbox,
        font_size=font_size,
        spans=spans,
    )


def _expand_paragraph_to_blocks(
    para: dict[str, Any],
    avg_font: float,
    *,
    is_first: bool = False,
) -> list[TextBlock]:
    text = re.sub(r"\s+", " ", para["text"]).strip()
    size = para["size"]

    if is_first and "SKILLS" in text.upper() and _EMAIL.search(text):
        chunks = _split_resume_header(text)
    elif is_first and re.match(r"^[A-Z][A-Z\s]{3,50}\s+This\b", text):
        chunks = _split_document_title(text)
    else:
        base_role = _classify_paragraph(text, size, avg_font, is_first=is_first)
        chunks = []
        if base_role == "paragraph":
            for part in _split_legal_sections(text):
                if part[0] == "h2":
                    chunks.append(part)
                else:
                    chunks.extend(_split_inline_bullets(part[1]))
        elif base_role == "list_item":
            text = _BULLET_START.sub("", text)
            text = _SUB_BULLET.sub("", text)
            chunks = [("list_item", text.strip())]
        else:
            chunks = [(base_role, text)]

    words = para.get("words") or []
    blocks: list[TextBlock] = []
    for role, chunk in chunks:
        chunk = sanitise_text(re.sub(r"^[●•○■]\s*", "", chunk))
        if not chunk:
            continue
        if role == "paragraph" and re.search(r"[●•]", chunk):
            for sub_role, sub in _split_inline_bullets(chunk):
                sub = sanitise_text(re.sub(r"^[●•○■]\s*", "", sub))
                if sub:
                    blk = _build_text_block(sub, sub_role, None, font_size=size)
                    if blk:
                        blocks.append(blk)
            continue
        blk = _build_text_block(chunk, role, words if len(chunks) == 1 else None, font_size=size)
        if blk:
            blocks.append(blk)
    return blocks


def _split_section_headings(blocks: list[TextBlock]) -> list[TextBlock]:
    """Split merged section + company lines (e.g. 'Professional Experience Foo')."""
    out: list[TextBlock] = []
    for block in blocks:
        if block.role not in ("h2", "h3", "paragraph"):
            out.append(block)
            continue
        text = block.text
        m = re.match(
            r"^(Professional Experience|Education|Projects|Work Experience)\s+(.+)$",
            text,
            re.I,
        )
        if m:
            out.append(TextBlock(text=m.group(1), role="h2", bbox=block.bbox, font_size=block.font_size))
            rest = m.group(2).strip()
            if rest:
                out.append(
                    TextBlock(text=rest, role="h3", bbox=block.bbox, font_size=block.font_size)
                )
            continue
        if block.role == "paragraph" and _DATE_RANGE.search(text):
            m2 = re.match(r"^(.+?)\s+((?:Jan|Feb|Mar).+)$", text, re.I | re.DOTALL)
            if m2 and len(m2.group(1)) < 80:
                title_part = m2.group(1).strip()
                date_part = m2.group(2).strip()
                title_role = "h3" if len(title_part) < 40 and "-" in title_part else "paragraph"
                if re.search(r"\b(Developer|Engineer|Manager|Writer|Tester)\b", title_part, re.I):
                    title_role = "paragraph"
                out.append(
                    TextBlock(
                        text=title_part, role=title_role, bbox=block.bbox, font_size=block.font_size
                    )
                )
                out.append(
                    TextBlock(
                        text=f"*{date_part}*", role="paragraph", bbox=block.bbox, font_size=block.font_size
                    )
                )
                continue
        out.append(block)
    return out


_REFERENCE_LABELS = frozenset(
    {
        "Length",
        "Area",
        "Volume",
        "Time",
        "Angle",
        "Speed",
        "Acceleration",
        "Mass",
        "Force",
        "Pressure",
        "Energy",
        "Power",
        "Mass–Energy Equivalence",
        "Mass-Energy Equivalence",
    }
)

_INDEX_HEADER_RE = re.compile(r"^(?:Index|I-\d+)$", re.I)


def _role_for_dense_line(text: str, font_size: float, avg_font: float) -> str:
    stripped = text.strip()
    if not stripped:
        return "blank"
    if stripped in _REFERENCE_LABELS:
        return "h3"
    if _INDEX_HEADER_RE.match(stripped):
        return "h3"
    if len(stripped) <= 2 and stripped.isalpha() and stripped.isupper():
        return "h3"
    return _classify_paragraph(stripped, font_size, avg_font)


def _extract_line_blocks(
    words: list[dict],
    *,
    page_index: int,
    is_document_start: bool,
) -> list[TextBlock]:
    """One block per visual line (factor sheets, dense reference pages)."""
    font_sizes = [float(w["size"]) for w in words if w.get("size")]
    avg_font = statistics.mean(font_sizes) if font_sizes else 12.0
    lines = _group_words_into_lines(words)
    blocks: list[TextBlock] = []
    for i, line in enumerate(lines):
        text = sanitise_text(line["text"]).strip()
        if not text:
            continue
        role = _role_for_dense_line(text, line["size"], avg_font)
        if i == 0 and is_document_start and role == "paragraph":
            role = _classify_paragraph(text, line["size"], avg_font, is_first=True)
        blk = _build_text_block(
            text, role, line.get("words"), font_size=line["size"]
        )
        if blk:
            blocks.append(blk)
    return blocks


def _extract_index_column_words(
    words: list[dict],
    *,
    page_index: int,
    is_document_start: bool,
) -> list[TextBlock]:
    """Index column: preserve one entry per line, minimal merging."""
    return _extract_line_blocks(
        words, page_index=page_index, is_document_start=is_document_start
    )


def _extract_column_words(
    words: list[dict],
    *,
    page_index: int,
    is_document_start: bool,
) -> list[TextBlock]:
    """Single-column flow inside a page or column slice."""
    font_sizes = [float(w["size"]) for w in words if w.get("size")]
    avg_font = statistics.mean(font_sizes) if font_sizes else 12.0

    lines = _group_words_into_lines(words)
    if not lines:
        return []

    paragraphs = _join_broken_paragraphs(_merge_lines_to_paragraphs(lines))
    blocks: list[TextBlock] = []
    for i, para in enumerate(paragraphs):
        blocks.extend(
            _expand_paragraph_to_blocks(
                para, avg_font, is_first=(i == 0 and is_document_start)
            )
        )
    return blocks


def extract_blocks_from_layout(
    page,
    words: list[dict],
    *,
    page_index: int = 0,
    book_mode: bool = False,
) -> list[TextBlock]:
    """
    Primary structure extraction: lines → merged paragraphs → classified blocks.
  In book_mode: TOC pages, multi-column infographic pages handled separately.
    """
    if not words:
        raw = sanitise_text(page.extract_text(layout=True) or "")
        if not raw:
            return []
        return [
            TextBlock(text=raw, role="paragraph", bbox=None, font_size=12.0),
        ]

    if book_mode and is_toc_page(page, words):
        toc_blocks = extract_toc_blocks(page)
        if toc_blocks:
            return toc_blocks

    page_width = float(getattr(page, "width", 0) or 612)
    raw_layout = page_text_hint(page, words)
    index_page = is_index_page(raw_layout)
    factor_page = is_factor_sheet_page(raw_layout)
    photo_page = is_photo_credits_page(raw_layout)

    use_multi = book_mode or is_multi_column_page(
        words, page_width, min_words_per_col=60
    )

    if use_multi and (
        index_page
        or factor_page
        or photo_page
        or is_multi_column_page(words, page_width, min_words_per_col=50)
    ):
        all_blocks: list[TextBlock] = []
        if index_page and count_substantial_thirds(words, page_width) >= 3:
            columns = split_words_by_page_regions(words, page_width, 3)
            extract_fn = _extract_index_column_words
        else:
            columns = split_two_column_body(words, page_width)
            if columns is None:
                columns = split_words_by_columns(
                    words, page_width, min_words_per_col=25
                )
            if factor_page or index_page:
                extract_fn = _extract_line_blocks if factor_page else _extract_index_column_words
            else:
                extract_fn = _extract_column_words

        for col_idx, col_words in enumerate(columns):
            if len(col_words) < 15:
                continue
            col_blocks = extract_fn(
                col_words,
                page_index=page_index,
                is_document_start=(page_index == 0 and col_idx == 0),
            )
            if not col_blocks:
                continue
            for b in col_blocks:
                b.meta["column"] = col_idx
            all_blocks.extend(col_blocks)
        return _split_section_headings(all_blocks)

    blocks = _extract_column_words(
        words, page_index=page_index, is_document_start=(page_index == 0)
    )
    return _split_section_headings(blocks)

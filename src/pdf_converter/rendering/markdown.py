"""Markdown renderer from PageContent."""

from __future__ import annotations

import re

from pdf_converter.models import PageContent, TextBlock
from pdf_converter.rendering.document import (
    heading_markdown_prefix,
    iter_render_segments,
    normalize_markdown,
    page_column_indices,
)
from pdf_converter.rendering.rich_text import block_inline_markdown


def _cell(val) -> str:
    if val is None:
        return ""
    return str(val).replace("|", "\\|").replace("\n", " ").strip()


def _table_to_markdown(table: list) -> str:
    if not table or not table[0]:
        return ""
    col_count = max(len(row) for row in table)
    padded = [row + [None] * (col_count - len(row)) for row in table]
    lines = [
        "",
        "| " + " | ".join(_cell(c) for c in padded[0]) + " |",
        "| " + " | ".join(["---"] * col_count) + " |",
    ]
    for row in padded[1:]:
        lines.append("| " + " | ".join(_cell(c) for c in row) + " |")
    lines.append("")
    return "\n".join(lines)


def _list_item_markdown(block: TextBlock) -> str:
    text = block.text.strip()
    body = block_inline_markdown(block) if block.spans else re.sub(
        r"^[\u2022\u2023\u25E6\u2043\*\-\+•○■]\s*", "", text
    )
    m = re.match(r"^(\d+[\.\)])\s+", text)
    if m:
        return f"{m.group(1)} {body}"
    return f"- {body}"


def _list_group_markdown(blocks: list[TextBlock]) -> str:
    return "\n".join(_list_item_markdown(b) for b in blocks)


def _toc_chapter_markdown(block: TextBlock) -> str:
    page = block.meta.get("page", "")
    title = block_inline_markdown(block) if block.spans else block.text.strip()
    if page:
        return f"**{title}** — {page}"
    return f"**{title}**"


def _toc_item_markdown(block: TextBlock) -> str:
    page = block.meta.get("page", "")
    title = block_inline_markdown(block) if block.spans else block.text.strip()
    if page:
        return f"- {title} — {page}"
    return f"- {title}"


def _append_segments(
    parts: list[str],
    page: PageContent,
    *,
    page_breaks: bool,
) -> None:
    for kind, payload in iter_render_segments([page], page_breaks=page_breaks):
        if kind == "page_break":
            parts.append(f"\n\n---\n\n*Page {payload}*\n\n")
        elif kind == "heading" and isinstance(payload, TextBlock):
            prefix = heading_markdown_prefix(payload.role)
            line = f"{prefix}{block_inline_markdown(payload)}"
            parts.append(f"\n{line}\n")
        elif kind == "list_group" and isinstance(payload, list):
            parts.append("\n" + _list_group_markdown(payload).strip() + "\n")
        elif kind == "toc_chapter" and isinstance(payload, TextBlock):
            parts.append(f"\n{_toc_chapter_markdown(payload)}\n")
        elif kind == "toc_item" and isinstance(payload, TextBlock):
            parts.append(f"{_toc_item_markdown(payload)}\n")
        elif kind == "blockquote" and isinstance(payload, TextBlock):
            body = block_inline_markdown(payload)
            parts.append("\n" + "\n".join(f"> {ln}" for ln in body.split("\n")) + "\n")
        elif kind == "code_block" and isinstance(payload, TextBlock):
            parts.append(f"\n```\n{payload.text}\n```\n")
        elif kind == "footnote" and isinstance(payload, TextBlock):
            parts.append(f"\n> {block_inline_markdown(payload)}\n")
        elif kind == "caption" and isinstance(payload, TextBlock):
            parts.append(f"\n*{block_inline_markdown(payload)}*\n")
        elif kind == "hr":
            parts.append("\n---\n")
        elif kind == "paragraph" and isinstance(payload, TextBlock):
            body = block_inline_markdown(payload)
            if (
                payload.text.startswith("*")
                and payload.text.endswith("*")
                and not payload.spans
            ):
                parts.append(f"\n{body}\n")
            else:
                parts.append(f"\n{body}\n")
        elif kind == "table" and payload is not None:
            parts.append(_table_to_markdown(payload))


def pages_to_markdown(
    pages: list[PageContent],
    image_dir: str = "images",
    *,
    page_breaks: bool = False,
) -> tuple[str, dict[str, bytes]]:
    """Convert PageContent list to editor-friendly Markdown."""
    parts: list[str] = []
    image_files: dict[str, bytes] = {}
    img_counter = 0

    for page in pages:
        if page.mode == "ocr":
            for img in page.images:
                if img.is_full_page:
                    fname = f"{image_dir}/page_{page.page_num + 1}_scan.png"
                    image_files[fname] = img.data
                    parts.append(f"\n![Scanned page {page.page_num + 1}]({fname})\n")

        columns = page_column_indices(page)
        if len(columns) >= 2 and not page.tables:
            for col in columns[:3]:
                parts.append(f"\n<!-- column {col + 1} -->\n")
                col_blocks = [
                    b for b in page.text_blocks if b.meta.get("column") == col
                ]
                col_page = PageContent(
                    page_num=page.page_num,
                    mode=page.mode,
                    text_blocks=col_blocks,
                    tables=[],
                    images=[],
                    raw_text=page.raw_text,
                    stats=page.stats,
                )
                _append_segments(parts, col_page, page_breaks=page_breaks)
        else:
            _append_segments(parts, page, page_breaks=page_breaks)

        for img in page.images:
            if img.is_full_page:
                continue
            img_counter += 1
            fname = f"{image_dir}/figure_{page.page_num + 1}_{img.index + 1}.{img.ext}"
            image_files[fname] = img.data
            parts.append(f"\n![Figure {img_counter}]({fname})\n")

    return normalize_markdown("\n".join(parts)), image_files

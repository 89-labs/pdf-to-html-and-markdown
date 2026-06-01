"""Shared document rendering helpers."""

from __future__ import annotations

import re
from typing import Iterator, Union

from pdf_converter.models import PageContent, TextBlock

_HEADING_PREFIX = {
    "h1": "# ",
    "h2": "## ",
    "h3": "### ",
    "h4": "#### ",
    "h5": "##### ",
    "h6": "###### ",
}


def heading_markdown_prefix(role: str) -> str:
    return _HEADING_PREFIX.get(role, "## ")


def iter_render_segments(
    pages: list[PageContent],
    *,
    page_breaks: bool = False,
) -> Iterator[tuple[str, Union[TextBlock, list[TextBlock], int, object]]]:
    """Yield (kind, payload) for markdown/HTML renderers.

    Payload types:
    - TextBlock for heading, paragraph, blockquote, code_block, footnote, caption
    - list[TextBlock] for list_group
    - int for page_break page number
    - table rows for table
    """
    for page in pages:
        if page_breaks and page.page_num > 0:
            yield ("page_break", page.page_num + 1)

        pending_list: list[TextBlock] = []

        def flush_list() -> Iterator[tuple[str, list[TextBlock]]]:
            nonlocal pending_list
            if pending_list:
                batch = pending_list
                pending_list = []
                yield ("list_group", batch)

        for block in page.text_blocks:
            role = block.role
            text = block.text.strip()
            if not text and role != "hr":
                continue

            if role == "list_item":
                yield from flush_list()
                pending_list.append(block)
                continue

            yield from flush_list()

            if role in _HEADING_PREFIX:
                yield ("heading", block)
            elif role == "blockquote":
                yield ("blockquote", block)
            elif role == "code_block":
                yield ("code_block", block)
            elif role == "footnote":
                yield ("footnote", block)
            elif role == "caption":
                yield ("caption", block)
            elif role == "hr":
                yield ("hr", block)
            else:
                yield ("paragraph", block)

        yield from flush_list()

        for table in page.tables:
            yield ("table", table)


def normalize_markdown(text: str) -> str:
    """Collapse excessive blank lines while keeping structure."""
    text = re.sub(r"\n{4,}", "\n\n", text)
    text = re.sub(r"([^\n])\n(#{1,6}\s)", r"\1\n\n\2", text)
    while re.search(r"^(- .+)\n\n(- )", text, re.MULTILINE):
        text = re.sub(r"^(- .+)\n\n(- )", r"\1\n\2", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"

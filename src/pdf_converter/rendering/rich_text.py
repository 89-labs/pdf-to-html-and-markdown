"""Render inline spans to HTML and Markdown."""

from __future__ import annotations

import html
import re
from urllib.parse import quote

from pdf_converter.models import TextBlock, TextSpan


def spans_to_html(spans: list[TextSpan]) -> str:
    if not spans:
        return ""
    parts: list[str] = []
    for span in spans:
        text = html.escape(span.text)
        if not text:
            continue
        if span.superscript:
            text = f"<sup>{text}</sup>"
        elif span.subscript:
            text = f"<sub>{text}</sub>"
        if span.code:
            text = f"<code>{text}</code>"
        if span.bold and span.italic:
            text = f"<strong><em>{text}</em></strong>"
        elif span.bold:
            text = f"<strong>{text}</strong>"
        elif span.italic:
            text = f"<em>{text}</em>"
        if span.underline:
            text = f"<u>{text}</u>"
        if span.strikethrough:
            text = f"<del>{text}</del>"
        if span.link:
            href = html.escape(span.link, quote=True)
            text = f'<a href="{href}">{text}</a>'
        styles: list[str] = []
        if span.color:
            styles.append(f"color:{span.color}")
        if span.background:
            styles.append(f"background:{span.background}")
        if span.small:
            styles.append("font-size:0.85em")
        if styles:
            text = f'<span style="{";".join(styles)}">{text}</span>'
        parts.append(text)
    return "".join(parts)


def _escape_md(text: str) -> str:
    return re.sub(r"([\\`*_{}[\]()#+\-.!|>])", r"\\\1", text)


def spans_to_markdown(spans: list[TextSpan]) -> str:
    if not spans:
        return ""
    parts: list[str] = []
    for span in spans:
        text = span.text
        if not text:
            continue
        core = text
        if span.code:
            core = f"`{core}`"
        else:
            if span.bold and span.italic:
                core = f"***{core}***"
            elif span.bold:
                core = f"**{core}**"
            elif span.italic:
                core = f"*{core}*"
            if span.strikethrough:
                core = f"~~{core}~~"
            if span.link:
                core = f"[{core}]({span.link})"
        parts.append(core)
    return "".join(parts)


def block_inline_html(block: TextBlock) -> str:
    if block.spans:
        return spans_to_html(block.spans)
    return html.escape(block.text)


def block_inline_markdown(block: TextBlock) -> str:
    if block.spans:
        return spans_to_markdown(block.spans)
    return block.text

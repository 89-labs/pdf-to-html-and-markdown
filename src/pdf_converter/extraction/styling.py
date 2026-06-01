"""Inline style detection from PDF words and characters."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Optional

from pdf_converter.models import TextSpan

_BOLD_RE = re.compile(r"bold|black|heavy|semibold|demi", re.I)
_ITALIC_RE = re.compile(r"italic|oblique", re.I)
_MONO_RE = re.compile(r"mono|courier|consolas|menlo|code|typewriter", re.I)
_SMALL_SIZE_RATIO = 0.82
_SUPERSCRIPT_RATIO = 0.75
_SUBSCRIPT_RATIO = 0.75
_SUPERSCRIPT_Y_OFFSET = 2.5


@dataclass
class WordStyle:
    bold: bool = False
    italic: bool = False
    code: bool = False
    superscript: bool = False
    subscript: bool = False
    underline: bool = False
    strikethrough: bool = False
    link: Optional[str] = None
    color: Optional[str] = None
    background: Optional[str] = None
    font_size: Optional[float] = None
    small: bool = False


def _color_to_hex(color: Any) -> Optional[str]:
    if not color or not isinstance(color, (tuple, list)):
        return None
    if len(color) >= 3:
        r, g, b = color[0], color[1], color[2]
        if all(0 <= v <= 1 for v in (r, g, b)):
            return "#{:02x}{:02x}{:02x}".format(
                int(r * 255), int(g * 255), int(b * 255)
            )
    return None


def _is_highlight_bg(color: Any) -> bool:
    hex_c = _color_to_hex(color)
    if not hex_c:
        return False
    r = int(hex_c[1:3], 16)
    g = int(hex_c[3:5], 16)
    b = int(hex_c[5:7], 16)
    return r > 200 and g > 200 and b < 180


def style_from_fontname(fontname: str) -> tuple[bool, bool, bool]:
    fn = fontname or ""
    bold = bool(_BOLD_RE.search(fn))
    italic = bool(_ITALIC_RE.search(fn))
    code = bool(_MONO_RE.search(fn))
    return bold, italic, code


def word_style(
    word: dict,
    *,
    line_median_size: float,
    line_baseline_top: float,
) -> WordStyle:
    fontname = word.get("fontname") or ""
    size = float(word.get("size") or line_median_size or 12)
    bold, italic, code = style_from_fontname(fontname)

    top = float(word.get("top", 0))
    y_offset = line_baseline_top - top
    superscript = size < line_median_size * _SUPERSCRIPT_RATIO and y_offset > _SUPERSCRIPT_Y_OFFSET
    subscript = size < line_median_size * _SUBSCRIPT_RATIO and y_offset < -1.5
    small = size < line_median_size * _SMALL_SIZE_RATIO and not superscript and not subscript

    fg = _color_to_hex(word.get("non_stroking_color"))
    bg = _color_to_hex(word.get("stroking_color"))
    background = bg if _is_highlight_bg(word.get("stroking_color")) else None
    if fg in ("#000000", "#00000000") or fg is None:
        fg = None

    return WordStyle(
        bold=bold,
        italic=italic,
        code=code,
        superscript=superscript,
        subscript=subscript,
        small=small,
        link=word.get("uri"),
        color=fg,
        background=background,
        font_size=size,
    )


def _style_key(ws: WordStyle) -> tuple:
    return (
        ws.bold,
        ws.italic,
        ws.code,
        ws.superscript,
        ws.subscript,
        ws.underline,
        ws.strikethrough,
        ws.link,
        ws.color,
        ws.background,
        round(ws.font_size or 0, 1) if ws.small else None,
    )


def spans_from_words(
    words: list[dict],
    *,
    line_median_size: Optional[float] = None,
) -> list[TextSpan]:
    """Merge styled words into inline spans."""
    if not words:
        return []

    sizes = [float(w.get("size") or 12) for w in words if w.get("size")]
    median = line_median_size or (sorted(sizes)[len(sizes) // 2] if sizes else 12.0)
    baseline_top = float(words[0].get("top", 0))

    spans: list[TextSpan] = []
    current: Optional[TextSpan] = None
    current_key = None

    for i, w in enumerate(words):
        text = w.get("text") or ""
        if not text:
            continue
        ws = word_style(w, line_median_size=median, line_baseline_top=baseline_top)
        key = _style_key(ws)

        if i > 0 and not text.startswith(" ") and current:
            prev = words[i - 1].get("text", "")
            if prev and not prev.endswith(" "):
                text = " " + text

        span = TextSpan(
            text=text,
            bold=ws.bold,
            italic=ws.italic,
            code=ws.code,
            superscript=ws.superscript,
            subscript=ws.subscript,
            underline=ws.underline,
            strikethrough=ws.strikethrough,
            link=ws.link,
            color=ws.color,
            background=ws.background,
            font_size=ws.font_size,
            small=ws.small,
        )

        if current and key == current_key:
            current = replace(current, text=current.text + text)
        else:
            if current:
                spans.append(current)
            current = span
            current_key = key

    if current and current.text.strip():
        spans.append(current)
    return spans


def plain_text_from_spans(spans: list[TextSpan]) -> str:
    return "".join(s.text for s in spans).strip()

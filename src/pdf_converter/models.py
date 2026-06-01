"""Data models for conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


PIPELINE_VERSION = "1.4.0"
ENGINE_PDFPLUMBER = "pdfplumber"
ENGINE_MARKER = "marker"


@dataclass
class TextSpan:
    """Inline run with formatting preserved from PDF."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    superscript: bool = False
    subscript: bool = False
    code: bool = False
    link: Optional[str] = None
    color: Optional[str] = None
    background: Optional[str] = None
    font_size: Optional[float] = None
    small: bool = False


@dataclass
class TextBlock:
    text: str
    role: str  # h1-h6, paragraph, list_item, footnote, blockquote, code_block, caption, hr, blank
    bbox: Optional[tuple[float, float, float, float]] = None
    font_size: float = 12.0
    spans: list[TextSpan] = field(default_factory=list)
    list_level: int = 0
    ordered: bool = False
    meta: dict = field(default_factory=dict)


@dataclass
class PageImage:
    data: bytes
    ext: str
    bbox: Optional[tuple[float, float, float, float]] = None
    index: int = 0
    is_full_page: bool = False


@dataclass
class PageStats:
    page_num: int
    mode: str  # native | ocr
    char_count: int = 0
    word_count: int = 0
    table_count: int = 0
    image_count: int = 0
    ocr_mean_confidence: Optional[float] = None


@dataclass
class PageContent:
    page_num: int
    mode: str
    text_blocks: list[TextBlock] = field(default_factory=list)
    tables: list[list[list[Optional[str]]]] = field(default_factory=list)
    images: list[PageImage] = field(default_factory=list)
    raw_text: str = ""
    stats: Optional[PageStats] = None


@dataclass
class ConversionResult:
    input_path: str
    input_sha256: str
    page_count: int
    engine: str = ENGINE_PDFPLUMBER
    pipeline_version: str = PIPELINE_VERSION
    status: str = "success"  # success | failed | needs_review
    markdown: Optional[str] = None
    html: Optional[str] = None
    image_files: dict[str, bytes] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    page_stats: list[PageStats] = field(default_factory=list)
    coverage_ratio: Optional[float] = None
    elapsed_seconds: float = 0.0
    output_sha256: dict[str, str] = field(default_factory=dict)

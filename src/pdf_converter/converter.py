"""Main PDF conversion orchestrator."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Literal, Optional

from pypdf import PdfReader

from pdf_converter.extraction.marker import extract_with_marker
from pdf_converter.extraction.pipeline import extract_document
from pdf_converter.models import (
    ENGINE_MARKER,
    ENGINE_PDFPLUMBER,
    PIPELINE_VERSION,
    ConversionResult,
    PageStats,
)
from pdf_converter.rendering.html import pages_to_html
from pdf_converter.rendering.markdown import pages_to_markdown
from pdf_converter.validation import (
    compute_coverage_ratio,
    has_critical,
    issues_to_strings,
    validate_output,
)

log = logging.getLogger(__name__)

OutputFormat = Literal["markdown", "html", "both"]


class ConversionError(Exception):
    """Raised when conversion fails validation in strict mode."""

    def __init__(self, message: str, result: ConversionResult):
        super().__init__(message)
        self.result = result


class PDFConverter:
    """
    PDF → Markdown / HTML converter.

    Strategy:
      - prefer_marker=True: try Marker once per job (markdown renderer);
        if it succeeds, use Marker output for markdown; still use pdfplumber
        IR for HTML unless Marker-only path is extended.
      - For consistency with --format both: always extract once via pdfplumber
        pipeline and render both formats from the same PageContent IR.
      - Marker can be used as optional override for markdown-only jobs.

    Default (best practice): single pdfplumber extraction → both formats.
    """

    def __init__(
        self,
        prefer_marker: bool = False,
        embed_images: bool = True,
        strict: bool = True,
        min_coverage: float = 0.5,
        prose_mode: bool = False,
        allow_text_tables: bool = False,
        page_breaks: bool = False,
        book_mode: bool = False,
    ):
        self.prefer_marker = prefer_marker
        self.embed_images = embed_images
        self.strict = strict
        self.min_coverage = min_coverage
        self.prose_mode = prose_mode
        self.allow_text_tables = allow_text_tables
        self.page_breaks = page_breaks
        self.book_mode = book_mode

    def convert(
        self,
        pdf_path: str,
        output_format: OutputFormat = "both",
        image_dir: str = "images",
        marker_markdown_only: bool = True,
    ) -> ConversionResult:
        """
        Convert PDF to requested format(s).

        When output_format is 'both', both outputs always come from the same
        pdfplumber extraction (canonical IR) unless marker_markdown_only=False.
        """
        pdf_path = str(Path(pdf_path).resolve())
        start = time.time()

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        with open(pdf_path, "rb") as f:
            raw = f.read()
        input_sha256 = hashlib.sha256(raw).hexdigest()

        reader = PdfReader(pdf_path)
        page_count = len(reader.pages)
        meta = reader.metadata
        title = Path(pdf_path).stem
        if meta and getattr(meta, "title", None):
            title = str(meta.title)

        log.info("Converting: %s (%s pages)", Path(pdf_path).name, page_count)
        log.info("  SHA-256: %s...", input_sha256[:16])

        result = ConversionResult(
            input_path=pdf_path,
            input_sha256=input_sha256,
            page_count=page_count,
            pipeline_version=PIPELINE_VERSION,
            metadata={
                "title": title,
                "author": getattr(meta, "author", None),
                "pages": page_count,
            },
        )

        formats = (
            ["markdown", "html"]
            if output_format == "both"
            else [output_format]
        )

        # Single canonical extraction for both formats (consistent outputs)
        pages = extract_document(
            pdf_path,
            prose_mode=self.prose_mode,
            allow_text_tables=self.allow_text_tables,
            book_mode=self.book_mode,
        )
        result.engine = ENGINE_PDFPLUMBER
        result.page_stats = [p.stats for p in pages if p.stats]

        marker_used_for_md = False
        if (
            self.prefer_marker
            and "markdown" in formats
            and marker_markdown_only
            and output_format != "both"
        ):
            marker_result = extract_with_marker(pdf_path, "markdown")
            if marker_result:
                content, img_files, meta_extra = marker_result
                result.markdown = content
                result.image_files.update(img_files)
                result.metadata.update(meta_extra or {})
                result.engine = ENGINE_MARKER
                marker_used_for_md = True

        if not marker_used_for_md:
            if "markdown" in formats:
                md, img_md = pages_to_markdown(
                    pages, image_dir=image_dir, page_breaks=self.page_breaks
                )
                result.markdown = md
                result.image_files.update(img_md)

            if "html" in formats:
                html_out, img_html = pages_to_html(
                    pages,
                    title=title,
                    embed_images=self.embed_images,
                    image_dir=image_dir,
                    page_breaks=self.page_breaks,
                )
                result.html = html_out
                result.image_files.update(img_html)

        # Optional: Marker for both when explicitly not markdown-only
        if (
            self.prefer_marker
            and not marker_used_for_md
            and output_format == "both"
            and not marker_markdown_only
        ):
            log.warning(
                "Marker for both formats runs two ML passes; "
                "using pdfplumber IR for consistent both output."
            )

        # Validation
        all_issues = []
        primary_text = result.markdown or result.html or ""
        coverage = compute_coverage_ratio(pages, primary_text)
        result.coverage_ratio = round(coverage, 4)

        seen: set[str] = set()
        for fmt in formats:
            content = result.markdown if fmt == "markdown" else result.html
            if not content:
                continue
            issues = validate_output(
                content,
                page_count,
                fmt,
                page_stats=result.page_stats,
                coverage_ratio=coverage,
                min_coverage=self.min_coverage,
            )
            for issue in issues:
                key = f"{issue.level}:{issue.message}"
                if key not in seen:
                    seen.add(key)
                    all_issues.append(issue)

        result.warnings = issues_to_strings(all_issues)

        if has_critical(all_issues):
            result.status = "failed" if self.strict else "needs_review"
            if self.strict:
                result.elapsed_seconds = round(time.time() - start, 2)
                raise ConversionError(
                    f"Conversion failed validation: {result.warnings}",
                    result=result,
                )
        elif any(i.level == "warning" for i in all_issues):
            result.status = "needs_review"
        else:
            result.status = "success"

        if result.markdown:
            result.output_sha256["markdown"] = hashlib.sha256(
                result.markdown.encode("utf-8")
            ).hexdigest()
        if result.html:
            result.output_sha256["html"] = hashlib.sha256(
                result.html.encode("utf-8")
            ).hexdigest()

        result.elapsed_seconds = round(time.time() - start, 2)
        log.info("  Done in %ss (status=%s)", result.elapsed_seconds, result.status)

        if result.warnings:
            log.warning("  Quality warnings:")
            for w in result.warnings:
                log.warning("    %s", w)

        return result

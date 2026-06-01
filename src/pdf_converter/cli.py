"""Command-line interface."""

from __future__ import annotations

import argparse
import logging
import sys

from pdf_converter.converter import ConversionError, PDFConverter
from pdf_converter.io import save_result

DOC = """
PDF → Markdown & HTML Converter
================================
Auditable conversion of book-style PDFs with native text, tables, images, and OCR fallback.

Examples:
  pdf-convert book.pdf --format both --output-dir ./output
  pdf-convert book.pdf --format markdown --no-strict
  pdf-convert book.pdf --format html --marker
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert PDF books to Markdown and/or HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=DOC,
    )
    parser.add_argument("pdf", help="Input PDF file path")
    parser.add_argument(
        "--format",
        "-f",
        default="both",
        choices=["markdown", "html", "both"],
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="./output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--marker",
        action="store_true",
        help="Use Marker ML for markdown-only jobs (requires marker-pdf)",
    )
    parser.add_argument(
        "--no-embed-images",
        action="store_true",
        help="Write images as files instead of base64 in HTML",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Do not fail on critical validation warnings",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.5,
        help="Minimum input/output coverage ratio (default: 0.5)",
    )
    parser.add_argument(
        "--prose",
        action="store_true",
        help="Prose mode: skip table extraction (resumes, contracts, letters)",
    )
    parser.add_argument(
        "--allow-text-tables",
        action="store_true",
        help="Allow text-inferred tables (may duplicate prose; not recommended)",
    )
    parser.add_argument(
        "--page-breaks",
        action="store_true",
        help="Insert visible page breaks between PDF pages",
    )
    parser.add_argument(
        "--book",
        action="store_true",
        help="Book/report mode: columns, TOC, headers stripped, more images",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    converter = PDFConverter(
        prefer_marker=args.marker,
        embed_images=not args.no_embed_images,
        strict=not args.no_strict,
        min_coverage=args.min_coverage,
        prose_mode=args.prose,
        allow_text_tables=args.allow_text_tables,
        page_breaks=args.page_breaks,
        book_mode=args.book,
    )

    try:
        result = converter.convert(
            pdf_path=args.pdf,
            output_format=args.format,
        )
        manifest = save_result(result, args.output_dir, args.format)
    except ConversionError as e:
        logging.error("%s", e)
        if e.result:
            save_result(e.result, args.output_dir, args.format)
        return 1
    except FileNotFoundError as e:
        logging.error("%s", e)
        return 1

    print("\n── Conversion complete ──")
    print(f"  Status :  {manifest['status']}")
    print(f"  Engine :  {manifest['engine']}")
    print(f"  Input  :  {manifest['input']}")
    print(f"  Pages  :  {manifest['pages']}")
    if manifest.get("coverage_ratio") is not None:
        print(f"  Coverage: {manifest['coverage_ratio']}")
    print(f"  Time   :  {manifest['elapsed_seconds']}s")
    print(f"  Output :  {', '.join(manifest['outputs'])}")
    if manifest["warnings"]:
        print(f"  Warnings ({len(manifest['warnings'])}):")
        for w in manifest["warnings"]:
            print(f"    {w}")
    else:
        print("  Quality: OK")
    return 0 if manifest["status"] == "success" else 2


if __name__ == "__main__":
    sys.exit(main())

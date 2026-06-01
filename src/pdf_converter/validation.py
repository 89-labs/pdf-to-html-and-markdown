"""Output quality validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pdf_converter.models import PageContent, PageStats


@dataclass
class ValidationIssue:
    level: str  # warning | critical
    message: str


def compute_coverage_ratio(
    pages: list[PageContent],
    output_text: str,
) -> float:
    """Ratio of output chars to estimated input chars from extraction."""
    input_chars = sum(
        len(p.raw_text) or sum(len(b.text) for b in p.text_blocks)
        for p in pages
    )
    output_chars = len(re.sub(r"\s+", " ", output_text).strip())
    if input_chars == 0:
        return 1.0 if output_chars > 0 else 0.0
    return output_chars / input_chars


def estimate_output_duplication_ratio(
    pages: list[PageContent],
    output_text: str,
) -> float:
    """
    Approximate how much rendered output repeats content (e.g. false tables).
    Values > 1.15 suggest duplication.
    """
    body_chars = sum(len(b.text) for p in pages for b in p.text_blocks)
    table_chars = sum(
        len(str(cell or ""))
        for p in pages
        for table in p.tables
        for row in table
        for cell in row or []
    )
    expected = body_chars + table_chars
    output_chars = len(re.sub(r"\s+", " ", output_text).strip())
    if expected == 0:
        return 1.0
    return output_chars / expected


def validate_output(
    content: str,
    page_count: int,
    fmt: str,
    page_stats: list[PageStats] | None = None,
    coverage_ratio: float | None = None,
    min_coverage: float = 0.5,
) -> list[ValidationIssue]:
    """Run quality checks; returns structured issues."""
    issues: list[ValidationIssue] = []
    word_count = len(content.split())
    char_count = len(content)

    expected_min_chars = max(80, page_count * 80)
    expected_min_words = max(8, page_count * 8)
    char_floor = max(30, int(expected_min_chars * 0.2))
    word_floor = max(5, int(expected_min_words * 0.25))

    if page_count > 0 and char_count < char_floor:
        issues.append(
            ValidationIssue(
                "critical",
                f"Output suspiciously short ({char_count} chars, floor {char_floor})",
            )
        )
    if page_count > 0 and word_count < word_floor:
        issues.append(
            ValidationIssue(
                "critical",
                f"Very few words extracted ({word_count} words, floor {word_floor})",
            )
        )

    expected_min_words = page_count * 8
    if page_count > 0 and word_count < expected_min_words:
        issues.append(
            ValidationIssue(
                "warning",
                f"Low word count: {word_count} words for {page_count} pages "
                f"(expected ≥ {expected_min_words})",
            )
        )

    if coverage_ratio is not None and coverage_ratio < min_coverage:
        issues.append(
            ValidationIssue(
                "critical",
                f"Low coverage ratio: {coverage_ratio:.2f} (threshold {min_coverage})",
            )
        )
    if coverage_ratio is not None and coverage_ratio > 1.15:
        issues.append(
            ValidationIssue(
                "warning",
                f"Possible duplicated content in output (coverage {coverage_ratio:.2f} > 1.15)",
            )
        )

    if page_stats:
        table_pages = sum(1 for s in page_stats if s.table_count > 0)
        if table_pages > 0 and page_count > 0:
            if table_pages == page_count and page_count >= 2:
                issues.append(
                    ValidationIssue(
                        "warning",
                        f"Every page has a detected table ({table_pages}/{page_count}) "
                        "— verify this is not a false positive",
                    )
                )

    if fmt == "html":
        if "<body>" not in content.lower():
            issues.append(ValidationIssue("warning", "HTML missing <body> tag"))
        if "</html>" not in content.lower():
            issues.append(ValidationIssue("warning", "HTML document not properly closed"))
    elif fmt == "markdown":
        if page_stats:
            empty_pages = sum(1 for s in page_stats if s.word_count < 3)
            if empty_pages > page_count * 0.3:
                issues.append(
                    ValidationIssue(
                        "warning",
                        f"{empty_pages}/{page_count} pages have very little text",
                    )
                )

    return issues


def issues_to_strings(issues: list[ValidationIssue]) -> list[str]:
    prefix = {"critical": "CRITICAL", "warning": "WARNING"}
    return [f"{prefix.get(i.level, i.level.upper())}: {i.message}" for i in issues]


def has_critical(issues: list[ValidationIssue]) -> bool:
    return any(i.level == "critical" for i in issues)

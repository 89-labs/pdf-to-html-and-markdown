"""Multi-column layout detection and column-ordered reading."""

from __future__ import annotations

import statistics
from typing import Any


def detect_column_x0_peaks(
    words: list[dict],
    page_width: float,
    *,
    min_gap: float = 90,
) -> list[float]:
    """
    Return approximate x0 anchors for text columns (left edge of each column).
    Uses line-start x0 clustering.
    """
    if not words:
        return [0.0]

    line_x0: list[float] = []
    sorted_w = sorted(words, key=lambda w: (w.get("top", 0), w.get("x0", 0)))
    current_top = None
    line_start_x = None
    for w in sorted_w:
        top = w.get("top", 0)
        if current_top is None or abs(top - current_top) > 3:
            if line_start_x is not None:
                line_x0.append(line_start_x)
            line_start_x = w["x0"]
            current_top = top
        else:
            line_start_x = min(line_start_x or w["x0"], w["x0"])
    if line_start_x is not None:
        line_x0.append(line_start_x)

    if not line_x0:
        return [0.0]

    line_x0.sort()
    clusters: list[list[float]] = [[line_x0[0]]]
    for x in line_x0[1:]:
        if x - clusters[-1][-1] < min_gap:
            clusters[-1].append(x)
        else:
            clusters.append([x])

    anchors = [statistics.median(c) for c in clusters]
    # Single full-width column if spread is narrow
    if len(anchors) == 1:
        return anchors
    # Ignore tiny margin cluster at far left with few lines (page numbers)
    if len(anchors) >= 2 and anchors[0] < page_width * 0.08:
        left_cluster = [x for x in line_x0 if x < page_width * 0.12]
        if len(left_cluster) < len(line_x0) * 0.08:
            anchors = anchors[1:]
    return anchors or [0.0]


def assign_column_index(x0: float, anchors: list[float], x1: float | None = None) -> int:
    """Assign word/line to nearest column anchor (uses horizontal center when x1 given)."""
    if len(anchors) == 1:
        return 0
    cx = (x0 + x1) / 2 if x1 is not None else x0
    return min(range(len(anchors)), key=lambda i: abs(cx - anchors[i]))


def split_words_by_columns(
    words: list[dict],
    page_width: float,
    *,
    min_words_per_col: int = 80,
) -> list[list[dict]]:
    """Split words into column groups in left-to-right order."""
    anchors = detect_column_x0_peaks(words, page_width)
    if len(anchors) <= 1:
        return [words]

    columns: list[list[dict]] = [[] for _ in anchors]
    for w in words:
        col = assign_column_index(
            w.get("x0", 0), anchors, w.get("x1"),
        )
        columns[col].append(w)

    non_empty = [c for c in columns if c]
    substantial = [c for c in non_empty if len(c) >= min_words_per_col]
    if len(substantial) >= 2:
        if len(substantial) > 2:
            substantial = _merge_columns_to_page_halves(substantial, page_width)
        return substantial
    # Many tiny clusters — single reading flow
    if len(non_empty) > 3:
        return [words]
    return non_empty


def detect_page_column_split(
    words: list[dict],
    page_width: float,
    *,
    min_gap: float = 50,
) -> float | None:
    """Find vertical gutter for two-column book pages; None if not clearly split."""
    if not words:
        return None
    xs = sorted((w.get("x0", 0) + w.get("x1", 0)) / 2 for w in words)
    mid = [x for x in xs if page_width * 0.12 < x < page_width * 0.88]
    if len(mid) < 20:
        return None
    best_gap = 0.0
    split = page_width / 2
    for i in range(len(mid) - 1):
        gap = mid[i + 1] - mid[i]
        if gap > best_gap:
            best_gap = gap
            split = (mid[i] + mid[i + 1]) / 2
    if best_gap < min_gap:
        return None
    return split


def split_two_column_body(
    words: list[dict],
    page_width: float,
) -> list[list[dict]] | None:
    """Binary left/right split when a clear gutter exists."""
    split = detect_page_column_split(words, page_width)
    if split is None:
        return None
    left = [w for w in words if (w.get("x0", 0) + w.get("x1", 0)) / 2 < split]
    right = [w for w in words if (w.get("x0", 0) + w.get("x1", 0)) / 2 >= split]
    cols = []
    if len(left) >= 40:
        cols.append(left)
    if len(right) >= 40:
        cols.append(right)
    return cols if len(cols) == 2 else None


def _merge_columns_to_page_halves(
    columns: list[list[dict]],
    page_width: float,
) -> list[list[dict]]:
    """Merge over-segmented columns into left/right page halves (common in books)."""
    left: list[dict] = []
    right: list[dict] = []
    mid = page_width * 0.52
    for col in columns:
        avg_x = statistics.mean(w.get("x0", 0) for w in col)
        if avg_x < mid:
            left.extend(col)
        else:
            right.extend(col)
    halves = []
    if len(left) >= 40:
        halves.append(left)
    if len(right) >= 40:
        halves.append(right)
    return halves if len(halves) >= 2 else columns


def is_multi_column_page(
    words: list[dict],
    page_width: float,
    *,
    min_columns: int = 2,
    min_words_per_col: int = 25,
) -> bool:
    columns = split_words_by_columns(words, page_width)
    substantial = [c for c in columns if len(c) >= min_words_per_col]
    return len(substantial) >= min_columns


def split_words_by_page_regions(
    words: list[dict],
    page_width: float,
    n_columns: int,
    *,
    min_words_per_col: int = 15,
) -> list[list[dict]]:
    """Split words into N equal vertical regions (for 3-column index pages)."""
    if n_columns <= 1 or not words:
        return [words]

    boundaries = [page_width * i / n_columns for i in range(1, n_columns)]
    columns: list[list[dict]] = [[] for _ in range(n_columns)]
    for w in words:
        cx = (w.get("x0", 0) + w.get("x1", 0)) / 2
        col = 0
        while col < len(boundaries) and cx >= boundaries[col]:
            col += 1
        columns[col].append(w)

    substantial = [c for c in columns if len(c) >= min_words_per_col]
    return substantial if len(substantial) >= 2 else [words]


def count_substantial_thirds(
    words: list[dict],
    page_width: float,
    *,
    min_words: int = 40,
) -> int:
    """How many page-thirds have enough words to be real columns."""
    thirds = split_words_by_page_regions(
        words, page_width, 3, min_words_per_col=min_words
    )
    return len(thirds)

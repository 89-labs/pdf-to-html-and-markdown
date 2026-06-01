"""PDF hyperlink annotation mapping."""

from __future__ import annotations

from typing import Any


def _bbox_overlap_ratio(
    word_bbox: tuple[float, float, float, float],
    link_bbox: tuple[float, float, float, float],
) -> float:
    x0, top, x1, bottom = word_bbox
    lx0, ltop, lx1, lbottom = link_bbox
    ox = max(0, min(x1, lx1) - max(x0, lx0))
    oy = max(0, min(bottom, lbottom) - max(top, ltop))
    overlap = ox * oy
    word_area = max((x1 - x0) * (bottom - top), 1e-6)
    return overlap / word_area


def attach_hyperlinks_to_words(
    words: list[dict],
    hyperlinks: list[dict] | None,
) -> list[dict]:
    """Attach uri to words overlapping link annotations."""
    if not hyperlinks or not words:
        return words

    link_boxes: list[tuple[str, tuple[float, float, float, float]]] = []
    for h in hyperlinks:
        uri = h.get("uri")
        if not uri:
            continue
        if isinstance(uri, bytes):
            uri = uri.decode("utf-8", errors="replace")
        uri = str(uri).strip()
        bbox = (h.get("x0"), h.get("top"), h.get("x1"), h.get("bottom"))
        if None not in bbox:
            link_boxes.append((uri, bbox))  # type: ignore[arg-type]

    enriched = []
    for w in words:
        w = dict(w)
        if w.get("uri"):
            enriched.append(w)
            continue
        wb = (w.get("x0"), w.get("top"), w.get("x1"), w.get("bottom"))
        if None in wb:
            enriched.append(w)
            continue
        best_uri = None
        best_ratio = 0.0
        for uri, lb in link_boxes:
            ratio = _bbox_overlap_ratio(wb, lb)  # type: ignore[arg-type]
            if ratio > best_ratio and ratio >= 0.3:
                best_ratio = ratio
                best_uri = uri
        if best_uri:
            w["uri"] = best_uri
        enriched.append(w)
    return enriched

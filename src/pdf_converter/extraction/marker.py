"""Marker ML extraction (optional dependency)."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any, Optional

log = logging.getLogger(__name__)


def extract_with_marker(
    pdf_path: str,
    output_format: str,
) -> Optional[tuple[str, dict[str, bytes], dict[str, Any]]]:
    """
    Use Marker for high-fidelity extraction.
    Returns (content, image_files, metadata) or None if unavailable.
    """
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
    except ImportError:
        log.warning("marker-pdf not installed; skipping Marker engine.")
        return None

    try:
        renderer = (
            "marker.renderers.html.HTMLRenderer"
            if output_format == "html"
            else "marker.renderers.markdown.MarkdownRenderer"
        )

        log.info("Loading Marker models (first run may download ~500MB)...")
        artifact_dict = create_model_dict()
        converter = PdfConverter(
            artifact_dict=artifact_dict,
            renderer=renderer,
        )

        log.info("Running Marker conversion (%s)...", output_format)
        rendered = converter(pdf_path)
        content, images, metadata = text_from_rendered(rendered)

        img_files: dict[str, bytes] = {}
        for img_name, img_obj in (images or {}).items():
            if hasattr(img_obj, "save"):
                buf = BytesIO()
                img_obj.save(buf, format="PNG")
                img_files[str(img_name)] = buf.getvalue()

        return content, img_files, metadata or {}

    except Exception as e:
        log.warning("Marker unavailable (%s): %s", type(e).__name__, e)
        return None

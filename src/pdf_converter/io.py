"""Save conversion outputs and manifest."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from pdf_converter.models import ConversionResult, PageStats

log = logging.getLogger(__name__)


def save_result(
    result: ConversionResult,
    output_dir: str,
    output_format: str,
    stem: Optional[str] = None,
) -> dict[str, Any]:
    """Write outputs to disk and return manifest dict."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    name = stem or Path(result.input_path).stem

    manifest: dict[str, Any] = {
        "input": result.input_path,
        "input_sha256": result.input_sha256,
        "pages": result.page_count,
        "engine": result.engine,
        "pipeline_version": result.pipeline_version,
        "status": result.status,
        "coverage_ratio": result.coverage_ratio,
        "output_sha256": result.output_sha256,
        "outputs": [],
        "warnings": result.warnings,
        "elapsed_seconds": result.elapsed_seconds,
        "page_stats": [
            {
                "page": s.page_num + 1,
                "mode": s.mode,
                "chars": s.char_count,
                "words": s.word_count,
                "tables": s.table_count,
                "images": s.image_count,
                "ocr_confidence": s.ocr_mean_confidence,
            }
            for s in result.page_stats
            if isinstance(s, PageStats)
        ],
    }

    if result.markdown and output_format in ("markdown", "both"):
        md_path = out / f"{name}.md"
        md_path.write_text(result.markdown, encoding="utf-8")
        manifest["outputs"].append(str(md_path))
        log.info("  Saved: %s", md_path)

    if result.html and output_format in ("html", "both"):
        html_path = out / f"{name}.html"
        html_path.write_text(result.html, encoding="utf-8")
        manifest["outputs"].append(str(html_path))
        log.info("  Saved: %s", html_path)

    for fname, data in result.image_files.items():
        img_path = out / fname
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img_path.write_bytes(data)

    manifest_path = out / f"{name}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest

"""Integration test with a generated sample PDF."""

from pathlib import Path

import pytest

from pdf_converter.converter import PDFConverter
from pdf_converter.io import save_result

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


@pytest.mark.skipif(not FIXTURE.exists(), reason="sample.pdf not generated")
def test_convert_sample_both(tmp_path):
    converter = PDFConverter(strict=False)
    result = converter.convert(str(FIXTURE), output_format="both")
    assert result.page_count >= 1
    assert result.markdown
    assert result.html
    assert "<body>" in result.html.lower()
    assert result.status in ("success", "needs_review")

    manifest = save_result(result, str(tmp_path), "both")
    assert len(manifest["outputs"]) >= 2
    assert (tmp_path / "sample_manifest.json").exists()

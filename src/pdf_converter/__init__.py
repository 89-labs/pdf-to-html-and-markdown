"""PDF to Markdown & HTML converter."""

from pdf_converter.converter import ConversionError, PDFConverter
from pdf_converter.models import ConversionResult

__version__ = "1.0.0"
__all__ = ["PDFConverter", "ConversionResult", "ConversionError"]

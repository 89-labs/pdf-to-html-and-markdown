"""Output renderers."""

from pdf_converter.rendering.html import pages_to_html
from pdf_converter.rendering.markdown import pages_to_markdown

__all__ = ["pages_to_markdown", "pages_to_html"]

"""HTML escaping tests."""

from pdf_converter.models import PageContent, TextBlock
from pdf_converter.rendering.html import pages_to_html


def test_html_escapes_script():
    pages = [
        PageContent(
            page_num=0,
            mode="native",
            text_blocks=[
                TextBlock(text='<script>alert("x")</script>', role="paragraph"),
            ],
        )
    ]
    html, _ = pages_to_html(pages, title='Title <test>')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<title>Title &lt;test&gt;</title>" in html

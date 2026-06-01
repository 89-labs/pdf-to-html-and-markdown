"""HTML renderer from PageContent with proper escaping."""

from __future__ import annotations

import base64
import html
import re

from pdf_converter.models import PageContent, TextBlock
from pdf_converter.rendering.document import iter_render_segments
from pdf_converter.rendering.rich_text import block_inline_html


def _cell(val) -> str:
    if val is None:
        return ""
    return html.escape(str(val).replace("\n", " ")).strip()


def _table_to_html(table: list) -> str:
    if not table or not table[0]:
        return ""
    col_count = max(len(row) for row in table)
    padded = [row + [None] * (col_count - len(row)) for row in table]

    rows_html = []
    for i, row in enumerate(padded):
        tag = "th" if i == 0 else "td"
        cells = "".join(
            f"<{tag}>{_cell(c) or '&#160;'}</{tag}>" for c in row
        )
        rows_html.append(f"    <tr>{cells}</tr>")

    return "<table>\n" + "\n".join(rows_html) + "\n</table>"


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 16px;
      line-height: 1.75;
      color: #1a1a1a;
      max-width: 780px;
      margin: 0 auto;
      padding: 40px 24px 80px;
      background: #fff;
    }}
    h1 {{ font-size: 2em;   margin: 1.6em 0 0.5em; border-bottom: 2px solid #222; padding-bottom: .2em; }}
    h2 {{ font-size: 1.5em; margin: 1.5em 0 0.4em; }}
    h3 {{ font-size: 1.2em; margin: 1.2em 0 0.35em; color: #333; }}
    h4 {{ font-size: 1.05em; margin: 1em 0 0.3em; }}
    h5 {{ font-size: 1em; margin: 0.9em 0 0.25em; font-weight: 600; }}
    h6 {{ font-size: 0.95em; margin: 0.85em 0 0.2em; font-weight: 600; color: #444; }}
    p  {{ margin: 0.85em 0; }}
    ul, ol {{ margin: 0.75em 0 0.75em 1.8em; }}
    li {{ margin: 0.35em 0; }}
    a {{ color: #1a5fb4; }}
    code {{
      font-family: ui-monospace, 'Cascadia Code', Menlo, monospace;
      font-size: 0.9em;
      background: #f4f4f4;
      padding: 0.1em 0.35em;
      border-radius: 3px;
    }}
    pre {{
      background: #f4f4f4;
      padding: 1em;
      overflow-x: auto;
      border-radius: 4px;
      margin: 1em 0;
      font-size: 0.9em;
    }}
    blockquote {{
      margin: 1em 0;
      padding: .5em 1em;
      border-left: 3px solid #aaa;
      color: #555;
      font-size: .93em;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 1.4em 0;
      font-size: .92em;
      font-family: 'Helvetica Neue', Arial, sans-serif;
    }}
    th, td {{
      border: 1px solid #ccc;
      padding: 8px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #2c4770;
      color: #fff;
      font-weight: 600;
    }}
    tr:nth-child(even) td {{ background: #f7f8fa; }}
    img {{
      max-width: 100%;
      height: auto;
      display: block;
      margin: 1.2em auto;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
    }}
    figcaption {{
      font-size: 0.9em;
      color: #555;
      text-align: center;
      margin: -0.5em 0 1.2em;
    }}
    hr.page-break {{
      margin: 2.5em 0;
      border: none;
      border-top: 1px dashed #ccc;
    }}
    .page-label {{
      font-size: .75em;
      color: #999;
      text-align: center;
      margin: 1em 0;
    }}
    .footnote {{
      font-size: .85em;
      color: #555;
      border-left: 2px solid #ddd;
      padding-left: .8em;
      margin: .4em 0;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def _heading_html(block: TextBlock) -> str:
    level = block.role if block.role.startswith("h") else "h2"
    tag = level if level in ("h1", "h2", "h3", "h4", "h5", "h6") else "h2"
    inner = block_inline_html(block)
    return f"<{tag}>{inner}</{tag}>"


def _list_item_html(block: TextBlock) -> str:
    text = block.text.strip()
    clean = re.sub(r"^[\u2022\u2023\u25E6\u2043\*\-\+•○■]\s*", "", text)
    clean = re.sub(r"^\d+[\.\)]\s+", "", clean)
    return f"<li>{block_inline_html(block) if block.spans else html.escape(clean)}</li>"


def _list_group_html(blocks: list[TextBlock]) -> str:
    if not blocks:
        return ""
    first = blocks[0].text.strip()
    ordered = bool(re.match(r"^\d+[\.\)]\s+", first)) or blocks[0].ordered
    items = "".join(_list_item_html(b) for b in blocks)
    tag = "ol" if ordered else "ul"
    return f"<{tag}>{items}</{tag}>"


def pages_to_html(
    pages: list[PageContent],
    title: str = "Document",
    embed_images: bool = True,
    image_dir: str = "images",
    *,
    page_breaks: bool = False,
) -> tuple[str, dict[str, bytes]]:
    """Convert PageContent to styled HTML document."""
    body_parts: list[str] = []
    image_files: dict[str, bytes] = {}
    img_counter = 0
    safe_title = html.escape(title)

    for page in pages:
        if page_breaks and page.page_num > 0:
            body_parts.append(
                f'<hr class="page-break"><p class="page-label">Page {page.page_num + 1}</p>'
            )

        if page.mode == "ocr":
            for img in page.images:
                if img.is_full_page:
                    img_counter += 1
                    if embed_images:
                        b64 = base64.b64encode(img.data).decode()
                        src = f"data:image/png;base64,{b64}"
                    else:
                        fname = f"{image_dir}/page_{page.page_num + 1}_scan.png"
                        image_files[fname] = img.data
                        src = fname
                    alt = html.escape(f"Scanned page {page.page_num + 1}")
                    body_parts.append(f'<img src="{src}" alt="{alt}">')

        for kind, payload in iter_render_segments([page], page_breaks=False):
            if kind == "heading" and isinstance(payload, TextBlock):
                body_parts.append(_heading_html(payload))
            elif kind == "list_group" and isinstance(payload, list):
                body_parts.append(_list_group_html(payload))
            elif kind == "blockquote" and isinstance(payload, TextBlock):
                body_parts.append(f"<blockquote>{block_inline_html(payload)}</blockquote>")
            elif kind == "code_block" and isinstance(payload, TextBlock):
                body_parts.append(f"<pre><code>{block_inline_html(payload)}</code></pre>")
            elif kind == "footnote" and isinstance(payload, TextBlock):
                body_parts.append(
                    f'<p class="footnote">{block_inline_html(payload)}</p>'
                )
            elif kind == "caption" and isinstance(payload, TextBlock):
                body_parts.append(f"<figcaption>{block_inline_html(payload)}</figcaption>")
            elif kind == "hr":
                body_parts.append("<hr>")
            elif kind == "paragraph" and isinstance(payload, TextBlock):
                inner = block_inline_html(payload)
                if payload.text.startswith("*") and payload.text.endswith("*"):
                    body_parts.append(f"<p><em>{inner}</em></p>")
                else:
                    body_parts.append(f"<p>{inner}</p>")
            elif kind == "table" and payload is not None:
                body_parts.append(_table_to_html(payload))

        for img in page.images:
            if img.is_full_page:
                continue
            img_counter += 1
            if embed_images:
                b64 = base64.b64encode(img.data).decode()
                src = f"data:image/{img.ext};base64,{b64}"
            else:
                fname = f"{image_dir}/figure_{page.page_num + 1}_{img.index + 1}.{img.ext}"
                image_files[fname] = img.data
                src = fname
            alt = html.escape(f"Figure {img_counter}")
            body_parts.append(f'<img src="{src}" alt="{alt}">')

    body = "\n".join(body_parts)
    return HTML_TEMPLATE.format(title=safe_title, body=body), image_files

# PDF → Markdown & HTML

Production-oriented converter for **book-style PDFs**: native text, tables, embedded images, headings, lists, and OCR fallback for scanned pages.

## Features

- **Single canonical extraction** — `--format both` always renders Markdown and HTML from the same structured page model (no mixed engines).
- **Per-page routing** — native text vs OCR per page (mixed documents supported).
- **Table deduplication** — table regions masked from body text so tables are not emitted twice.
- **Text cleanup** — `(cid:NNN)` font artefacts, inline bullet splitting, font-size heading detection.
- **Batched OCR** — consecutive scanned pages rasterized in one poppler call.
- **Auditable output** — input/output SHA-256, per-page stats, coverage ratio, JSON manifest.
- **Strict validation** — critical quality issues fail the job by default (use `--no-strict` to warn only).
- **Safe HTML** — all text escaped to prevent injection from PDF content.
- **Rich inline text (v1.4)** — bold, italic, links, code, super/subscript, and colors when encoded in the PDF (see [docs/FEATURES.md](docs/FEATURES.md) for the full support matrix).

## Requirements

- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (`tesseract` on PATH)
- [Poppler](https://poppler.freedesktop.org/) (`pdftoppm` / `pdfinfo` for `pdf2image`)

### macOS

```bash
brew install tesseract poppler
```

### Ubuntu / Debian

```bash
sudo apt-get install tesseract-ocr poppler-utils
```

## Install

```bash
cd PDF-Markdown
python -m venv .venv
source .venv/bin/activate
pip install -e .
# or: pip install -r requirements.txt && pip install -e .
```

### Optional: Marker (ML layout, highest fidelity for complex books)

```bash
pip install -e ".[marker]"
```

First run downloads ~500MB of models. Set `MARKER_MODELS_DIR` for offline/air-gapped use.

## Usage

```bash
# Both Markdown and HTML (recommended)
pdf-convert mybook.pdf --format both --output-dir ./output

# Or via convenience script
python converter.py mybook.pdf --format both --output-dir ./output

# Markdown only
pdf-convert mybook.pdf -f markdown -o ./output

# HTML with external image files
pdf-convert mybook.pdf -f html --no-embed-images

# Marker for markdown-only (when installed)
pdf-convert mybook.pdf -f markdown --marker

# Lenient validation (warnings only)
pdf-convert mybook.pdf --no-strict

# Resumes, contracts, letters (skip table inference entirely)
pdf-convert resume.pdf --prose --format both -o ./output
```

### Prose PDFs (resumes, contracts)

By default, the converter **no longer** infers tables from text alignment (which caused duplicate/garbled output). Use `--prose` to disable table extraction entirely on documents with no real grid tables.

**v1.2** adds layout-aware structure: proper `#` / `##` headings, bullet lists, numbered milestones, paragraph breaks, and editor-friendly spacing. Page separators are off by default; use `--page-breaks` to show them.

**v1.4** preserves inline formatting from PDF fonts and link annotations into Markdown (`**bold**`, `[link](url)`) and HTML (`<strong>`, `<a href="...">`). Headings `h1`–`h6`, code blocks, blockquotes, and captions are rendered when detected. Editor-only features (AI blocks, track changes, embeds, tabs, etc.) are not in PDFs — see [docs/FEATURES.md](docs/FEATURES.md).

### Complex books & reports (`space.pdf`, strategy documents)

```bash
pdf-convert space.pdf --book --format both -o ./output
```

`--book` enables: multi-column reading order, TOC page parsing, repeating header/footer removal, higher-resolution figures, and full-page capture for diagram-heavy pages.

## Output

```
output/
  mybook.md
  mybook.html
  mybook_manifest.json
  images/          # when --no-embed-images or markdown figures
```

Manifest includes `input_sha256`, `output_sha256`, `coverage_ratio`, `page_stats`, `status`, and `warnings`.

## Architecture

```
PDF → classify pages → native (pdfplumber) / OCR (Tesseract, batched)
     → PageContent[] (canonical IR)
     → Markdown + HTML serializers
     → validation → manifest
```

Optional Marker path applies only to **markdown-only** jobs when `--marker` is passed, to avoid inconsistent dual-format output.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT

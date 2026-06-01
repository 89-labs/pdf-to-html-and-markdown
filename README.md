# PDF → Markdown & HTML

Convert **book-style PDFs** into clean, editable **Markdown** and **HTML** — with native text extraction, table handling, embedded images, layout-aware structure, and OCR fallback for scanned pages.

Use it when you need to **read, edit, search, or publish** PDF content outside a PDF viewer: documentation sites, knowledge bases, LLM pipelines, archival text, or version-controlled drafts.

---

## Table of contents

- [What this tool does](#what-this-tool-does)
- [Use cases](#use-cases)
- [How it works (at a glance)](#how-it-works-at-a-glance)
- [Quick start](#quick-start)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage guide](#usage-guide)
- [Choosing the right mode](#choosing-the-right-mode)
- [CLI reference](#cli-reference)
- [Output files](#output-files)
- [Optional: Marker (ML layout)](#optional-marker-ml-layout)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)
- [Development](#development)
- [License](#license)

---

## What this tool does

This converter turns a PDF into structured text formats while preserving as much of the original meaning as possible:

| Capability | Description |
|------------|-------------|
| **Dual output** | Markdown (`.md`) and HTML (`.html`) from the **same** internal page model — consistent content, not two different engines fighting each other. |
| **Smart page routing** | Each page is classified as **native text** or **scanned**; mixed PDFs (some digital, some scanned) are handled page by page. |
| **Structure** | Headings (`#`–`######`), lists, paragraphs, tables, images, links, code blocks, blockquotes, and inline formatting (bold, italic, colors when encoded). |
| **Tables** | Ruled tables extracted once; table regions are masked from body text so content is not duplicated. |
| **OCR** | Tesseract on scanned pages, with **batched** rasterization via Poppler for speed. |
| **Quality checks** | Coverage ratio, per-page stats, warnings; strict mode fails the job on critical issues (auditable manifests). |
| **Safe HTML** | All text is escaped so malicious content inside a PDF cannot become HTML injection. |

**What it is not:** a general “PDF to Word” clone, a form filler, or a guarantee of pixel-perfect layout. PDFs store **drawn glyphs**, not semantic documents — this tool reconstructs structure with heuristics. See [docs/FEATURES.md](docs/FEATURES.md) for a full feature matrix (what is supported, partial, or not in PDFs).

---

## Use cases

### Documentation & publishing

- Turn technical books, reports, or whitepapers into **Markdown** for Git, static site generators (Hugo, MkDocs, Docusaurus), or CMS import.
- Generate **HTML** for internal wikis or preview pages, with images embedded or written to disk.

### Search, analysis & AI

- Feed clean text into **search indexes**, RAG pipelines, or summarization — without brittle copy-paste from a PDF viewer.
- Keep **SHA-256 hashes** and manifests for reproducible batch jobs and compliance trails.

### Personal & professional documents

- **Resumes, cover letters, contracts** — use `--prose` to avoid false “tables” from aligned columns and get readable headings and lists.
- **Mixed native + scan** — e.g. signed appendices: native pages stay fast; scanned pages go through OCR automatically.

### Books & complex layouts

- Multi-column reports, strategy PDFs, diagram-heavy chapters — use `--book` for column order, TOC parsing, header/footer stripping, and richer figure handling.

### Archival & migration

- Move legacy PDF libraries into text-first storage with **auditable manifests** (`input_sha256`, `output_sha256`, `page_stats`, `coverage_ratio`).

---

## How it works (at a glance)

```
PDF file
   │
   ├─► Classify each page (native vs scanned)
   │
   ├─► Extract
   │     • Native: pdfplumber (text, fonts, tables, images, links)
   │     • Scanned: Poppler → image → Tesseract OCR (batched)
   │
   ├─► Build canonical page model (PageContent[])
   │
   ├─► Render → Markdown + HTML
   │
   └─► Validate → manifest JSON (stats, hashes, warnings)
```

**Default path:** one pdfplumber extraction → both formats. Optional **Marker** applies only to **markdown-only** jobs when you pass `--marker` (see below).

---

## Quick start

**1. Install system dependencies** (macOS example):

```bash
brew install tesseract poppler
```

**2. Install the Python package:**

```bash
git clone https://github.com/89-labs/pdf-to-html-and-markdown.git
cd PDF-Markdown
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

**3. Convert a PDF:**

```bash
pdf-convert my-document.pdf --format both --output-dir ./output
```

**4. Open the results:**

```text
output/
  my-document.md
  my-document.html
  my-document_manifest.json
```

You can also run:

```bash
python converter.py my-document.pdf --format both -o ./output
```

---

## Requirements

| Requirement | Purpose |
|-------------|---------|
| **Python 3.10+** | Runtime |
| **[Tesseract](https://github.com/tesseract-ocr/tesseract)** | OCR for scanned pages (`tesseract` on `PATH`) |
| **[Poppler](https://poppler.freedesktop.org/)** | Rasterize pages (`pdftoppm` / `pdfinfo` via `pdf2image`) |

### macOS

```bash
brew install tesseract poppler
```

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils
```

### Windows

Install [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases), and ensure both are on your `PATH`.

---

## Installation

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Alternative (if you maintain a `requirements.txt`):

```bash
pip install -r requirements.txt
pip install -e .
```

Verify the CLI:

```bash
pdf-convert --help
```

---

## Usage guide

### Recommended default (most documents)

Produces both Markdown and HTML with validation and a manifest:

```bash
pdf-convert report.pdf --format both --output-dir ./output
```

### Prose documents (resume, contract, letter)

Skip table extraction entirely — avoids duplicate or garbled “tables” from aligned text:

```bash
pdf-convert resume.pdf --prose --format both -o ./output
```

You get layout-aware structure: headings, bullet/numbered lists, paragraph breaks, and inline formatting when present in the PDF.

### Books & complex reports

Enables multi-column reading order, TOC parsing, repeating header/footer removal, higher-resolution figures, and fuller image capture on diagram-heavy pages:

```bash
pdf-convert strategy-report.pdf --book --format both -o ./output
```

### Markdown or HTML only

```bash
pdf-convert book.pdf -f markdown -o ./output
pdf-convert book.pdf -f html -o ./output
```

### HTML with external image files

Useful when you want smaller HTML files or to reuse images elsewhere:

```bash
pdf-convert book.pdf -f html --no-embed-images -o ./output
```

### Visible page separators

By default, page breaks are **not** shown in the output (reads like one document). To keep PDF page boundaries:

```bash
pdf-convert book.pdf --page-breaks --format both -o ./output
```

### Lenient validation

By default, critical quality issues **fail** the job (exit code non-zero) but may still write partial output. To only warn:

```bash
pdf-convert noisy-scan.pdf --no-strict -o ./output
```

### Adjust coverage threshold

Validation compares extracted text volume to the PDF text layer. Lower the bar for sparse or image-heavy PDFs:

```bash
pdf-convert slides.pdf --min-coverage 0.3 --no-strict -o ./output
```

### Debug logging

```bash
pdf-convert book.pdf -v --format both -o ./output
```

---

## Choosing the right mode

| Your PDF looks like… | Suggested flags |
|----------------------|-----------------|
| Resume, CV, contract, letter, one-column prose | `--prose` |
| Technical book, annual report, multi-column, TOC, many figures | `--book` |
| General article or mixed content | *(none)* — default |
| You need page boundaries in the output | `--page-breaks` |
| False tables / duplicated columns in prose | `--prose` (do **not** use `--allow-text-tables` unless you know you need it) |
| Markdown-only, maximum layout ML (optional) | `-f markdown --marker` (requires extra install) |

**Inline formatting (v1.4):** bold, italic, links, inline code, super/subscript, and colors are preserved when encoded in the PDF. Headings, lists, tables, images, code blocks, and blockquotes are emitted when detected. Editor-only concepts (track changes, embeds, tabs, AI blocks) are not in PDFs — see [docs/FEATURES.md](docs/FEATURES.md).

---

## CLI reference

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `pdf` | — | *(required)* | Path to input PDF |
| `--format` | `-f` | `both` | `markdown`, `html`, or `both` |
| `--output-dir` | `-o` | `./output` | Directory for outputs |
| `--prose` | — | off | Skip table extraction (prose PDFs) |
| `--book` | — | off | Book/report mode (columns, TOC, headers, figures) |
| `--page-breaks` | — | off | Insert visible separators between PDF pages |
| `--marker` | — | off | Use Marker ML for **markdown-only** jobs |
| `--no-embed-images` | — | off | Write images as files instead of base64 in HTML |
| `--no-strict` | — | off | Warn instead of failing on critical validation issues |
| `--min-coverage` | — | `0.5` | Minimum input/output coverage ratio |
| `--allow-text-tables` | — | off | Infer tables from text alignment (can duplicate prose) |
| `--verbose` | `-v` | off | Debug logging |

**Exit codes:** `0` success, `1` error (e.g. missing file, conversion error), `2` completed with validation failure in strict mode.

---

## Output files

After a successful run:

```text
output/
  <basename>.md                 # Markdown
  <basename>.html               # HTML (self-contained unless --no-embed-images)
  <basename>_manifest.json      # Audit metadata
  images/                       # When --no-embed-images or markdown figures need files
```

### Manifest (`*_manifest.json`)

Example fields:

| Field | Meaning |
|-------|---------|
| `input` / `input_sha256` | Source path and hash |
| `output_sha256` | Hashes of generated markdown/html |
| `pages` | Page count |
| `engine` | e.g. `pdfplumber` or `marker` |
| `pipeline_version` | Converter version (e.g. `1.4.0`) |
| `status` | `success` or failure state |
| `coverage_ratio` | How much text was captured vs PDF text layer |
| `page_stats` | Per page: `mode` (`native` / `ocr`), chars, words, tables, images, OCR confidence |
| `warnings` | Quality issues detected |
| `elapsed_seconds` | Wall time |

Use manifests for CI gates, regression tests, or batch pipelines.

---

## Optional: Marker (ML layout)

For **markdown-only** jobs on very complex books, you can opt into [Marker](https://github.com/VikParuchuri/marker) (higher fidelity, ML-based layout):

```bash
pip install -e ".[marker]"
pdf-convert complex-book.pdf -f markdown --marker -o ./output
```

- First run downloads ~500MB of models.
- Set `MARKER_MODELS_DIR` for offline or air-gapped environments.
- With `--format both`, the default pipeline still uses a **single** pdfplumber extraction for consistency; Marker is not mixed into the HTML path unless you run markdown-only with `--marker`.

---

## Troubleshooting

| Problem | Things to try |
|---------|----------------|
| `tesseract: command not found` | Install Tesseract and ensure it is on `PATH`. |
| Errors mentioning `pdftoppm` / Poppler | Install `poppler-utils` (Linux) or `poppler` (macOS). |
| Garbled or duplicate “tables” in a resume | Use `--prose`; avoid `--allow-text-tables`. |
| Multi-column text reads in wrong order | Use `--book`. |
| Job fails with low coverage | Scanned PDF with little text layer: try `--no-strict` and/or lower `--min-coverage`; check OCR language packs for Tesseract. |
| Missing bold/links | Depends on how the PDF was authored; see [docs/FEATURES.md](docs/FEATURES.md). |
| Huge HTML files | Use `--no-embed-images` and serve the `images/` folder alongside HTML. |

Run with `-v` to see per-page native vs OCR routing and extraction details.

---

## Architecture

```
PDF → classify pages → native (pdfplumber) / OCR (Tesseract, batched via Poppler)
     → PageContent[] (canonical intermediate representation)
     → Markdown + HTML serializers
     → validation → manifest
```

Package layout:

```text
src/pdf_converter/
  cli.py              # pdf-convert entry point
  converter.py        # Orchestration, validation, hashing
  extraction/         # Native, OCR, tables, layout, links, styling
  rendering/          # Markdown & HTML from page model
  validation.py       # Coverage and quality checks
```

Optional Marker integrates only on the markdown-only + `--marker` path.

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests live under `tests/` (unit tests and integration against fixture PDFs).

---

## License

MIT

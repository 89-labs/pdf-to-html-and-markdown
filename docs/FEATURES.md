# Feature support matrix

PDF → Markdown/HTML conversion preserves what is **encoded in the PDF**. Many editor/CMS features exist only in HTML apps, not in PDF files.

Legend:

| Status | Meaning |
|--------|---------|
| **Yes** | Extracted and emitted in MD/HTML when present in PDF |
| **Partial** | Heuristic or limited (depends on how the PDF was authored) |
| **Output** | Added at render time (not from PDF content) |
| **No** | Not in PDF; not generated unless you add post-processing |

## Inline text

| Feature | Status | Notes |
|---------|--------|-------|
| Bold | **Yes** | Font name (`Bold`, `Semibold`, …) |
| Italic | **Yes** | Font name (`Italic`, `Oblique`) |
| Bold + Italic | **Yes** | Combined spans |
| Underline | **Partial** | Rare in vector text; often missing |
| Strikethrough | **Partial** | Not reliably in font metadata |
| Inline code | **Yes** | Monospace / Courier fonts |
| Superscript | **Partial** | Size + vertical offset heuristics |
| Subscript | **Partial** | Size + vertical offset heuristics |
| Highlight / mark | **Partial** | Non-stroking color on chars when available |
| Small text | **Partial** | Relative font size |
| Uppercase / lowercase transform | **No** | PDF stores glyphs as drawn; case is literal |
| Drop caps | **No** | Layout-specific; not detected |

## Block structure

| Feature | Status | Notes |
|---------|--------|-------|
| Paragraph | **Yes** | Line/paragraph merge |
| Line break | **Partial** | Within paragraph merge; hard breaks rare |
| Page break | **Output** | `--page-breaks` in MD/HTML |
| Heading 1–6 | **Yes** | Size + title heuristics (`h1`–`h6`) |
| Bulleted list | **Yes** | Bullets and `●` splits |
| Numbered list | **Yes** | `1.` / `1)` patterns |
| Nested list | **Partial** | Indent levels not fully modeled |
| Checklist / task list | **Partial** | `[ ]` lines when present as text |
| Definition list | **No** | |
| Hyperlink | **Yes** | PDF link annotations → `<a>` / MD links |
| Anchor link | **Partial** | URIs preserved; fragment IDs not invented |
| Footnote | **Partial** | Role when detected; not true footnote refs |
| Endnote | **Partial** | Same as footnote |
| Citation / reference | **No** | Unless plain text |
| Cross-reference | **No** | |
| Blockquote | **Yes** | Role `blockquote` when classified |
| Pull quote | **No** | |
| Code block | **Yes** | Monospace blocks |
| Table | **Yes** | Ruled tables (`lines_strict`); `--prose` skips |
| Image | **Yes** | Embedded + book-mode full-page figures |
| Image caption | **Partial** | `caption` role when set |
| Video embed | **No** | |
| External embed | **No** | |
| Horizontal rule | **Yes** | `hr` role / `---` |
| Callout | **No** | Use post-processing |
| Collapsible / toggle | **No** | |
| Comments / annotations | **No** | PDF comments not read |
| Track changes | **No** | |
| Mentions (@user) | **No** | Unless literal text |
| Tags / labels | **No** | |
| Version history | **No** | |

## Document sections

| Feature | Status | Notes |
|---------|--------|-------|
| Table of contents | **Partial** | `--book` TOC from text |
| Title page | **Partial** | First-page title heuristics |
| Preface / Introduction / Chapter / … | **Partial** | Via headings only |
| Appendix / Glossary / Index / Bibliography | **Partial** | Heading text only |
| Headers / footers | **Partial** | Stripped in `--book` mode |
| Page numbers | **Partial** | Often removed as furniture |
| Margin notes | **No** | |

## Typography & layout

| Feature | Status | Notes |
|---------|--------|-------|
| Text alignment | **No** | Not emitted |
| Indentation | **Partial** | Column split only |
| Letter / line spacing | **No** | |
| Font size / family | **Partial** | Used for classification; inline size for small/sup |
| Text / background color | **Partial** | Char-level colors when available |
| Multi-column | **Partial** | `--book` two-column split |
| Grid layout | **No** | |
| Math (LaTeX) | **No** | Use Marker/OCR pipeline separately |
| Syntax highlighting | **No** | Fenced code only |
| HTML embed | **No** | |
| Custom blocks | **No** | |

## App / learning / AI blocks

| Feature | Status |
|---------|--------|
| Interactive quiz, inline Q&A, AI summary, AI assistant, highlight-to-comment/AI, bookmarks, reading progress, streaks | **No** |

## Media & files

| Feature | Status | Notes |
|---------|--------|-------|
| Audio embed | **No** | |
| File attachment | **No** | |
| Download link | **Partial** | If URL in link annotation |
| Copy-to-clipboard | **No** | |

## Composite UI blocks

| Feature | Status |
|---------|--------|
| Timeline, steps, cards, tabs, accordion, in-content alerts | **No** |

## Production

| Feature | Status | Notes |
|---------|--------|-------|
| Watermark | **No** | |
| Print layout | **Partial** | Basic HTML CSS |
| Export PDF/EPUB | **No** | Output is MD/HTML |

## CLI flags

```bash
pdf-convert doc.pdf --prose --format both -o output    # prose: no false tables
pdf-convert doc.pdf --book --format both -o output     # TOC, columns, headers
pdf-convert doc.pdf --page-breaks                      # page separators in output
```

Pipeline version is recorded in the conversion manifest (`PIPELINE_VERSION` in `models.py`).

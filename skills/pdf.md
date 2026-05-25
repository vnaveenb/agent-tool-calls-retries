# PDF Processing Skill

## Overview

This skill covers PDF processing: reading, creating, merging, splitting, and manipulating PDF files.

## Quick Reference

| Task | Best Tool | Command/Code |
|------|-----------|--------------|
| Merge PDFs | pypdf | `writer.add_page(page)` |
| Split PDFs | pypdf | One page per file |
| Extract text | pdfplumber | `page.extract_text()` |
| Extract tables | pdfplumber | `page.extract_tables()` |
| Create PDFs | reportlab | Canvas or Platypus |
| Command line merge | qpdf | `qpdf --empty --pages ...` |
| OCR scanned PDFs | pytesseract | Convert to image first |
| Fill PDF forms | pdf-lib or pypdf | See forms section |

---

## Quick Start

```python
from pypdf import PdfReader, PdfWriter

# Read a PDF
reader = PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")

# Extract text
text = ""
for page in reader.pages:
    text += page.extract_text()
```

---

## Python Libraries

### pypdf — Basic Operations

#### Merge PDFs
```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

#### Split PDF
```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

#### Rotate Pages
```python
reader = PdfReader("input.pdf")
writer = PdfWriter()
page = reader.pages[0]
page.rotate(90)  # 90 degrees clockwise
writer.add_page(page)
with open("rotated.pdf", "wb") as output:
    writer.write(output)
```

#### Extract Metadata
```python
reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"Title: {meta.title}, Author: {meta.author}")
```

#### Password Protection
```python
reader = PdfReader("input.pdf")
writer = PdfWriter()
for page in reader.pages:
    writer.add_page(page)
writer.encrypt("userpassword", "ownerpassword")
with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

#### Add Watermark
```python
from pypdf import PdfReader, PdfWriter

watermark = PdfReader("watermark.pdf").pages[0]
reader = PdfReader("document.pdf")
writer = PdfWriter()
for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)
with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

---

### pdfplumber — Text and Table Extraction

#### Extract Text with Layout
```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

#### Extract Tables
```python
with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"Table {j+1} on page {i+1}:")
            for row in table:
                print(row)
```

#### Advanced Table Extraction (to Excel)
```python
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

if all_tables:
    combined_df = pd.concat(all_tables, ignore_index=True)
    combined_df.to_excel("extracted_tables.xlsx", index=False)
```

---

### reportlab — Create PDFs

#### Basic PDF (Canvas)
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("hello.pdf", pagesize=letter)
width, height = letter
c.drawString(100, height - 100, "Hello World!")
c.line(100, height - 140, 400, height - 140)
c.save()
```

#### Multi-Page Report (Platypus)
```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

story.append(Paragraph("Report Title", styles['Title']))
story.append(Spacer(1, 12))
story.append(Paragraph("Body content here. " * 20, styles['Normal']))
story.append(PageBreak())
story.append(Paragraph("Page 2", styles['Heading1']))
story.append(Paragraph("Content for page 2", styles['Normal']))

doc.build(story)
```

#### Subscripts and Superscripts

**IMPORTANT**: Never use Unicode subscript/superscript characters (₀₁₂₃₄₅₆₇₈₉, ⁰¹²³⁴⁵⁶⁷⁸⁹) — they render as solid black boxes in ReportLab.

```python
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()
chemical = Paragraph("H<sub>2</sub>O", styles['Normal'])
squared = Paragraph("x<super>2</super> + y<super>2</super>", styles['Normal'])
```

---

## Command-Line Tools

### pdftotext (poppler-utils)
```bash
pdftotext input.pdf output.txt              # Extract text
pdftotext -layout input.pdf output.txt      # Preserve layout
pdftotext -f 1 -l 5 input.pdf output.txt   # Pages 1-5
```

### qpdf
```bash
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf   # Merge
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf             # Split
qpdf input.pdf output.pdf --rotate=+90:1                 # Rotate page 1
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf  # Decrypt
```

### pdftk
```bash
pdftk file1.pdf file2.pdf cat output merged.pdf  # Merge
pdftk input.pdf burst                            # Split
pdftk input.pdf rotate 1east output rotated.pdf  # Rotate
```

---

## Common Tasks

### OCR Scanned PDFs
```python
import pytesseract
from pdf2image import convert_from_path

images = convert_from_path('scanned.pdf')
text = ""
for i, image in enumerate(images):
    text += f"Page {i+1}:\n"
    text += pytesseract.image_to_string(image)
    text += "\n\n"
```

### Extract Images
```bash
pdfimages -j input.pdf output_prefix
# Creates output_prefix-000.jpg, output_prefix-001.jpg, etc.
```

---

## Color Palettes (for reportlab creation — pick one matching the TOPIC)

- **Midnight Executive**: title 1E2761, heading 408EC6, body 212121, accent 7A2048
- **Forest & Moss**: title 2C5F2D, heading 4E8C53, body 333333, accent 97BC62
- **Ocean Depth**: title 065A82, heading 1C7293, body 2D3436, accent 00B4D8
- **Warm Terracotta**: title B85042, heading E7653C, body 3D3D3D, accent A7BEAE
- **Charcoal Minimal**: title 36454F, heading 5C7080, body 212121, accent 028090

## Typography (for reportlab creation)

| Element | Font | Size | Notes |
|---------|------|------|-------|
| Title | Helvetica-Bold | 24pt | Primary color, spaceAfter=6 |
| Subtitle | Helvetica | 13pt | Muted gray (#5C7080), spaceAfter=20 |
| Section heading | Helvetica-Bold | 15pt | Secondary color, spaceBefore=20 |
| Body | Helvetica | 11pt | leading=16, spaceAfter=8 |
| Bullets | Helvetica | 11pt | leftIndent=20, bulletIndent=10, "•  " prefix |

## Rules

- NEVER use unicode subscripts (₀₁₂) — they render as black boxes
- Use Spacer(1, 12) between sections, Spacer(1, 20) before new topics
- Use HRFlowable for visual breaks between major sections
- Save to `./data/filename.pdf`

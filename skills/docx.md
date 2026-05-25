# DOCX Skill

## Overview

A .docx file is a ZIP archive containing XML files.

## Quick Reference

| Task | Approach |
|------|----------|
| Read/analyze content | `pandoc` or unpack for raw XML |
| Create new document | Use `docx-js` (JavaScript) — see Creating New Documents below |
| Edit existing document | Unpack → edit XML → repack — see Editing below |

### Reading Content

```bash
# Text extraction with tracked changes
pandoc --track-changes=all document.docx -o output.md

# Raw XML access
python scripts/office/unpack.py document.docx unpacked/
```

### Converting to Images

```bash
python scripts/office/soffice.py --headless --convert-to pdf document.docx
pdftoppm -jpeg -r 150 document.pdf page
```

### Converting .doc to .docx

```bash
python scripts/office/soffice.py --headless --convert-to docx document.doc
```

---

## Creating New Documents (docx-js)

Install: `npm install -g docx`

### Setup

```javascript
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
        Header, Footer, AlignmentType, PageOrientation, LevelFormat, ExternalHyperlink,
        InternalHyperlink, Bookmark, FootnoteReferenceRun, PositionalTab,
        PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader,
        TabStopType, TabStopPosition, Column, SectionType,
        TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
        VerticalAlign, PageNumber, PageBreak } = require('docx');

const doc = new Document({ sections: [{ children: [/* content */] }] });
Packer.toBuffer(doc).then(buffer => fs.writeFileSync("doc.docx", buffer));
```

### Validation

```bash
python scripts/office/validate.py doc.docx
```

### Page Size

```javascript
// CRITICAL: docx-js defaults to A4, not US Letter
sections: [{
  properties: {
    page: {
      size: { width: 12240, height: 15840 },  // 8.5" × 11" in DXA (1440 DXA = 1 inch)
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }  // 1" margins
    }
  },
  children: [/* content */]
}]
```

Common sizes (DXA): US Letter 12240×15840, A4 11906×16838.

**Landscape**: Pass portrait dimensions + `orientation: PageOrientation.LANDSCAPE` (docx-js swaps internally).

### Styles (Override Built-in Headings)

```javascript
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 24 } } },  // 12pt default
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Title")] }),
    ]
  }]
});
```

### Lists (NEVER use unicode bullets)

```javascript
// ❌ WRONG
new Paragraph({ children: [new TextRun("• Item")] })  // BAD

// ✅ CORRECT - use numbering config with LevelFormat.BULLET
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Bullet item")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Numbered item")] }),
    ]
  }]
});
```

### Tables

**CRITICAL: Tables need dual widths** — set both `columnWidths` AND `width` on each cell.

```javascript
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

new Table({
  width: { size: 9360, type: WidthType.DXA },  // Always use DXA (percentages break in Google Docs)
  columnWidths: [4680, 4680],  // Must sum to table width
  rows: [
    new TableRow({
      children: [
        new TableCell({
          borders,
          width: { size: 4680, type: WidthType.DXA },
          shading: { fill: "D5E8F0", type: ShadingType.CLEAR },  // CLEAR not SOLID
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun("Cell")] })]
        })
      ]
    })
  ]
})
```

**Width rules:**
- Always use `WidthType.DXA` — never `WidthType.PERCENTAGE`
- Table width = sum of `columnWidths`
- Cell `width` must match corresponding `columnWidth`
- US Letter with 1" margins: content width = 9360 DXA

### Images

```javascript
// CRITICAL: type parameter is REQUIRED
new Paragraph({
  children: [new ImageRun({
    type: "png",  // Required: png, jpg, jpeg, gif, bmp, svg
    data: fs.readFileSync("image.png"),
    transformation: { width: 200, height: 150 },
    altText: { title: "Title", description: "Desc", name: "Name" }  // All three required
  })]
})
```

### Page Breaks

```javascript
// PageBreak must be inside a Paragraph
new Paragraph({ children: [new PageBreak()] })
// Or use pageBreakBefore
new Paragraph({ pageBreakBefore: true, children: [new TextRun("New page")] })
```

### Hyperlinks

```javascript
// External
new Paragraph({ children: [new ExternalHyperlink({
  children: [new TextRun({ text: "Click here", style: "Hyperlink" })],
  link: "https://example.com",
})]})

// Internal (bookmark + reference)
new Paragraph({ heading: HeadingLevel.HEADING_1, children: [
  new Bookmark({ id: "chapter1", children: [new TextRun("Chapter 1")] }),
]})
new Paragraph({ children: [new InternalHyperlink({
  children: [new TextRun({ text: "See Chapter 1", style: "Hyperlink" })],
  anchor: "chapter1",
})]})
```

### Footnotes

```javascript
const doc = new Document({
  footnotes: {
    1: { children: [new Paragraph("Source: Annual Report 2024")] },
    2: { children: [new Paragraph("See appendix for methodology")] },
  },
  sections: [{
    children: [new Paragraph({
      children: [
        new TextRun("Revenue grew 15%"),
        new FootnoteReferenceRun(1),
        new TextRun(" using adjusted metrics"),
        new FootnoteReferenceRun(2),
      ],
    })]
  }]
});
```

### Tab Stops

```javascript
// Right-align text on same line
new Paragraph({
  children: [new TextRun("Company Name"), new TextRun("\tJanuary 2025")],
  tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
})

// Dot leader (TOC-style)
new Paragraph({
  children: [
    new TextRun("Introduction"),
    new TextRun({ children: [
      new PositionalTab({
        alignment: PositionalTabAlignment.RIGHT,
        relativeTo: PositionalTabRelativeTo.MARGIN,
        leader: PositionalTabLeader.DOT,
      }), "3",
    ]}),
  ],
})
```

### Multi-Column Layouts

```javascript
// Equal-width columns
sections: [{
  properties: {
    column: { count: 2, space: 720, equalWidth: true, separate: true },
  },
  children: [/* content flows across columns */]
}]

// Custom-width columns
sections: [{
  properties: {
    column: {
      equalWidth: false,
      children: [new Column({ width: 5400, space: 720 }), new Column({ width: 3240 })],
    },
  },
  children: [/* content */]
}]
```

### Table of Contents

```javascript
// CRITICAL: Headings must use HeadingLevel ONLY - no custom styles
new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" })
```

### Headers/Footers

```javascript
sections: [{
  properties: { page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
  headers: {
    default: new Header({ children: [new Paragraph({ children: [new TextRun("Header")] })] })
  },
  footers: {
    default: new Footer({ children: [new Paragraph({
      children: [new TextRun("Page "), new TextRun({ children: [PageNumber.CURRENT] })]
    })] })
  },
  children: [/* content */]
}]
```

---

## Editing Existing Documents

**Follow all 3 steps in order.**

### Step 1: Unpack

```bash
python scripts/office/unpack.py document.docx unpacked/
```

Extracts XML, pretty-prints, merges adjacent runs, converts smart quotes to XML entities.

### Step 2: Edit XML

Edit files in `unpacked/word/`. Use the Edit tool directly — do NOT write Python scripts.

**Smart quotes for new content:**
```xml
<w:t>Here&#x2019;s a quote: &#x201C;Hello&#x201D;</w:t>
```

| Entity | Character |
|--------|-----------|
| `&#x2018;` | ' (left single) |
| `&#x2019;` | ' (right single / apostrophe) |
| `&#x201C;` | " (left double) |
| `&#x201D;` | " (right double) |

**Adding comments:**
```bash
python scripts/comment.py unpacked/ 0 "Comment text"
python scripts/comment.py unpacked/ 1 "Reply text" --parent 0
```

### Step 3: Pack

```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```

### Tracked Changes

```xml
<!-- Insertion -->
<w:ins w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:t>inserted text</w:t></w:r>
</w:ins>

<!-- Deletion (use w:delText, not w:t) -->
<w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>

<!-- Minimal edit: change "30 days" to "60 days" -->
<w:r><w:t>The term is </w:t></w:r>
<w:del w:id="1" w:author="Claude" w:date="...">
  <w:r><w:delText>30</w:delText></w:r>
</w:del>
<w:ins w:id="2" w:author="Claude" w:date="...">
  <w:r><w:t>60</w:t></w:r>
</w:ins>
<w:r><w:t> days.</w:t></w:r>
```

### XML Schema Rules

- **Element order in `<w:pPr>`**: `<w:pStyle>`, `<w:numPr>`, `<w:spacing>`, `<w:ind>`, `<w:jc>`, `<w:rPr>` last
- **Whitespace**: Add `xml:space="preserve"` to `<w:t>` with leading/trailing spaces
- **RSIDs**: Must be 8-digit hex (e.g., `00AB1234`)
- **Comments**: `<w:commentRangeStart>` and `<w:commentRangeEnd>` are siblings of `<w:r>`, never inside

### Common Pitfalls

- **Replace entire `<w:r>` elements** for tracked changes — don't inject tags inside a run
- **Preserve `<w:rPr>` formatting** — copy original run's formatting into tracked change runs
- **Multi-item content**: Create separate `<a:p>` elements — never concatenate
- **Never use tables as dividers** — use `border: { bottom: { style: BorderStyle.SINGLE } }` on Paragraph
- **Never use `\n`** — use separate Paragraph elements

---

## Critical Rules (docx-js)

- Set page size explicitly (defaults to A4)
- Landscape: pass portrait dimensions, docx-js swaps internally
- Never use unicode bullets — use `LevelFormat.BULLET`
- PageBreak must be in Paragraph
- ImageRun requires `type` parameter
- Always use `WidthType.DXA` — never PERCENTAGE
- Tables need dual widths: `columnWidths` + cell `width`
- Use `ShadingType.CLEAR` — never SOLID
- TOC requires HeadingLevel only — no custom styles
- Override built-in styles with exact IDs: "Heading1", "Heading2"
- Include `outlineLevel` for TOC (0 for H1, 1 for H2)

---

## Dependencies

- **pandoc** — text extraction
- **docx**: `npm install -g docx` — new documents
- **LibreOffice** — PDF conversion via `scripts/office/soffice.py`
- **Poppler** — `pdftoppm` for images

Save output to `./data/filename.docx`

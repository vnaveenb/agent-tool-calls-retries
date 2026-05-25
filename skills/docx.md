# DOCX Creation Guide (python-docx)

Use python-docx. Set default font Arial 11pt on styles['Normal']. Margins: Cm(2.54) all sides.

## Color Themes (pick one matching the TOPIC)

- **Midnight Executive**: heading 1E2761, subheading 408EC6, accent CADCFC, table header 1E2761
- **Forest & Moss**: heading 2C5F2D, subheading 4E8C53, accent 97BC62, table header 2C5F2D
- **Ocean Depth**: heading 065A82, subheading 1C7293, accent 00B4D8, table header 065A82
- **Warm Terracotta**: heading B85042, subheading E7653C, accent A7BEAE, table header B85042
- **Charcoal Minimal**: heading 36454F, subheading 5C7080, accent 028090, table header 36454F

## Typography
- Title: heading level=0, font Arial 28pt bold, primary color
- Heading 1: Arial 22pt bold, primary color, space_before=Pt(24)
- Heading 2: Arial 16pt bold, secondary color, space_before=Pt(18)
- Heading 3: Arial 13pt bold, muted (#5C7080), space_before=Pt(12)
- Body: Arial 11pt, color #212121, space_after=Pt(8)

## Document Structure
1. Title (level=0) + italic subtitle paragraph
2. Horizontal line separator (w:pBdr with w:bottom)
3. 3-6 major sections using Heading 1
4. Subsections using Heading 2/3
5. Conclusion section

## Lists
- Bullets: `doc.add_paragraph(text, style='List Bullet')` — NEVER use unicode bullets (•, ▪)
- Numbers: `doc.add_paragraph(text, style='List Number')`

## Tables
- Set BOTH column.width AND cell.width (setting only one won't work)
- Header row: bold white text, dark BG using w:shd element
- Alternate rows: white + #F5F7FA shading
- Use `from docx.oxml.ns import qn` and `OxmlElement('w:shd')` for cell shading

## Rules
- NEVER use unicode bullets — always use built-in styles
- Set BOTH column AND cell widths for tables
- Use heading styles (level=1,2,3) not bold paragraphs
- Page breaks (`doc.add_page_break()`) between major sections
- Write at least 4-6 sections with substantial content (3+ sentences each)
- Save to `./data/filename.docx`

# PDF Creation Guide (reportlab)

Use reportlab Platypus (SimpleDocTemplate, not Canvas). Letter pagesize, margins 72pt all sides.

## Color Palettes (pick one matching the TOPIC)

- **Midnight Executive**: title 1E2761, heading 408EC6, body 212121, accent 7A2048
- **Forest & Moss**: title 2C5F2D, heading 4E8C53, body 333333, accent 97BC62
- **Ocean Depth**: title 065A82, heading 1C7293, body 2D3436, accent 00B4D8
- **Warm Terracotta**: title B85042, heading E7653C, body 3D3D3D, accent A7BEAE
- **Charcoal Minimal**: title 36454F, heading 5C7080, body 212121, accent 028090

## Typography
- Title: Helvetica-Bold 24pt, primary color, spaceAfter=6
- Subtitle: Helvetica 13pt, muted gray (#5C7080), spaceAfter=20
- Section heading: Helvetica-Bold 15pt, secondary color, spaceBefore=20, spaceAfter=10
- Body: Helvetica 11pt, leading=16, body color, spaceAfter=8
- Bullets: leftIndent=20, bulletIndent=10, use "•  " prefix

## Document Structure
1. Title + subtitle + HRFlowable(width="100%", thickness=1.5, color=heading_color)
2. Introduction paragraph
3. 3-5 content sections (heading + body + bullets)
4. Conclusion section

## Tables
- Header row: dark BG (primary color), white bold text
- Alternating row shading: white + #F5F7FA
- Grid lines: 0.5pt, #CCCCCC
- Padding: 8pt top/bottom, 10pt left

## Rules
- NEVER use unicode subscripts (₀₁₂) — they render as black boxes
- Use Spacer(1, 12) between sections, Spacer(1, 20) before new topics
- Write at least 4-6 real sections with substantial content
- Use HRFlowable for visual breaks between major sections
- Save to `./data/filename.pdf`

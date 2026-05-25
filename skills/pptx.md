# PPTX Creation Guide (python-pptx)

Use python-pptx. Widescreen 16:9: `prs.slide_width = Inches(13.333)`, `prs.slide_height = Inches(7.5)`.

## Color Palettes (pick one matching the TOPIC)

- **Midnight Executive**: BG 1E2761, text FFFFFF, accent CADCFC, light F8F9FA, body 2D3436
- **Forest & Moss**: BG 2C5F2D, text FFFFFF, accent 97BC62, light F5F7F2, body 333333
- **Ocean Gradient**: BG 065A82, text FFFFFF, accent 00B4D8, light F0F8FF, body 1B2838
- **Teal Trust**: BG 028090, text FFFFFF, accent 02C39A, light F0FDFA, body 1A1A2E
- **Warm Terracotta**: BG B85042, text FFFFFF, accent E7E8D1, light FBF8F3, body 3D3D3D

## Typography
- Titles: Calibri 36-44pt bold
- Body: Calibri 16-18pt, space_after=Pt(12)
- Captions: Calibri 10-12pt, muted color

## Slide Structure (mandatory order)
1. Title slide — dark BG, white title 44pt centered, subtitle 18pt muted
2. Agenda — 3-5 topics
3. Content slides (3-6) — VARY layouts below
4. Key Takeaways
5. Thank You — dark BG closing

## Layout Patterns (vary, never repeat consecutively)
- **Bullets**: slide_layouts[1], max 5 bullets, Pt(18) body
- **Two-column**: slide_layouts[5] blank, textbox left + shape right
- **Big stat**: slide_layouts[5], giant number Pt(72) centered + label Pt(20) below
- **Process flow**: slide_layouts[5], 3 rounded rectangles side by side with steps

## Dark slides (title + closing)
Use `slide.background.fill.solid()` + `fill.fore_color.rgb = RGBColor(...)` for dark BG.
White text on dark: `font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)`.

## Rules
- MAX 5 bullets per slide. Split if more.
- 0.5" min margins from edges
- Vary layouts — never repeat same layout consecutively
- Every slide needs visual structure (shapes, colors) not just text
- Dark title slide → light content → dark closing ("sandwich")
- Left-align body, center only titles
- Save to `./data/filename.pptx`

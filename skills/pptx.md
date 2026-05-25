# PPTX Skill

## Quick Reference

| Task | Method |
|------|--------|
| Read/analyze content | `python -m markitdown presentation.pptx` |
| Edit or create from template | See [Editing Workflow](#editing-workflow) |
| Create from scratch | See [PptxGenJS Creation](#creating-from-scratch-pptxgenjs) |

---

## Reading Content

```bash
# Text extraction
python -m markitdown presentation.pptx

# Visual overview (thumbnail grid)
python scripts/thumbnail.py presentation.pptx

# Raw XML inspection
python scripts/office/unpack.py presentation.pptx unpacked/
```

---

## Editing Workflow (Template-Based)

1. **Analyze existing slides**:
   ```bash
   python scripts/thumbnail.py template.pptx
   python -m markitdown template.pptx
   ```

2. **Plan slide mapping**: For each content section, choose a template slide.
   - Use VARIED layouts — don't default to basic title + bullet slides
   - Seek out: multi-column, image+text, full-bleed, quote, stat callouts, icon grids

3. **Unpack**: `python scripts/office/unpack.py template.pptx unpacked/`

4. **Build presentation**:
   - Delete unwanted slides (remove from `<p:sldIdLst>`)
   - Duplicate slides to reuse (`python scripts/add_slide.py unpacked/ slide2.xml`)
   - Reorder slides in `<p:sldIdLst>`
   - Complete all structural changes before editing content

5. **Edit content**: Update text in each `slide{N}.xml`

6. **Clean**: `python scripts/clean.py unpacked/`

7. **Pack**: `python scripts/office/pack.py unpacked/ output.pptx --original template.pptx`

### Editing Rules
- **Bold all headers, subheadings, and inline labels**: Use `b="1"` on `<a:rPr>`
- **Never use unicode bullets (•)**: Use proper `<a:buChar>` or `<a:buAutoNum>`
- **Multi-item content**: Create separate `<a:p>` elements — never concatenate into one string
- **Smart quotes**: Use XML entities (`&#x201C;`, `&#x201D;`, `&#x2018;`, `&#x2019;`)
- **Whitespace**: Use `xml:space="preserve"` on `<a:t>` with leading/trailing spaces

---

## Creating from Scratch (PptxGenJS)

### Setup & Basic Structure

```javascript
const pptxgen = require("pptxgenjs");

let pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';  // 10" × 5.625"
// Options: 'LAYOUT_16x10' (10"×6.25"), 'LAYOUT_4x3' (10"×7.5"), 'LAYOUT_WIDE' (13.3"×7.5")
pres.author = 'Your Name';
pres.title = 'Presentation Title';

let slide = pres.addSlide();
slide.addText("Hello World!", { x: 0.5, y: 0.5, fontSize: 36, color: "363636" });

pres.writeFile({ fileName: "output.pptx" });
```

### Text & Formatting

```javascript
// Basic text
slide.addText("Title", {
  x: 1, y: 1, w: 8, h: 2, fontSize: 24, fontFace: "Arial",
  color: "363636", bold: true, align: "center", valign: "middle"
});

// Character spacing
slide.addText("SPACED TEXT", { x: 1, y: 1, w: 8, h: 1, charSpacing: 6 });

// Rich text arrays
slide.addText([
  { text: "Bold ", options: { bold: true } },
  { text: "Italic ", options: { italic: true } }
], { x: 1, y: 3, w: 8, h: 1 });

// Multi-line text (requires breakLine: true)
slide.addText([
  { text: "Line 1", options: { breakLine: true } },
  { text: "Line 2", options: { breakLine: true } },
  { text: "Line 3" }
], { x: 0.5, y: 0.5, w: 8, h: 2 });

// Text box margin (internal padding)
slide.addText("Title", {
  x: 0.5, y: 0.3, w: 9, h: 0.6,
  margin: 0  // Use 0 when aligning text with shapes/icons
});
```

### Lists & Bullets

```javascript
// ✅ CORRECT: Multiple bullets
slide.addText([
  { text: "First item", options: { bullet: true, breakLine: true } },
  { text: "Second item", options: { bullet: true, breakLine: true } },
  { text: "Third item", options: { bullet: true } }
], { x: 0.5, y: 0.5, w: 8, h: 3 });

// ❌ WRONG: Never use unicode bullets
slide.addText("• First item", { ... });  // Creates double bullets

// Sub-items and numbered lists
{ text: "Sub-item", options: { bullet: true, indentLevel: 1 } }
{ text: "First", options: { bullet: { type: "number" }, breakLine: true } }
```

### Shapes

```javascript
slide.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 0.8, w: 1.5, h: 3.0,
  fill: { color: "FF0000" }, line: { color: "000000", width: 2 }
});

slide.addShape(pres.shapes.OVAL, { x: 4, y: 1, w: 2, h: 2, fill: { color: "0000FF" } });

slide.addShape(pres.shapes.LINE, {
  x: 1, y: 3, w: 5, h: 0, line: { color: "FF0000", width: 3, dashType: "dash" }
});

// Rounded rectangle
slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x: 1, y: 1, w: 3, h: 2,
  fill: { color: "FFFFFF" }, rectRadius: 0.1
});

// With shadow
slide.addShape(pres.shapes.RECTANGLE, {
  x: 1, y: 1, w: 3, h: 2,
  fill: { color: "FFFFFF" },
  shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.15 }
});
```

Shadow options: `type` ("outer"/"inner"), `color` (6-char hex), `blur` (0-100pt), `offset` (must be non-negative), `angle` (0-359), `opacity` (0.0-1.0).

### Images

```javascript
// From file path
slide.addImage({ path: "images/chart.png", x: 1, y: 1, w: 5, h: 3 });

// From base64 (faster, no file I/O)
slide.addImage({ data: "image/png;base64,iVBORw0KGgo...", x: 1, y: 1, w: 5, h: 3 });

// Image options
slide.addImage({
  path: "image.png", x: 1, y: 1, w: 5, h: 3,
  rotate: 45, rounding: true, transparency: 50,
  altText: "Description"
});

// Sizing modes
{ sizing: { type: 'contain', w: 4, h: 3 } }  // Fit inside, preserve ratio
{ sizing: { type: 'cover', w: 4, h: 3 } }    // Fill area, may crop
```

### Icons (react-icons → PNG)

```javascript
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const { FaCheckCircle } = require("react-icons/fa");

function renderIconSvg(IconComponent, color = "#000000", size = 256) {
  return ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color, size: String(size) })
  );
}

async function iconToBase64Png(IconComponent, color, size = 256) {
  const svg = renderIconSvg(IconComponent, color, size);
  const pngBuffer = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + pngBuffer.toString("base64");
}

// Usage
const iconData = await iconToBase64Png(FaCheckCircle, "#4472C4", 256);
slide.addImage({ data: iconData, x: 1, y: 1, w: 0.5, h: 0.5 });
```

Install: `npm install -g react-icons react react-dom sharp`

### Slide Backgrounds

```javascript
slide.background = { color: "F1F1F1" };                      // Solid
slide.background = { color: "FF3399", transparency: 50 };    // With transparency
slide.background = { path: "https://example.com/bg.jpg" };   // Image
slide.background = { data: "image/png;base64,..." };         // Base64
```

### Charts

```javascript
// Bar chart
slide.addChart(pres.charts.BAR, [{
  name: "Sales", labels: ["Q1", "Q2", "Q3", "Q4"], values: [4500, 5500, 6200, 7100]
}], { x: 0.5, y: 0.6, w: 6, h: 3, barDir: 'col' });

// Modern styled chart
slide.addChart(pres.charts.BAR, chartData, {
  x: 0.5, y: 1, w: 9, h: 4, barDir: "col",
  chartColors: ["0D9488", "14B8A6", "5EEAD4"],
  chartArea: { fill: { color: "FFFFFF" }, roundedCorners: true },
  catAxisLabelColor: "64748B", valAxisLabelColor: "64748B",
  valGridLine: { color: "E2E8F0", size: 0.5 },
  catGridLine: { style: "none" },
  showValue: true, dataLabelPosition: "outEnd", dataLabelColor: "1E293B",
  showLegend: false,
});
```

Chart types: BAR, LINE, PIE, DOUGHNUT, SCATTER, BUBBLE, RADAR

### Tables

```javascript
slide.addTable([
  ["Header 1", "Header 2"],
  ["Cell 1", "Cell 2"]
], {
  x: 1, y: 1, w: 8, h: 2,
  border: { pt: 1, color: "999999" }, fill: { color: "F1F1F1" }
});
```

### Slide Masters

```javascript
pres.defineSlideMaster({
  title: 'TITLE_SLIDE', background: { color: '283A5E' },
  objects: [{
    placeholder: { options: { name: 'title', type: 'title', x: 1, y: 2, w: 8, h: 2 } }
  }]
});

let titleSlide = pres.addSlide({ masterName: "TITLE_SLIDE" });
titleSlide.addText("My Title", { placeholder: "title" });
```

---

## Design Ideas

**Don't create boring slides.** Plain bullets on white won't impress. Every slide needs a visual element.

### Color Palettes (pick one matching the TOPIC)

| Theme | Primary | Secondary | Accent |
|-------|---------|-----------|--------|
| **Midnight Executive** | `1E2761` (navy) | `CADCFC` (ice blue) | `FFFFFF` (white) |
| **Forest & Moss** | `2C5F2D` (forest) | `97BC62` (moss) | `F5F5F5` (cream) |
| **Coral Energy** | `F96167` (coral) | `F9E795` (gold) | `2F3C7E` (navy) |
| **Warm Terracotta** | `B85042` (terracotta) | `E7E8D1` (sand) | `A7BEAE` (sage) |
| **Ocean Gradient** | `065A82` (deep blue) | `1C7293` (teal) | `21295C` (midnight) |
| **Charcoal Minimal** | `36454F` (charcoal) | `F2F2F2` (off-white) | `212121` (black) |
| **Teal Trust** | `028090` (teal) | `00A896` (seafoam) | `02C39A` (mint) |
| **Berry & Cream** | `6D2E46` (berry) | `A26769` (dusty rose) | `ECE2D0` (cream) |
| **Sage Calm** | `84B59F` (sage) | `69A297` (eucalyptus) | `50808E` (slate) |
| **Cherry Bold** | `990011` (cherry) | `FCF6F5` (off-white) | `2F3C7E` (navy) |

### Design Principles
- **Dominance over equality**: One color dominates (60-70%), 1-2 supporting tones, one sharp accent
- **Dark/light contrast**: Dark backgrounds for title + conclusion ("sandwich" structure), light for content
- **Commit to a visual motif**: Pick ONE distinctive element and repeat — rounded frames, icons in circles, thick borders

### Typography

| Header Font | Body Font |
|-------------|-----------|
| Georgia | Calibri |
| Arial Black | Arial |
| Calibri | Calibri Light |
| Cambria | Calibri |
| Trebuchet MS | Calibri |

---

## python-pptx (Python) — Common Errors & Fixes

Use this section to avoid the most frequent runtime errors when generating PPTX with `python-pptx`.

### Imports

```python
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_VERTICAL_ANCHOR  # NOT pptx.enum.shapes
from pptx.enum.shapes import MSO_SHAPE_TYPE               # for shape type checks only
from pptx.oxml.ns import qn                               # for direct XML manipulation
```

### Vertical Anchor — ALWAYS use the enum, never a string

```python
# ✅ CORRECT
from pptx.enum.text import MSO_VERTICAL_ANCHOR
tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE   # TOP | MIDDLE | BOTTOM

# ❌ WRONG — raises ValueError: 'middle' is not a valid MSO_VERTICAL_ANCHOR
tf.vertical_anchor = 'middle'
```

### add_shape() — positional args only, no keyword fill/line

```python
# ✅ CORRECT — (shape_type, left, top, width, height)
shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1), Inches(1), Inches(4), Inches(2))
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0x2F, 0x3C, 0x7E)
shape.line.fill.background()  # transparent line

# ❌ WRONG — add_shape() does not accept fill= or line= kwargs
slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, ..., fill=...)
```

### Shape fill & line patterns

```python
shape.fill.solid()                         # solid color fill
shape.fill.fore_color.rgb = RGBColor(...)  # set the color after .solid()
shape.fill.background()                    # transparent / no fill

shape.line.color.rgb = RGBColor(0x99, 0, 0x11)  # solid border color
shape.line.width = Pt(1.5)
shape.line.fill.background()               # remove border entirely
```

### MSO_SHAPE constants — import from pptx.enum.shapes

```python
from pptx.enum.shapes import MSO_SHAPE   # e.g. MSO_SHAPE.RECTANGLE, .ROUNDED_RECTANGLE, .RIGHT_ARROW
# Do NOT use string names — always use the enum attribute
```

### Text frame — line spacing and paragraph spacing

```python
from pptx.util import Pt
from pptx.oxml.ns import qn
from lxml import etree

# Set space after paragraph (safe approach)
p = tf.add_paragraph()
pPr = p._p.get_or_add_pPr()
pPr.set(qn('a:spcAft'), None)  # clear first if needed
# OR use paragraph spacing directly:
p.space_after = Pt(6)
p.space_before = Pt(0)
```

### Widescreen slide dimensions

```python
prs = Presentation()
prs.slide_width  = Inches(16)   # 16:9 widescreen
prs.slide_height = Inches(9)
# Use layout index 6 (blank) for full custom control:
slide = prs.slides.add_slide(prs.slide_layouts[6])
```
| Palatino | Garamond |
| Consolas | Calibri |

| Element | Size |
|---------|------|
| Slide title | 36-44pt bold |
| Section header | 20-24pt bold |
| Body text | 14-16pt |
| Captions | 10-12pt muted |

### Layout Options (vary, never repeat consecutively)
- Two-column (text left, illustration right)
- Icon + text rows (icon in colored circle, bold header, description below)
- 2x2 or 2x3 grid (image one side, content blocks other)
- Half-bleed image with content overlay
- Large stat callouts (big numbers 60-72pt with small labels below)
- Comparison columns (before/after, pros/cons)
- Timeline or process flow (numbered steps, arrows)

### Slide Structure (mandatory order)
1. Title slide — dark BG, white title 44pt centered, subtitle 18pt muted
2. Agenda — 3-5 topics
3. Content slides (3-6) — VARY layouts
4. Key Takeaways
5. Thank You — dark BG closing

### Spacing
- 0.5" minimum margins from edges
- 0.3-0.5" between content blocks
- Leave breathing room — don't fill every inch

---

## Common Pitfalls (PptxGenJS)

1. **NEVER use "#" with hex colors** — causes file corruption: `"FF0000"` ✅ | `"#FF0000"` ❌
2. **NEVER encode opacity in hex color strings** — 8-char colors corrupt. Use `opacity` property instead
3. **Use `bullet: true`** — NEVER unicode "•" (creates double bullets)
4. **Use `breakLine: true`** between array items or text runs together
5. **Avoid `lineSpacing` with bullets** — use `paraSpaceAfter` instead
6. **Each presentation needs fresh instance** — don't reuse `pptxgen()` objects
7. **NEVER reuse option objects across calls** — PptxGenJS mutates objects in-place. Use factory functions:
   ```javascript
   const makeShadow = () => ({ type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.15 });
   slide.addShape(pres.shapes.RECTANGLE, { shadow: makeShadow(), ... });
   ```
8. **Don't use `ROUNDED_RECTANGLE` with accent borders** — rectangular overlays won't cover rounded corners
9. **NEVER use accent lines under titles** — hallmark of AI-generated slides; use whitespace or background color

---

## QA (Required)

**Assume there are problems. Your first render is almost never correct.**

### Content QA
```bash
python -m markitdown output.pptx
python -m markitdown output.pptx | grep -iE "xxxx|lorem|ipsum|this.*(page|slide).*layout"
```

### Visual QA
Convert slides to images, then inspect:
```bash
python scripts/office/soffice.py --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 150 output.pdf slide
```

Look for: overlapping elements, text overflow, decorative lines mispositioned, elements too close (<0.3"), uneven gaps, insufficient margins (<0.5"), low-contrast text/icons, leftover placeholder content.

### Verification Loop
1. Generate → Convert to images → Inspect
2. List issues found
3. Fix issues
4. Re-verify affected slides
5. Repeat until clean pass

---

## Dependencies

- `pip install "markitdown[pptx]"` — text extraction
- `pip install Pillow` — thumbnail grids
- `npm install -g pptxgenjs` — creating from scratch
- `npm install -g react-icons react react-dom sharp` — icons
- LibreOffice (`soffice`) — PDF conversion
- Poppler (`pdftoppm`) — PDF to images

Save output to `./data/filename.pptx`

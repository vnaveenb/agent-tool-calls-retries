# XLSX Skill — Creation, Editing, and Analysis

## Overview

Use this skill for any spreadsheet task: creating, reading, editing, or analyzing .xlsx, .xlsm, .csv, or .tsv files.

## Quick Reference

| Task | Best Tool |
|------|-----------|
| Data analysis & visualization | pandas |
| Complex formatting & formulas | openpyxl |
| Formula recalculation | `scripts/recalc.py` |

---

## CRITICAL: Use Formulas, Not Hardcoded Values

**Always use Excel formulas instead of calculating in Python and hardcoding.**

### ❌ WRONG — Hardcoding
```python
total = df['Sales'].sum()
sheet['B10'] = total  # Hardcodes 5000

growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth  # Hardcodes 0.15
```

### ✅ CORRECT — Excel Formulas
```python
sheet['B10'] = '=SUM(B2:B9)'
sheet['C5'] = '=(C4-C2)/C2'
sheet['D20'] = '=AVERAGE(D2:D19)'
```

---

## Reading and Analyzing Data

### pandas (data analysis)
```python
import pandas as pd

df = pd.read_excel('file.xlsx')                        # First sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # All sheets as dict

df.head()       # Preview
df.info()       # Column info
df.describe()   # Statistics

df.to_excel('output.xlsx', index=False)
```

---

## Common Workflow

1. **Choose tool**: pandas for data, openpyxl for formulas/formatting
2. **Create/Load**: Create new workbook or load existing
3. **Modify**: Add data, formulas, formatting
4. **Save**: Write to file
5. **Recalculate formulas (MANDATORY)**:
   ```bash
   python scripts/recalc.py output.xlsx
   ```
6. **Verify and fix errors** — script returns JSON with error details

---

## Creating New Excel Files

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# Add data
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

# Add formula
sheet['B2'] = '=SUM(A1:A10)'

# Formatting
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# Column width
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

---

## Editing Existing Excel Files

```python
from openpyxl import load_workbook

wb = load_workbook('existing.xlsx')
sheet = wb.active  # or wb['SheetName']

# Working with multiple sheets
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]

# Modify cells
sheet['A1'] = 'New Value'
sheet.insert_rows(2)
sheet.delete_cols(3)

# Add new sheet
new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

---

## Recalculating Formulas

```bash
python scripts/recalc.py <excel_file> [timeout_seconds]
python scripts/recalc.py output.xlsx 30
```

The script:
- Automatically sets up LibreOffice macro on first run
- Recalculates all formulas in all sheets
- Scans ALL cells for Excel errors
- Returns JSON with detailed error locations

### Interpreting Output
```json
{
  "status": "success",
  "total_errors": 0,
  "total_formulas": 42,
  "error_summary": {
    "#REF!": { "count": 2, "locations": ["Sheet1!B5", "Sheet1!C10"] }
  }
}
```

---

## Financial Models

### Color Coding Standards (Industry-Standard)

| Color | Usage |
|-------|-------|
| **Blue text** (0,0,255) | Hardcoded inputs, scenario variables |
| **Black text** (0,0,0) | ALL formulas and calculations |
| **Green text** (0,128,0) | Links from other worksheets |
| **Red text** (255,0,0) | External links to other files |
| **Yellow background** (255,255,0) | Key assumptions needing attention |

### Number Formatting Standards

- **Years**: Format as text ("2024" not "2,024")
- **Currency**: `$#,##0` — always specify units in headers ("Revenue ($mm)")
- **Zeros**: Format all zeros as "-" including percentages (`$#,##0;($#,##0);-`)
- **Percentages**: Default `0.0%` (one decimal)
- **Multiples**: `0.0x` for valuation (EV/EBITDA, P/E)
- **Negative numbers**: Use parentheses `(123)` not minus `-123`

### Formula Construction Rules

- Place ALL assumptions in separate cells — use cell references, not hardcoded values
- Example: `=B5*(1+$B$6)` instead of `=B5*1.05`
- Verify all cell references are correct
- Check for off-by-one errors in ranges
- Ensure consistent formulas across projection periods
- No unintended circular references

### Documentation for Hardcodes

Format: "Source: [System/Document], [Date], [Specific Reference], [URL if applicable]"
- "Source: Company 10-K, FY2024, Page 45, Revenue Note"
- "Source: Bloomberg Terminal, 8/15/2025, AAPL US Equity"

---

## Formula Verification Checklist

### Essential Verification
- [ ] Test 2-3 sample references before building full model
- [ ] Column mapping confirmed (column 64 = BL, not BK)
- [ ] Row offset: Excel rows are 1-indexed (DataFrame row 5 = Excel row 6)

### Common Pitfalls
- [ ] NaN handling: check with `pd.notna()`
- [ ] Far-right columns: FY data often in columns 50+
- [ ] Division by zero: check denominators (#DIV/0!)
- [ ] Cross-sheet references: correct format (`Sheet1!A1`)

---

## Best Practices

### Library Selection
- **pandas**: Data analysis, bulk operations, simple data export
- **openpyxl**: Complex formatting, formulas, Excel-specific features

### Working with openpyxl
- Cell indices are 1-based (row=1, column=1 = A1)
- `data_only=True` reads calculated values but **destroys formulas if saved**
- `read_only=True` / `write_only=True` for large files
- Formulas preserved but not evaluated — use `scripts/recalc.py`

### Working with pandas
- Specify data types: `pd.read_excel('file.xlsx', dtype={'id': str})`
- Large files: `pd.read_excel('file.xlsx', usecols=['A', 'C', 'E'])`
- Handle dates: `pd.read_excel('file.xlsx', parse_dates=['date_column'])`

---

## Requirements for All Excel Outputs

- Use professional font (Arial, Times New Roman) unless instructed otherwise
- Every model MUST have ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)
- Preserve existing templates — match existing format/style/conventions when modifying
- Existing template conventions ALWAYS override these guidelines

---

## Code Style

- Write minimal, concise Python code
- Avoid verbose variable names and redundant operations
- Add comments to cells with complex formulas
- Document data sources for hardcoded values

Save output to `./data/filename.xlsx`

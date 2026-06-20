"""PDF export with mandatory disclaimer injection.

Uses fpdf2 (MIT) for pure-Python PDF generation.
Every page footer contains the disclaimer from DISCLAIMER.md.

Note: Full Chinese PDF support requires a CJK font file (e.g., NotoSansSC).
When no CJK font is available, non-ASCII characters are replaced with '?'.
For production-quality Chinese PDF reports, use the Markdown export with
pandoc/wkhtmltopdf (configured in the Docker image).
"""

from __future__ import annotations

from pathlib import Path
from fpdf import FPDF

from src.compliance.disclaimer import get_pdf_footer_text, get_footer_text


# Unicode CJK font path (auto-detect, prefer single TTF over TTC)
import re

_CJK_FONT_PATH = None
for _candidate in [
    # Project-bundled font (users can place any CJK .ttf here)
    Path(__file__).resolve().parent / "fonts" / "cjk_font.ttf",
    # Windows single TTF fonts (avoid .ttc collections)
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simfang.ttf",
    "C:/Windows/Fonts/simkai.ttf",
    # Linux (Docker: apt install fonts-noto-cjk)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
]:
    if Path(_candidate).exists():
        _CJK_FONT_PATH = str(_candidate)
        break


def _clean_emoji(text: str) -> str:
    """Remove emoji and special symbols that CJK fonts lack."""
    return re.sub(r'[\U0001F300-\U0001F9FF☀-➿︀-️─-╿]', '', text)


def export_report_pdf(
    report_text: str,
    output_path: str | Path,
    title: str = "QuantSage 研究报告",
) -> Path:
    """Export a report to PDF with disclaimer footer on every page."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean emoji/special chars that CJK fonts lack
    report_text = _clean_emoji(report_text)
    title = _clean_emoji(title)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Load CJK font if available
    use_cjk = False
    if _CJK_FONT_PATH:
        try:
            pdf.add_font("CJK", fname=_CJK_FONT_PATH)
            use_cjk = True
        except Exception:
            pass
    font_name = "CJK" if use_cjk else "Helvetica"

    # Title
    pdf.set_font(font_name, "", 18)
    pdf.set_text_color(30, 30, 50)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    # Disclaimer notice at top
    pdf.set_font(font_name, "", 9)
    pdf.set_text_color(180, 60, 60)
    pdf.cell(0, 5, get_footer_text(), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Body: parse markdown lines
    pdf.set_text_color(40, 40, 40)

    for line in report_text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("```"):
            continue

        if stripped.startswith("# "):
            pdf.set_font(font_name, "", 16)
            pdf.ln(4)
            pdf.cell(0, 8, stripped[2:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif stripped.startswith("## "):
            pdf.set_font(font_name, "", 13)
            pdf.ln(3)
            pdf.cell(0, 7, stripped[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif stripped.startswith("### "):
            pdf.set_font(font_name, "", 11)
            pdf.ln(2)
            pdf.cell(0, 6, stripped[4:], new_x="LMARGIN", new_y="NEXT")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.set_font(font_name, "", 10)
            pdf.cell(8, 5, "  ")
            pdf.cell(0, 5, "  " + stripped[2:], new_x="LMARGIN", new_y="NEXT")
        elif stripped.startswith(">"):
            pdf.set_font(font_name, "", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, stripped[1:].strip(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(40, 40, 40)
        elif stripped == "---":
            pdf.set_draw_color(180, 180, 180)
            y = pdf.get_y()
            pdf.line(10, y, 200, y)
            pdf.ln(4)
        elif stripped:
            pdf.set_font(font_name, "", 10)
            clean = stripped.replace("**", "").replace("*", "").replace("`", "")
            pdf.cell(0, 5, clean, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.ln(3)

    # Footer disclaimer on last page
    pdf.set_y(-15)
    pdf.set_font(font_name, "", 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 10, get_pdf_footer_text(), align="C")

    pdf.output(str(output_path))
    return output_path


def export_report_markdown(
    report_text: str,
    output_path: str | Path,
) -> Path:
    """Export report as markdown file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
    return output_path

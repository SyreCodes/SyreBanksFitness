from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from app.providers.payments import CURRENCY_FACTORS

font_root = Path(__file__).resolve().parents[1] / "assets" / "fonts"
pdfmetrics.registerFont(TTFont("InvoiceSans", str(font_root / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("InvoiceBold", str(font_root / "DejaVuSans-Bold.ttf")))


def invoice_pdf(invoice: Any, client: Any, brand: dict[str, Any]) -> bytes:
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=A4)
    canvas.setTitle(f"Invoice {invoice.number} - Syre Banks Fitness")
    width, height = A4
    ink = colors.HexColor("#152018")
    muted = colors.HexColor("#677367")
    lime = colors.HexColor("#D7F65A")
    margin = 48
    y = height - 54

    def text(value: str, x: float, top: float, size: int = 10, bold: bool = False, color=ink) -> None:
        canvas.setFillColor(color)
        canvas.setFont("InvoiceBold" if bold else "InvoiceSans", size)
        canvas.drawString(x, top, value)

    def footer() -> None:
        canvas.setStrokeColor(colors.HexColor("#DFE5DC"))
        canvas.line(margin, 74, width - margin, 74)
        text(str(brand.get("contact_email") or "syrefitness6@gmail.com"), margin, 55, 9, color=muted)
        text(f"Page {canvas.getPageNumber()}", width - margin - 45, 55, 9, color=muted)

    canvas.setFillColor(lime)
    canvas.roundRect(margin, y - 8, 6, 29, 3, fill=1, stroke=0)
    text("SYRE BANKS FITNESS", margin + 20, y + 6, 18, True)
    y -= 68
    text("INVOICE", margin, y, 30, True)
    text("PAID" if invoice.status == "PAID" else invoice.status, width - margin - 48, y + 4, 12, True)
    y -= 30
    text(invoice.number, margin, y, 10, color=muted)
    y -= 44
    text("BILL TO", margin, y, 9, True, muted)
    text("ISSUED (UTC)", width - margin - 150, y, 9, True, muted)
    y -= 22
    name_lines = simpleSplit(client.name, "InvoiceBold", 12, 270)
    for line in name_lines:
        text(line, margin, y, 12, True)
        y -= 18
    text(invoice.issued_at.strftime("%d %B %Y"), width - margin - 150, y + len(name_lines) * 18, 10)
    for line in simpleSplit(client.email, "InvoiceSans", 10, 270):
        text(line, margin, y, 10, color=muted)
        y -= 16
    y -= 44
    canvas.setFillColor(colors.HexColor("#F2F5EC"))
    canvas.roundRect(margin, y - 14, width - 2 * margin, 33, 5, fill=1, stroke=0)
    text("DESCRIPTION", margin + 12, y, 9, True, muted)
    text("QTY", width - margin - 147, y, 9, True, muted)
    text("AMOUNT", width - margin - 84, y, 9, True, muted)
    y -= 40
    factor = CURRENCY_FACTORS[invoice.currency]
    for item in invoice.items:
        lines = simpleSplit(str(item.get("name", "Coaching plan")), "InvoiceSans", 11, 300)
        if y - len(lines) * 17 < 180:
            footer()
            canvas.showPage()
            y = height - 70
            text("INVOICE (continued)", margin, y, 16, True)
            y -= 35
        for offset, line in enumerate(lines):
            text(line, margin + 12, y - offset * 17, 11)
        text(str(item.get("quantity", 1)), width - margin - 138, y, 11)
        canvas.setFont("InvoiceSans", 11)
        canvas.setFillColor(ink)
        amount = int(item.get("price_minor", invoice.amount_minor)) * int(item.get("quantity", 1)) / factor
        canvas.drawRightString(width - margin - 12, y, f"{amount:,.2f}" if factor == 100 else f"{amount:,.0f}")
        y -= max(35, len(lines) * 17 + 16)
    y -= 24
    canvas.setStrokeColor(colors.HexColor("#DFE5DC"))
    canvas.line(margin, y, width - margin, y)
    y -= 34
    text(f"TOTAL PAID ({invoice.currency})", margin + 12, y, 12, True)
    canvas.setFont("InvoiceBold", 18)
    canvas.setFillColor(ink)
    total = invoice.amount_minor / factor
    canvas.drawRightString(width - margin - 12, y, f"{total:,.2f}" if factor == 100 else f"{total:,.0f}")
    y -= 58
    text("Thank you for investing in your coaching journey.", margin + 12, y, 10, color=muted)
    y -= 18
    text("This receipt reflects a server-verified payment.", margin + 12, y, 9, color=muted)
    footer()
    canvas.save()
    return stream.getvalue()

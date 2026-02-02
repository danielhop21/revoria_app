from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Optional
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
LOGO_PATH = ASSETS_DIR / "logo_offset_santiago.png"

def _safe(d: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return d or {}


def _fmt_cm(x) -> str:
    try:
        return f"{float(x):.1f} cm"
    except Exception:
        return ""


def _fmt_int(x) -> str:
    try:
        return f"{int(x)}"
    except Exception:
        return ""


def build_quote_pdf_bytes(row: Dict[str, Any]) -> bytes:
    """
    PDF CLIENTE (comercial):
    - NO incluye costos internos ni breakdown ni config_snapshot
    - Sí incluye: código, fecha, usuario/rol creador, características del trabajo, precios (unitario/total)
    """

    inputs = _safe(row.get("inputs"))
    quote_code = str(row.get("quote_code") or "")
    created_at = str(row.get("created_at") or "")
    created_by = str(row.get("created_by") or "")
    created_role = str(row.get("created_role") or "")
    customer_name = row.get("customer_name")
    notes = row.get("notes")

    # Precios (comercial sí)
    price_unit = row.get("price_unit")
    price_total = row.get("price_total")
    currency = str(row.get("currency") or "MXN")

    # Características del trabajo (solo inputs “seguros”)
    tipo = str(inputs.get("tipo_producto") or "")
    ancho = inputs.get("ancho_final_cm")
    alto = inputs.get("alto_final_cm")
    factor_carta = inputs.get("factor_carta")

    lados = inputs.get("lados")
    n_tintas = inputs.get("n_tintas")

    tipo_papel = inputs.get("tipo_papel")
    gramaje = inputs.get("papel_gramaje_gm2")

    piezas_por_lado = inputs.get("piezas_por_lado")
    orient = inputs.get("orientacion")
    hojas_fisicas = inputs.get("hojas_fisicas")

    tiraje_txt = ""
    if tipo == "Extendido":
        tiraje_txt = f"{_fmt_int(inputs.get('tiraje_piezas'))} pzas"
        imp_txt = "Frente" if str(lados) == "1" else "Frente y vuelta"
    else:
        tiraje_txt = f"{_fmt_int(inputs.get('tiraje_libros'))} libros"
        pags = inputs.get("paginas_por_libro")
        if pags is not None:
            tiraje_txt += f" · {_fmt_int(pags)} pág interiores"
        imp_txt = "Frente y vuelta"

    # --- PDF ---
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    # --- Logo ---
    logo_h = 50  # alto en puntos
    logo_w = 140 # ancho aprox (ajusta si quieres)

    if LOGO_PATH.exists():
        c.drawImage(
            str(LOGO_PATH),
            50,
            H - 50 - logo_h,
            width=logo_w,
            height=logo_h,
            preserveAspectRatio=True,
            mask="auto",
        )

    y = H - 50 - logo_h - 20

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50 + logo_w + 20, y + 10, "Cotización Impresion Digital")

    c.setFont("Helvetica", 10)
    c.drawString(50 + logo_w + 20, y - 6, "Offset Santiago")


    y -= 22

    c.setFont("Helvetica", 10)
    if quote_code:
        c.drawString(50, y, f"ID: {quote_code}")
        y -= 14
    if created_at:
        c.drawString(50, y, f"Fecha: {created_at}")
        y -= 14

    # Quién generó (requisito)
    if created_by or created_role:
        c.drawString(50, y, f"Generó: {created_by} ({created_role})")
        y -= 14

    if customer_name:
        c.drawString(50, y, f"Cliente: {customer_name}")
        y -= 14

    if notes:
        c.drawString(50, y, f"Notas: {notes}")
        y -= 14

    y -= 8
    c.line(50, y, W - 50, y)
    y -= 22

    # Detalle comercial
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Características del trabajo")
    y -= 18
    c.setFont("Helvetica", 10)

    def line(label: str, value: str):
        nonlocal y
        if value:
            c.drawString(50, y, f"{label}: {value}")
            y -= 14

    line("Producto", tipo)
    line("Medida final", f"{_fmt_cm(ancho)} × {_fmt_cm(alto)}")
    if tiraje_txt:
        line("Tiraje", tiraje_txt)
    line("Impresión", imp_txt)
    if n_tintas is not None:
        line("Tintas", "CMYK (4)" if int(n_tintas) == 4 else "1 tinta")

    if tipo_papel:
        papel_txt = tipo_papel
        if gramaje is not None:
            try:
                papel_txt += f" · {float(gramaje):.0f} g/m²"
            except Exception:
                pass
        line("Papel", papel_txt)

    if piezas_por_lado is not None:
        line("Cubicación", f"{piezas_por_lado} por lado ({orient})")
    if hojas_fisicas is not None:
        line("Tabloides (papel)", _fmt_int(hojas_fisicas))

    if factor_carta is not None:
        try:
            line("Factor vs carta", f"{float(factor_carta):.4f}")
        except Exception:
            pass

    y -= 8
    c.line(50, y, W - 50, y)
    y -= 22

    # Precios (comercial)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Precios")
    y -= 18
    c.setFont("Helvetica", 10)

    def money(x, decimals=2) -> str:
        try:
            return f"{currency} ${float(x):,.{decimals}f}"
        except Exception:
            return ""

    line("Precio unitario", money(price_unit, decimals=4))
    line("Precio total", money(price_total, decimals=2))

    # Footer
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 40, "Documento generado por Revoria App — Cotización comercial (sin desglose de costos).")

    c.showPage()
    c.save()

    return buf.getvalue()

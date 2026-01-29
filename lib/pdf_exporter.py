import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

def _money(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return ""

def build_quote_pdf_bytes(row: dict) -> bytes:
    """
    PDF cliente (presentable). No incluye costos internos.
    Retorna bytes PDF.
    """
    inputs = row.get("inputs") or {}
    breakdown = row.get("breakdown") or {}
    tot = breakdown.get("totales") or {}

    quote_code = row.get("quote_code", "Q-UNKNOWN")
    currency = row.get("currency", "MXN")
    customer = (row.get("customer_name") or "").strip()
    notes = (row.get("notes") or "").strip()
    created_by = (row.get("created_by") or "").strip()

    tipo = inputs.get("tipo_producto", "")
    ancho = inputs.get("ancho_final_cm", "")
    alto = inputs.get("alto_final_cm", "")
    lados = inputs.get("lados", 2 if "Libro" in str(tipo) else 1)

    # Tirajes
    tiraje_piezas = inputs.get("tiraje_piezas")
    tiraje_libros = inputs.get("tiraje_libros")
    paginas_por_libro = inputs.get("paginas_por_libro")

    precio_total = tot.get("precio_total", row.get("price_total"))
    precio_unit = tot.get("precio_unitario", row.get("price_unit"))

    # ----------------------------
    # PDF setup
    # ----------------------------
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter
    left = 2.0 * cm
    right = W - 2.0 * cm
    y = H - 2.2 * cm

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, y, "Cotización — Fujifilm Revoria")
    c.setFont("Helvetica", 10)
    c.drawRightString(right, y, f"{currency}")
    y -= 0.8 * cm

    c.setFont("Helvetica", 9)
    c.drawString(left, y, f"Código: {quote_code}")
    c.drawRightString(right, y, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 0.55 * cm

    # Cliente / usuario
    if customer:
        c.drawString(left, y, f"Cliente: {customer}")
        y -= 0.45 * cm
    if created_by:
        c.drawString(left, y, f"Atendió: {created_by}")
        y -= 0.55 * cm

    # Línea
    c.line(left, y, right, y)
    y -= 0.7 * cm

    # Detalles del trabajo
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "Detalle del trabajo")
    y -= 0.6 * cm

    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Tipo: {tipo}")
    y -= 0.45 * cm

    c.drawString(left, y, f"Medida final: {ancho} × {alto} cm")
    y -= 0.45 * cm

    if str(tipo) == "Extendido":
        c.drawString(left, y, f"Tiraje: {tiraje_piezas} pzas")
        y -= 0.45 * cm
        imp_txt = "Frente" if int(lados) == 1 else "Frente y vuelta"
        c.drawString(left, y, f"Impresión: {imp_txt}")
        y -= 0.45 * cm
    else:
        c.drawString(left, y, f"Tiraje: {tiraje_libros} libros")
        y -= 0.45 * cm
        c.drawString(left, y, f"Páginas interiores por libro: {paginas_por_libro}")
        y -= 0.45 * cm
        c.drawString(left, y, "Impresión: Frente y vuelta")
        y -= 0.45 * cm

    y -= 0.2 * cm
    c.line(left, y, right, y)
    y -= 0.7 * cm

    # Precios
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "Precio")
    y -= 0.6 * cm

    c.setFont("Helvetica", 11)
    c.drawString(left, y, f"Precio unitario: {_money(precio_unit)}")
    y -= 0.5 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, f"Precio total: {_money(precio_total)}")
    y -= 0.7 * cm

    # Notas
    if notes:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left, y, "Notas")
        y -= 0.5 * cm
        c.setFont("Helvetica", 10)

        # wrap simple
        max_chars = 95
        for i in range(0, len(notes), max_chars):
            line = notes[i:i+max_chars]
            c.drawString(left, y, line)
            y -= 0.42 * cm
            if y < 3.0 * cm:
                c.showPage()
                y = H - 2.2 * cm
                c.setFont("Helvetica", 10)

        y -= 0.3 * cm

    # Footer / condiciones (fijo)
    if y < 3.3 * cm:
        c.showPage()
        y = H - 2.2 * cm

    c.setFont("Helvetica", 8)
    condiciones = [
        "Condiciones: precios en MXN. Vigencia: 7 días (ajustable).",
        "El tiempo de entrega y especificaciones finales se confirman al aprobar artes y materiales.",
    ]
    c.line(left, 2.8 * cm, right, 2.8 * cm)
    yy = 2.4 * cm
    for line in condiciones:
        c.drawString(left, yy, line)
        yy -= 0.35 * cm

    c.showPage()
    c.save()

    return buf.getvalue()

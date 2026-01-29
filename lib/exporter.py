import io
import pandas as pd
from datetime import datetime

def build_quote_excel_bytes(row: dict, role: str) -> bytes:
    inputs = row.get("inputs") or {}
    breakdown = row.get("breakdown") or {}

    quote_code = row.get("quote_code", "Q-UNKNOWN")
    currency = row.get("currency", "MXN")
    customer = row.get("customer_name") or ""
    notes = row.get("notes") or ""
    created_by = row.get("created_by") or ""

    tipo_producto = inputs.get("tipo_producto", "")
    ancho = inputs.get("ancho_final_cm", "")
    alto = inputs.get("alto_final_cm", "")
    lados = inputs.get("lados", 2 if "Libro" in str(tipo_producto) else 1)

    tot = breakdown.get("totales", {})
    precio_total = tot.get("precio_total", row.get("price_total"))
    precio_unit = tot.get("precio_unitario", row.get("price_unit"))

    # Tirajes
    tiraje_piezas = inputs.get("tiraje_piezas")
    tiraje_libros = inputs.get("tiraje_libros")
    paginas_por_libro = inputs.get("paginas_por_libro")

    # ----------------------------
    # Hoja 1: Cotización (Cliente)
    # ----------------------------
    rows_cliente = [
        ("Código", quote_code),
        ("Cliente", customer),
        ("Usuario", created_by),
        ("Fecha exportación", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Tipo de producto", tipo_producto),
        ("Medida final (cm)", f"{ancho} x {alto}"),
        ("Moneda", currency),
    ]

    if tipo_producto == "Extendido":
        rows_cliente += [
            ("Tiraje (pzas)", tiraje_piezas),
            ("Impresión", "Frente" if int(lados) == 1 else "Frente y vuelta"),
        ]
    else:
        rows_cliente += [
            ("Tiraje (libros)", tiraje_libros),
            ("Páginas interiores por libro", paginas_por_libro),
            ("Impresión", "Frente y vuelta"),
        ]

    rows_cliente += [
        ("Precio unitario", precio_unit),
        ("Precio total", precio_total),
        ("Notas", notes),
    ]

    df_cliente = pd.DataFrame(rows_cliente, columns=["Campo", "Valor"])

    # ----------------------------
    # Hoja 2: Desglose técnico (solo admin/cotizador)
    # ----------------------------
    can_see_detail = role in {"admin", "cotizador"}

    papel = breakdown.get("papel", {})
    imp = breakdown.get("impresion", {})
    adicionales = breakdown.get("adicionales", {})

    hojas_fisicas = inputs.get("hojas_fisicas", papel.get("hojas_fisicas"))
    clicks_maquina = inputs.get("clicks_maquina")

    # si no viene (como en libro), lo inferimos operativamente:
    if clicks_maquina is None and hojas_fisicas is not None:
        if tipo_producto == "Extendido":
            clicks_maquina = int(hojas_fisicas) * int(lados)
        else:
            clicks_maquina = int(hojas_fisicas) * 2

    rows_detalle = []

    def add(sec, concepto, valor):
        rows_detalle.append((sec, concepto, valor))

    # Operación
    add("Operación", "Tabloides (papel)", hojas_fisicas)
    add("Operación", "Clicks máquina (tabloide-lado)", clicks_maquina)
    add("Operación", "Carta-lado (facturable)", imp.get("unidades_carta_lado"))
    add("Operación", "Cubicación (pzas/pág por lado)", inputs.get("piezas_por_lado"))
    add("Operación", "Orientación", inputs.get("orientacion"))
    add("Operación", "Huella (cm)", f"{inputs.get('area_w_cm')} x {inputs.get('area_h_cm')}")
    add("Operación", "Hoja (cm)", f"{inputs.get('hoja_w_cm')} x {inputs.get('hoja_h_cm')}")
    add("Operación", "Bleed (cm)", inputs.get("bleed_cm"))
    add("Operación", "Gutter (cm)", inputs.get("gutter_cm"))

    # Impresión
    add("Impresión", "Costo unitario carta-lado", imp.get("costo_unitario_carta_lado"))
    add("Impresión", "Total impresión", imp.get("total"))

    # Papel
    add("Papel", "Hojas físicas", papel.get("hojas_fisicas", hojas_fisicas))
    add("Papel", "Costo hoja (con merma)", papel.get("costo_hoja_con_merma"))
    add("Papel", "Total papel", papel.get("total"))

    # Adicionales
    add("Adicionales", "Total adicionales", adicionales.get("total"))

    # Totales
    add("Totales", "Subtotal antes margen", tot.get("subtotal_antes_margen"))
    add("Totales", "Margen", tot.get("margen"))
    add("Totales", "Precio total", tot.get("precio_total", precio_total))

    df_detalle = pd.DataFrame(rows_detalle, columns=["Sección", "Concepto", "Valor"])

    # Hoja adicionales
    items_adic = adicionales.get("items") or []
    df_adic = pd.DataFrame(items_adic) if items_adic else pd.DataFrame(columns=["concepto", "importe"])

    # ----------------------------
    # Escribir Excel
    # ----------------------------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_cliente.to_excel(writer, index=False, sheet_name="Cotizacion (Cliente)")
        if can_see_detail:
            df_detalle.to_excel(writer, index=False, sheet_name="Desglose tecnico")
            df_adic.to_excel(writer, index=False, sheet_name="Adicionales")

    return output.getvalue()


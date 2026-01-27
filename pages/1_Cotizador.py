import math
import streamlit as st

# ---------------------------------
# Config
# ---------------------------------
st.set_page_config(page_title="Cotizador Fujifilm Revoria / Offset Santiago", layout="centered")

st.markdown("""
<style>
.small-metric { 
    font-size: 0.85rem; 
    opacity: 0.90;
    line-height: 1.2;
}
.small-metric b {
    font-size: 0.85rem;
}
.small-metric .val {
    font-size: 1.00rem;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# Base carta (cm) para costeo de impresión por "Carta-lado"
CARTA_W = 21.5
CARTA_H = 28.0
AREA_CARTA_CM2 = CARTA_W * CARTA_H  # 602 cm²

# Defaults de preprensa (hoja real y huella/área útil)
DEFAULT_HOJA_W = 48.0
DEFAULT_HOJA_H = 33.0
DEFAULT_AREA_W = 47.4
DEFAULT_AREA_H = 32.4

st.title("Cotizador Fujifilm Revoria / Offset Santiago")
st.caption("Impresión escala por área vs Carta. Papel y cubicación usan hoja 48×33 y huella 47.4×32.4 (defaults).")

# ---------------------------------
# Sidebar: parámetros
# ---------------------------------
with st.sidebar:
    st.header("Impresión (por Carta – 1 lado)")
    mo_dep = st.number_input("MO + Depreciación", min_value=0.0, value=0.06, step=0.01, format="%.4f")
    tinta = st.number_input("Tinta CMYK", min_value=0.0, value=0.39, step=0.01, format="%.4f")
    click = st.number_input("Click servicio", min_value=0.0, value=0.35, step=0.01, format="%.4f")
    cobertura = st.number_input("Cobertura", min_value=0.0, value=0.10, step=0.01, format="%.4f")

    st.divider()
    st.header("Papel")
    papel_costo_kg = st.number_input("Costo papel ($/kg)", min_value=0.0, value=21.0, step=0.5, format="%.2f")
    papel_gramaje = st.number_input("Gramaje (g/m²)", min_value=0.0, value=130.0, step=5.0, format="%.1f")
    merma_papel = st.number_input("Merma papel (%)", min_value=0.0, value=0.0, step=0.5, format="%.1f") / 100.0

    st.divider()
    st.header("Margen")
    margen = st.number_input("Margen (ej. 0.40 = 40%)", min_value=0.0, value=0.40, step=0.01, format="%.2f")

# ---------------------------------
# Helpers
# ---------------------------------
def factor_vs_carta(ancho_cm: float, alto_cm: float) -> float:
    """Escala lineal por área: área_final / área_carta."""
    return (ancho_cm * alto_cm) / AREA_CARTA_CM2

def calc_piezas_por_lado(
    area_w_cm: float,
    area_h_cm: float,
    pieza_w_cm: float,
    pieza_h_cm: float,
    gutter_cm: float,
    bleed_cm: float,
    allow_rotate: bool,
) -> tuple[int, str, float, float]:
    """
    Cubicación simple:
    - Tamaño efectivo = pieza + 2*bleed + gutter (aprox)
    - fit normal y fit rotado (si aplica)
    Retorna: (piezas_por_lado, orientacion, w_eff, h_eff)
    """
    w_eff = pieza_w_cm + 2 * bleed_cm + gutter_cm
    h_eff = pieza_h_cm + 2 * bleed_cm + gutter_cm

    if w_eff <= 0 or h_eff <= 0:
        return 0, "Inválido", w_eff, h_eff

    fit1 = int(area_w_cm // w_eff) * int(area_h_cm // h_eff)

    fit2 = 0
    if allow_rotate:
        fit2 = int(area_w_cm // h_eff) * int(area_h_cm // w_eff)

    if fit2 > fit1:
        return fit2, "Rotado 90°", w_eff, h_eff
    return fit1, "Normal", w_eff, h_eff

def paper_cost_for_sheet(w_cm: float, h_cm: float, gramaje_gm2: float, costo_kg: float) -> tuple[float, float, float]:
    """Devuelve (area_m2, peso_hoja_kg, costo_hoja)"""
    w_m = w_cm / 100.0
    h_m = h_cm / 100.0
    area_m2 = w_m * h_m
    peso_kg = area_m2 * gramaje_gm2 / 1000.0
    costo_hoja = peso_kg * costo_kg
    return area_m2, peso_kg, costo_hoja

# ---------------------------------
# Inputs principales
# ---------------------------------
tipo_producto = st.selectbox("Tipo de producto", ["Extendido", "Libro / Folleto (interiores)"])

st.subheader("Medida final (libre)")
colA, colB = st.columns(2)
with colA:
    ancho_final = st.number_input("Ancho final (cm)", min_value=1.0, value=21.5, step=0.1)
with colB:
    alto_final = st.number_input("Alto final (cm)", min_value=1.0, value=28.0, step=0.1)

factor_carta = factor_vs_carta(ancho_final, alto_final)
st.caption(f"Factor vs Carta (por área): **{factor_carta:.4f}** (Carta=1.0000)")

st.divider()

# ---------------------------------
# Parámetros de hoja/huella y cubicación (config por trabajo)
# ---------------------------------
with st.expander("Cubicación / hoja de impresión (config por trabajo)", expanded=False):
    st.caption("Defaults vienen de preprensa. Ajusta sangrado y separación según trabajo.")

    col1, col2 = st.columns(2)
    with col1:
        hoja_w = st.number_input("Hoja impresión ancho (cm)", value=DEFAULT_HOJA_W, step=0.5)
        hoja_h = st.number_input("Hoja impresión alto (cm)", value=DEFAULT_HOJA_H, step=0.5)
    with col2:
        area_w = st.number_input("Huella/área útil ancho (cm)", value=DEFAULT_AREA_W, step=0.1)
        area_h = st.number_input("Huella/área útil alto (cm)", value=DEFAULT_AREA_H, step=0.1)

    col3, col4, col5 = st.columns(3)
    with col3:
        bleed = st.number_input("Sangrado por lado (cm)", value=0.3, step=0.1)
    with col4:
        gutter = st.number_input("Separación entre piezas (cm)", value=0.2, step=0.1)
    with col5:
        allow_rotate = st.checkbox("Permitir rotación 90°", value=True)

# Cubicación (siempre calculada)
piezas_por_lado, orientacion, w_eff, h_eff = calc_piezas_por_lado(
    area_w, area_h,
    ancho_final, alto_final,
    gutter, bleed,
    allow_rotate
)

st.info(f"Cubicación estimada: **{piezas_por_lado} por lado** (orientación: **{orientacion}**)")

# ---------------------------------
# Restricciones por tipo de producto
# ---------------------------------
area_huella = area_w * area_h

# Para validar tamaño, usa "área efectiva" (incluye bleed). Gutter no debe entrar al criterio de doblado.
area_pieza_eff = (ancho_final + 2 * bleed) * (alto_final + 2 * bleed)

restriccion_ok = True
motivo = ""

# Regla general: debe caber al menos 1 pieza en la huella (con bleed + gutter)
if piezas_por_lado <= 0:
    restriccion_ok = False
    motivo = "La pieza no cabe en el área útil (huella) del tabloide con estos parámetros."

# Regla libro/folleto: para doblado, área final efectiva <= 50% del área útil
if tipo_producto == "Libro / Folleto (interiores)":
    if area_pieza_eff > 0.5 * area_huella:
        restriccion_ok = False
        motivo = "Para libro/folleto (doblado), el área final (con sangrado) debe ser ≤ 50% del área útil del tabloide."

if not restriccion_ok:
    st.error(motivo)
    st.stop()

# ---------------------------------
# Inputs de tiraje y lógica de unidades / hojas
# ---------------------------------
if tipo_producto == "Extendido":
    col1, col2 = st.columns(2)
    with col1:
        piezas = st.number_input("Tiraje (piezas)", min_value=1, value=1000, step=1)
    with col2:
        lados = st.radio("Impresión", [1, 2], format_func=lambda x: "Frente" if x == 1 else "Frente y vuelta", horizontal=True)

    # IMPRESIÓN (Carta-lado): piezas * factor_area * lados
    unidades_carta_lado = piezas * factor_carta * lados

    # PAPEL (hojas físicas): rendimiento por hoja depende de lados
    piezas_por_hoja = piezas_por_lado if lados == 1 else piezas_por_lado * 2
    hojas_fisicas = math.ceil(piezas / piezas_por_hoja)

    descripcion_producto = "Extendido"
    etiqueta_tiraje = "pzas"
    paginas = None

else:
    col1, col2 = st.columns(2)
    with col1:
        libros = st.number_input("Tiraje (libros)", min_value=1, value=4, step=1)
    with col2:
        paginas = st.number_input("Páginas interiores por libro", min_value=1, value=456, step=1,
                                  help="Solo interiores. 1 página = 1 lado impreso.")

    piezas = libros
    descripcion_producto = "Libro / Folleto (interiores)"
    etiqueta_tiraje = "libros"

    paginas_totales = libros * paginas

    # IMPRESIÓN (Carta-lado): páginas_totales * factor_area
    unidades_carta_lado = paginas_totales * factor_carta

    # PAPEL (FyV): páginas por hoja FyV = piezas_por_lado * 2
    paginas_por_hoja_fyv = piezas_por_lado * 2
    hojas_fisicas = math.ceil(paginas_totales / paginas_por_hoja_fyv)

# ---------------------------------
# Costos impresión
# ---------------------------------
costo_mo_dep = unidades_carta_lado * mo_dep
costo_tinta = unidades_carta_lado * tinta
costo_click = unidades_carta_lado * click
costo_cobertura = unidades_carta_lado * cobertura
costo_impresion = costo_mo_dep + costo_tinta + costo_click + costo_cobertura

# ---------------------------------
# Costo papel (siempre hoja de impresión)
# ---------------------------------
area_m2, peso_hoja_kg, costo_hoja = paper_cost_for_sheet(hoja_w, hoja_h, papel_gramaje, papel_costo_kg)
costo_papel = hojas_fisicas * costo_hoja * (1 + merma_papel)

# ---------------------------------
# Costos adicionales (manuales) – UI estable
# ---------------------------------
st.subheader("Costos adicionales (antes de margen)")

if "costos_adicionales" not in st.session_state:
    st.session_state.costos_adicionales = [
        {"Concepto": "Encuadernación", "Importe": 0.0},
        {"Concepto": "Barniz / Lam", "Importe": 0.0},
        {"Concepto": "Flete", "Importe": 0.0},
    ]

cbtn1, cbtn2 = st.columns([1, 1])
with cbtn1:
    if st.button("➕ Agregar concepto"):
        st.session_state.costos_adicionales.append({"Concepto": "", "Importe": 0.0})
        st.rerun()
with cbtn2:
    if st.button("🗑️ Borrar adicionales"):
        st.session_state.costos_adicionales = []
        st.rerun()

total_adicionales = 0.0

for i, row in enumerate(st.session_state.costos_adicionales):
    c1, c2, c3 = st.columns([3, 2, 1])
    concepto_key = f"concepto_{i}"
    importe_key = f"importe_{i}"

    with c1:
        st.text_input("Concepto", value=row.get("Concepto", ""), key=concepto_key, label_visibility="collapsed")
    with c2:
        st.number_input("Importe", min_value=0.0, step=1.0, value=float(row.get("Importe", 0.0)),
                        key=importe_key, label_visibility="collapsed")
    with c3:
        if st.button("❌", key=f"del_{i}"):
            st.session_state.costos_adicionales.pop(i)
            st.session_state.pop(concepto_key, None)
            st.session_state.pop(importe_key, None)
            st.rerun()

    concepto = str(st.session_state.get(concepto_key, "")).strip()
    importe = float(st.session_state.get(importe_key, 0.0))
    row["Concepto"] = concepto
    row["Importe"] = importe

    if concepto:
        total_adicionales += importe

# ---------------------------------
# Subtotal y precio
# ---------------------------------
subtotal_costos = costo_impresion + costo_papel + total_adicionales
precio_total = subtotal_costos * (1 + margen)
precio_unitario = precio_total / piezas

# ---------------------------------
# Resultados
# ---------------------------------
st.divider()
st.subheader("Resultados")

# IMPORTANTES (grandes)
cA, cB = st.columns(2)
with cA:
    st.metric("Precio unitario", f"${precio_unitario:,.4f}")
with cB:
    st.metric("Precio total", f"${precio_total:,.2f}")

st.divider()

# SECUNDARIOS (chicos)
c1, c2, c3, c4 = st.columns(4)

c1.markdown(f"""
<div class="small-metric">
<b>Unidades Carta-lado</b><br>
<span class="val">{unidades_carta_lado:,.2f}</span>
</div>
""", unsafe_allow_html=True)

c2.markdown(f"""
<div class="small-metric">
<b>Hojas físicas (papel)</b><br>
<span class="val">{hojas_fisicas:,.0f}</span>
</div>
""", unsafe_allow_html=True)

c3.markdown(f"""
<div class="small-metric">
<b>Costo impresión</b><br>
<span class="val">${costo_impresion:,.2f}</span>
</div>
""", unsafe_allow_html=True)

c4.markdown(f"""
<div class="small-metric">
<b>Costo papel</b><br>
<span class="val">${costo_papel:,.2f}</span>
</div>
""", unsafe_allow_html=True)

# Otra fila chica
c5, c6, c7 = st.columns(3)
c5.markdown(f"""
<div class="small-metric">
<b>Costos adicionales</b><br>
<span class="val">${total_adicionales:,.2f}</span>
</div>
""", unsafe_allow_html=True)

c6.markdown(f"""
<div class="small-metric">
<b>Subtotal (antes margen)</b><br>
<span class="val">${subtotal_costos:,.2f}</span>
</div>
""", unsafe_allow_html=True)

c7.markdown(f"""
<div class="small-metric">
<b>Margen aplicado</b><br>
<span class="val">{margen*100:.1f}%</span>
</div>
""", unsafe_allow_html=True)


# ---------------------------------
# Texto copiable
# ---------------------------------
texto = (
    f"Cotización Revoria\n"
    f"- Tipo de producto: {descripcion_producto}\n"
    f"- Medida final: {ancho_final:.2f} x {alto_final:.2f} cm\n"
    f"- Tiraje: {piezas:,} {'pzas' if tipo_producto == 'Extendido' else 'libros'}\n"
)

if tipo_producto == "Extendido":
    texto += f"- Impresión: {'Frente' if lados == 1 else 'Frente y vuelta'}\n"
else:
    texto += f"- Páginas interiores por libro: {paginas}\n"

texto += (
    f"- Cubicación: {piezas_por_lado} por lado ({orientacion}) | Huella {area_w:.1f} x {area_h:.1f} cm\n"
    f"- Hoja impresión: {hoja_w:.1f} x {hoja_h:.1f} cm\n"
    f"- Costo de impresión: ${costo_impresion:,.2f}\n"
    f"- Papel: {papel_gramaje:.0f} g/m² @ ${papel_costo_kg:,.2f}/kg (merma {merma_papel*100:.1f}%)\n"
    f"- Costo de papel: ${costo_papel:,.2f}\n"
)

if total_adicionales > 0:
    texto += "- Costos adicionales:\n"
    for r in st.session_state.costos_adicionales:
        concepto = str(r["Concepto"]).strip()
        importe = float(r["Importe"])
        if concepto and importe > 0:
            texto += f"  • {concepto}: ${importe:,.2f}\n"

texto += (
    f"- Subtotal costos (antes de margen): ${subtotal_costos:,.2f}\n"
    f"- Margen aplicado: {margen*100:.1f}%\n"
    f"- Precio unitario: ${precio_unitario:,.4f}\n"
    f"- Precio total: ${precio_total:,.2f}\n"
)

st.text_area("Texto para copiar (WhatsApp / correo)", value=texto, height=360)

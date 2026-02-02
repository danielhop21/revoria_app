import sys
from pathlib import Path
import math
import datetime as dt
import secrets
import string

import streamlit as st

# -------------------------------------------------
# Root / imports internos
# -------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]  # carpeta revoria_app
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import require_role
from lib.supa import get_supabase
from lib.config_store import get_config
from lib.ui import (
    inject_global_css, render_header,
    card_open, card_close, hr,
    section_open, section_close
)

# -------------------------------------------------
# Config (SIEMPRE primero)
# -------------------------------------------------
st.set_page_config(page_title="Cotizador Revoria — Offset Santiago", layout="centered")
inject_global_css()
require_role({"admin", "sales"})

render_header(
    "Cotizador Revoria",
    "Área vs Carta · Tabloide 48×33 · Huella 47.4×32.4"
)

# Base carta (cm) para costeo de impresión por "Carta-lado"
CARTA_W = 21.5
CARTA_H = 28.0
AREA_CARTA_CM2 = CARTA_W * CARTA_H  # 602 cm²

# Defaults de preprensa (hoja real y huella/área útil)
DEFAULT_HOJA_W = 48.0
DEFAULT_HOJA_H = 33.0
DEFAULT_AREA_W = 47.4
DEFAULT_AREA_H = 32.4

# ---------------------------------
# Config (desde Configuración)
# ---------------------------------
cfg = get_config()

# Validación mínima de config (fail-fast)
papel_cfg = cfg.get("papel", {})
for k in ("cuche_costo_kg", "bond_costo_kg", "especial_costo_kg", "merma"):
    if k not in papel_cfg:
        st.error(f"Config incompleta: falta papel.{k}. Revisa Configuración/Secrets.")
        st.stop()

# Papel: costos por tipo (CONFIG). Gramaje lo alimenta el usuario en cotización.
papel_costos_kg = {
    "Couché": float(cfg["papel"]["cuche_costo_kg"]),
    "Bond": float(cfg["papel"]["bond_costo_kg"]),
    "Especial": float(cfg["papel"]["especial_costo_kg"]),
}
merma_papel = float(cfg["papel"]["merma"])

margen = float(cfg["margen"]["margen"])

# -------------------------
# Parámetros (desde cfg)
# -------------------------
mo_dep = float(cfg["impresion"]["mo_dep"])

tinta_cmyk_base = float(cfg["impresion"].get(
    "tinta_cmyk_base", cfg["impresion"].get("tinta", 0.0)
))

click_base = float(cfg["impresion"].get(
    "click_base", cfg["impresion"].get("click", 0.0)
))

cobertura_op = float(cfg["impresion"].get(
    "cobertura_op", cfg["impresion"].get("cobertura", 0.0)
))

cov_base = float(cfg["impresion"].get("cobertura_tinta_base_pct", 7.5))

cov_base = max(cov_base, 0.0001)

# Evitar división por cero
cov_base = max(cov_base, 0.0001)

with st.expander("Ver configuración aplicada (solo lectura)", expanded=False):
    st.write({
        "MO+Dep (unit)": float(mo_dep),
        "Tinta CMYK base (unit)": float(tinta_cmyk_base),
        "Click base (unit)": float(click_base),
        "Cobertura operativa (unit)": float(cobertura_op),
        "Cobertura tinta base (%)": float(cov_base),

        "Tipo papel $/kg (Couché)": papel_costos_kg["Couché"],
        "Tipo papel $/kg (Bond)": papel_costos_kg["Bond"],
        "Tipo papel $/kg (Especial)": papel_costos_kg["Especial"],
        "Merma papel": merma_papel,
        "Margen": margen,
    })


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
    Cubicación:
    - Tamaño efectivo por pieza = pieza + 2*bleed
    - Considera gutter entre piezas con aproximación: floor((W+g)/(w+g))
    Retorna: (piezas_por_lado, orientacion, w_eff, h_eff)
    """
    w_eff = pieza_w_cm + 2 * bleed_cm
    h_eff = pieza_h_cm + 2 * bleed_cm

    if w_eff <= 0 or h_eff <= 0:
        return 0, "Inválido", w_eff, h_eff

    def fit(area_w: float, area_h: float, w: float, h: float, g: float) -> int:
        nx = int((area_w + g) // (w + g)) if (w + g) > 0 else 0
        ny = int((area_h + g) // (h + g)) if (h + g) > 0 else 0
        return max(nx, 0) * max(ny, 0)

    fit1 = fit(area_w_cm, area_h_cm, w_eff, h_eff, gutter_cm)

    fit2 = 0
    if allow_rotate:
        fit2 = fit(area_w_cm, area_h_cm, h_eff, w_eff, gutter_cm)

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

def make_quote_code() -> str:
    now = dt.datetime.now()
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"Q-{now:%Y%m%d-%H%M%S}-{suffix}"


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
# Papel (inputs del usuario)
# ---------------------------------
st.subheader("Papel")
colP1, colP2 = st.columns(2)
with colP1:
    tipo_papel = st.selectbox("Tipo de papel", ["Couché", "Bond", "Especial"])
with colP2:
    papel_gramaje = st.number_input("Gramaje (g/m²)", min_value=40.0, value=150.0, step=5.0)

papel_costo_kg = float(papel_costos_kg[tipo_papel])
st.caption(f"Costo aplicado: **${papel_costo_kg:,.2f}/kg** · Merma: **{merma_papel*100:.1f}%**")

st.divider()


# ---------------------------------
# Inputs de tiraje y lógica de unidades / hojas
# ---------------------------------
# Defaults para evitar variables no definidas
unidades_carta_lado = 0.0
hojas_fisicas = 0
paginas = None
paginas_totales = 0

if tipo_producto == "Extendido":
    col1, col2 = st.columns(2)
    with col1:
        piezas = st.number_input("Tiraje (piezas)", min_value=1, value=1000, step=1)
    with col2:
        lados = st.radio(
            "Impresión",
            [1, 2],
            format_func=lambda x: "Frente" if x == 1 else "Frente y vuelta",
            horizontal=True
        )

    # IMPRESIÓN (Carta-lado): piezas * factor_area * lados
    unidades_carta_lado = float(piezas) * float(factor_carta) * float(lados)

    # PAPEL: tabloides físicos (independiente de frente/FyV)
    piezas_por_hoja = int(piezas_por_lado)
    hojas_fisicas = math.ceil(int(piezas) / max(piezas_por_hoja, 1))

    descripcion_producto = "Extendido"
    etiqueta_tiraje = "pzas"

else:
    col1, col2 = st.columns(2)
    with col1:
        libros = st.number_input("Tiraje (libros)", min_value=1, value=4, step=1)
    with col2:
        paginas = st.number_input(
            "Páginas interiores por libro",
            min_value=1, value=456, step=1,
            help="Solo interiores. 1 página = 1 lado impreso."
        )

    piezas = int(libros)  # para precio_unitario
    descripcion_producto = "Libro / Folleto (interiores)"
    etiqueta_tiraje = "libros"

    paginas_totales = int(libros) * int(paginas)

    # IMPRESIÓN (Carta-lado): páginas_totales * factor_area
    unidades_carta_lado = float(paginas_totales) * float(factor_carta)

    # PAPEL (FyV): páginas por hoja FyV = piezas_por_lado * 2
    paginas_por_hoja_fyv = int(piezas_por_lado) * 2
    hojas_fisicas = math.ceil(int(paginas_totales) / max(paginas_por_hoja_fyv, 1))


# ---------------------------------
# Clicks: máquina vs facturable
# ---------------------------------
if tipo_producto == "Extendido":
    clicks_maquina = int(hojas_fisicas) * int(lados)     # tabloide-lado
    clicks_facturable = float(unidades_carta_lado)       # carta-lado
else:
    # Libro / interiores: siempre FyV
    clicks_maquina = int(hojas_fisicas) * 2              # tabloide-lado
    clicks_facturable = float(unidades_carta_lado)       # carta-lado


# -------------------------
# Selector de tintas (1 o 4)
# -------------------------
# (pon este input donde te convenga en UI)
n_tintas = st.radio("Tintas", [4, 1], horizontal=True, format_func=lambda x: "CMYK (4)" if x == 4 else "1 tinta")

factor_tintas = float(n_tintas) / 4.0
factor_cobertura = 1.0

tinta_unit = tinta_cmyk_base * factor_tintas * factor_cobertura
click_unit = click_base      * factor_tintas * factor_cobertura

# -------------------------
# Costos impresión
# -------------------------
costo_mo_dep = unidades_carta_lado * mo_dep
costo_tinta  = unidades_carta_lado * tinta_unit
costo_click  = unidades_carta_lado * click_unit
costo_cobertura_op = unidades_carta_lado * cobertura_op

costo_impresion = costo_mo_dep + costo_tinta + costo_click + costo_cobertura_op

# ---------------------------------
# Costo papel (siempre hoja de impresión)
# ---------------------------------
area_m2, peso_hoja_kg, costo_hoja = paper_cost_for_sheet(
    hoja_w, hoja_h, papel_gramaje, papel_costo_kg
)

# Merma aplicada en hojas enteras
hojas_con_merma = math.ceil(hojas_fisicas * (1 + merma_papel))
costo_papel = hojas_con_merma * costo_hoja


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
# Resultados (section)
# ---------------------------------
section_open()
st.subheader("Resultados")

# IMPORTANTES (grandes)
cA, cB = st.columns(2)
with cA:
    st.metric("Precio unitario", f"${precio_unitario:,.4f}")
with cB:
    st.metric("Precio total", f"${precio_total:,.2f}")

hr()

c1, c2, c3, c4, c5 = st.columns(5)

c1.markdown(f"""
<div class="small-metric">
<b>Unidades Carta-lado</b><br>
<span class="val">{unidades_carta_lado:,.0f}</span>
</div>
""", unsafe_allow_html=True)

c2.markdown(f"""
<div class="small-metric">
<b>Tabloides (papel)</b><br>
<span class="val">{hojas_fisicas:,.0f}</span>
</div>
""", unsafe_allow_html=True)

c3.markdown(f"""
<div class="small-metric">
<b>Clicks máquina</b><br>
<span class="val">{clicks_maquina:,.0f}</span>
</div>
""", unsafe_allow_html=True)

c4.markdown(f"""
<div class="small-metric">
<b>Clicks facturable</b><br>
<span class="val">{clicks_facturable:,.0f}</span>
</div>
""", unsafe_allow_html=True)

c5.markdown(f"""
<div class="small-metric">
<b>Costo impresión</b><br>
<span class="val">${costo_impresion:,.2f}</span>
</div>
""", unsafe_allow_html=True)

hr()

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

section_close()

st.divider()

section_open()
st.subheader("Guardar cotización")

if "auth" not in st.session_state or not st.session_state.auth.get("is_logged", False):
    st.warning("Inicia sesión desde Home para poder guardar cotizaciones.")
else:
    sb = get_supabase()

    if st.button("💾 Guardar cotización en historial"):
        quote_code = make_quote_code()
        created_by = st.session_state.auth.get("user")
        created_role = st.session_state.auth.get("role")

        # Snapshot de configuración para que NO cambie el pasado
        cfg_snapshot = copy.deepcopy(cfg)

        # Inputs (lo que el usuario metió)
        inputs_payload = {
            "tipo_producto": tipo_producto,
            "ancho_final_cm": float(ancho_final),
            "alto_final_cm": float(alto_final),
            "factor_carta": float(factor_carta),
            "hoja_w_cm": float(hoja_w),
            "hoja_h_cm": float(hoja_h),
            "area_w_cm": float(area_w),
            "area_h_cm": float(area_h),
            "bleed_cm": float(bleed),
            "gutter_cm": float(gutter),
            "allow_rotate": bool(allow_rotate),
            "piezas_por_lado": int(piezas_por_lado),
            "orientacion": orientacion,

            # Papel (inputs del usuario)
            "tipo_papel": tipo_papel,
            "papel_gramaje_gm2": float(papel_gramaje),
            "papel_costo_kg_aplicado": float(papel_costo_kg),

            "hojas_fisicas": int(hojas_fisicas),
            "clicks_maquina": int(clicks_maquina),
            "clicks_facturable": float(clicks_facturable),
            "hojas_con_merma": int(hojas_con_merma),
            "n_tintas": int(n_tintas),
            "cobertura_tinta_base_pct": float(cov_base),

        }

        if tipo_producto == "Extendido":
            inputs_payload.update({"tiraje_piezas": int(piezas), "lados": int(lados)})
        else:
            inputs_payload.update({
                "tiraje_libros": int(libros),
                "paginas_por_libro": int(paginas),
                "paginas_totales": int(paginas_totales),
                "lados": 2
            })

        # Costo unitario real por carta-lado (según n_tintas y cobertura vigente)
        costo_unitario_carta_lado = float(mo_dep + tinta_unit + click_unit + cobertura_op)

        # Guardar parámetros de impresión usados
        impresion_params = {
            "n_tintas": int(n_tintas),
            "factor_tintas": float(factor_tintas),
            "cobertura_tinta_base_pct": float(cov_base),
            "mo_dep_unit": float(mo_dep),
            "tinta_unit": float(tinta_unit),
            "click_unit": float(click_unit),
            "cobertura_op_unit": float(cobertura_op),
        }


        breakdown_payload = {
            "impresion": {
                "unidades_carta_lado": float(unidades_carta_lado),
                "costo_unitario_carta_lado": float(costo_unitario_carta_lado),
                "formula_costo": "total = unidades_carta_lado * costo_unitario_carta_lado",
                "total": float(costo_impresion),
                "params": impresion_params,

                # Métrica operativa (NO facturable)
                "clicks_maquina": int(clicks_maquina),
                "formula_clicks_maquina": "clicks_maquina = hojas_fisicas * lados (extendido) | hojas_fisicas * 2 (libro)"
            },

            "papel": {
                "tipo_papel": tipo_papel,
                "gramaje_gm2": float(papel_gramaje),
                "costo_kg": float(papel_costo_kg),

                "hojas_fisicas": int(hojas_fisicas),
                "hojas_con_merma": int(hojas_con_merma),
                "costo_hoja": float(costo_hoja),
                "merma": float(merma_papel),
                "formula": "hojas_con_merma = ceil(hojas_fisicas * (1 + merma)); total = hojas_con_merma * costo_hoja",
                "total": float(costo_papel),
            },

            "adicionales": {
                "total": float(total_adicionales),
                "formula": "total = suma(importes)",
                "items": [
                    {"concepto": r.get("Concepto", ""), "importe": float(r.get("Importe", 0.0))}
                    for r in st.session_state.get("costos_adicionales", [])
                    if str(r.get("Concepto", "")).strip()
                ]
            },

            "totales": {
                "subtotal_antes_margen": float(subtotal_costos),
                "margen": float(margen),
                "precio_unitario": float(precio_unitario),
                "precio_total": float(precio_total),
                "formula_precio": "precio_total = subtotal_antes_margen * (1 + margen)"
            }
        }

        row = {
            "quote_code": quote_code,
            "created_by": created_by,
            "created_role": created_role,
            "customer_name": None,
            "notes": None,
            "price_unit": float(precio_unitario),
            "price_total": float(precio_total),
            "currency": "MXN",
            "inputs": inputs_payload,
            "breakdown": breakdown_payload,
            "config_snapshot": cfg_snapshot
        }

        try:
            sb.table("quotes").insert(row).execute()
            st.success(f"Cotización guardada ✅ ID: {quote_code}")
        except Exception as e:
            st.error("No se pudo guardar en Supabase (revisa secrets / conexión).")
            st.exception(e)

section_close()


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
    f"- Papel: {tipo_papel} · {papel_gramaje:.0f} g/m² @ ${papel_costo_kg:,.2f}/kg (merma {merma_papel*100:.1f}%)\n"
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

section_open()
st.subheader("Texto para copiar")
st.text_area("Texto para copiar (WhatsApp / correo)", value=texto, height=360)
section_close()

import sys
from pathlib import Path
import math
import datetime as dt
import secrets
import string
import copy

import streamlit as st

# -------------------------------------------------
# Root / imports internos
# -------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]  # carpeta revoria_app
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth_users_yaml import require_login
from lib.permissions import permissions_for

from lib.supa import get_supabase
from lib.config_store import get_config
from lib.ui import (
    inject_global_css, render_header,
    hr, section_open, section_close
)

# -------------------------------------------------
# Config (SIEMPRE primero)
# -------------------------------------------------
st.set_page_config(page_title="Cotizador Revoria — Offset Santiago", layout="centered")
inject_global_css()

# Login gate + permisos
user = require_login()
perms = permissions_for(user.role)

# Back-compat: tu app venía usando st.session_state.auth
st.session_state.auth = {
    "is_logged": True,
    "user": user.username,
    "role": user.role,
}

render_header(
    "Cotizador Revoria",
    "Área vs Carta · Tabloide 48×33 · Huella 47.4×32.4"
)

# -------------------------------------------------
# Constantes
# -------------------------------------------------
CARTA_W = 21.5
CARTA_H = 28.0
AREA_CARTA_CM2 = CARTA_W * CARTA_H  # 602 cm²

DEFAULT_HOJA_W = 48.0
DEFAULT_HOJA_H = 33.0
DEFAULT_AREA_W = 47.4
DEFAULT_AREA_H = 32.4

# -------------------------------------------------
# Config (desde Configuración)
# -------------------------------------------------
cfg = get_config()

# Validación mínima (fail-fast)
papel_cfg = cfg.get("papel", {})
for k in ("cuche_costo_kg", "bond_costo_kg", "especial_costo_kg", "merma"):
    if k not in papel_cfg:
        st.error(f"Config incompleta: falta papel.{k}. Revisa Configuración/Secrets.")
        st.stop()

imp_cfg = cfg.get("impresion", {})
margen = float(cfg.get("margen", {}).get("margen", 0.0))

papel_costos_kg = {
    "Couché": float(cfg["papel"]["cuche_costo_kg"]),
    "Bond": float(cfg["papel"]["bond_costo_kg"]),
    "Especial": float(cfg["papel"]["especial_costo_kg"]),
}
merma_papel = float(cfg["papel"]["merma"])

# Parámetros impresión
mo_dep = float(imp_cfg.get("mo_dep", 0.0))
tinta_cmyk_base = float(imp_cfg.get("tinta_cmyk_base", imp_cfg.get("tinta", 0.0)))
click_base = float(imp_cfg.get("click_base", imp_cfg.get("click", 0.0)))
cobertura_op = float(imp_cfg.get("cobertura_op", imp_cfg.get("cobertura", 0.0)))
cov_base = float(imp_cfg.get("cobertura_tinta_base_pct", 7.5))
cov_base = max(cov_base, 0.0001)

if perms.can_view_costs:
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

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def factor_vs_carta(ancho_cm: float, alto_cm: float) -> float:
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

def compute_finish_cost(fdef: dict, metrics: dict, user_inputs: dict) -> dict:
    """
    Cambio clave:
    - Si basis == sheet_m2_total => SIEMPRE aplica coverage (default 1.0)
    """
    basis = fdef.get("basis")
    calc_type = fdef.get("calc_type")

    # 1) qty base
    if basis == "sheet_m2_total":
        qty = float(metrics.get("sheet_m2_total", 0.0))

        # Coverage SIEMPRE que sea m² (default 100%)
        coverage = float(user_inputs.get("coverage", 1.0))
        coverage = max(0.0, min(1.0, coverage))
        qty *= coverage

    elif basis == "sheets_total":
        qty = float(metrics.get("sheets_total", 0.0))
        mult = float(user_inputs.get("folds_per_sheet", 1.0))
        qty *= max(mult, 0.0)

    elif basis == "pieces_total":
        qty = float(metrics.get("pieces_total", 0.0))
        mult = float(user_inputs.get("mult_per_piece", 1.0))
        qty *= max(mult, 0.0)

    else:
        qty = 0.0

    # 2) rounding opcional
    rounding = fdef.get("qty_rounding", "none")
    qty_rounded = qty
    if rounding == "ceil_1000":
        qty_rounded = math.ceil(qty / 1000.0)

    rate = float(fdef.get("rate", 0.0))
    setup = float(fdef.get("setup", 0.0))
    minimum = float(fdef.get("minimum", 0.0))

    variable = rate * float(qty_rounded)

    # 3) plantillas
    if calc_type == "unit":
        total = variable
    elif calc_type == "min_or_unit":
        total = max(minimum, variable)
    elif calc_type == "setup_plus_unit":
        total = setup + variable
    elif calc_type == "setup_plus_min_or_unit":
        total = max(minimum, setup + variable)
    else:
        total = 0.0

    return {
        "qty_base": float(qty),
        "qty_used": float(qty_rounded),
        "rate": rate,
        "setup": setup,
        "minimum": minimum,
        "variable": float(variable),
        "total": float(total),
        "basis": basis,
        "calc_type": calc_type,
        "rounding": rounding,
    }

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

def build_text(
    perms,
    descripcion_producto, ancho_final, alto_final, piezas, tipo_producto,
    lados, paginas, piezas_por_lado, orientacion, area_w, area_h, hoja_w, hoja_h,
    costo_impresion, tipo_papel, papel_gramaje, papel_costo_kg, merma_papel, costo_papel,
    total_acabados, acabados_items,
    total_adicionales, costos_adicionales, subtotal_costos, margen, precio_unitario, precio_total
):
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
        f"- Papel: {tipo_papel} · {papel_gramaje:.0f} g/m²\n"
    )

    # Acabados
    items = (acabados_items or [])
    if items and float(total_acabados or 0.0) > 0:
        texto += "- Acabados:\n"
        for it in items:
            nombre = str(it.get("display_name", "")).strip()
            total_it = float(it.get("total", 0.0) or 0.0)
            if not nombre or total_it <= 0:
                continue
            if perms.can_view_costs:
                texto += f"  • {nombre}: ${total_it:,.2f}\n"
            else:
                texto += f"  • {nombre}\n"

    if perms.can_view_costs:
        texto += (
            f"- Costo de impresión: ${costo_impresion:,.2f}\n"
            f"- Papel: {tipo_papel} · {papel_gramaje:.0f} g/m² @ ${papel_costo_kg:,.2f}/kg (merma {merma_papel*100:.1f}%)\n"
            f"- Costo de papel: ${costo_papel:,.2f}\n"
        )

        if float(total_adicionales or 0.0) > 0:
            texto += "- Costos adicionales:\n"
            for r in (costos_adicionales or []):
                concepto = str(r.get("Concepto", "")).strip()
                importe = float(r.get("Importe", 0.0) or 0.0)
                if concepto and importe > 0:
                    texto += f"  • {concepto}: ${importe:,.2f}\n"

        texto += (
            f"- Subtotal costos (antes de margen): ${subtotal_costos:,.2f}\n"
            f"- Margen aplicado: {margen*100:.1f}%\n"
        )
    else:
        if float(total_adicionales or 0.0) > 0:
            texto += "- Conceptos adicionales:\n"
            for r in (costos_adicionales or []):
                concepto = str(r.get("Concepto", "")).strip()
                importe = float(r.get("Importe", 0.0) or 0.0)
                if concepto and importe > 0:
                    texto += f"  • {concepto}: ${importe:,.2f}\n"

    texto += (
        f"- Precio unitario: ${precio_unitario:,.4f}\n"
        f"- Precio total: ${precio_total:,.2f}\n"
    )
    return texto

def render_extras_manual() -> tuple[float, list]:
    st.subheader("Extras manuales")

    cbtn1, cbtn2 = st.columns([1, 1])
    with cbtn1:
        if st.button("➕ Agregar concepto", key="extras_add"):
            st.session_state.costos_adicionales.append({"Concepto": "", "Importe": 0.0})
            st.rerun()
    with cbtn2:
        if st.button("🗑️ Borrar extras", key="extras_clear"):
            st.session_state.costos_adicionales = []
            st.rerun()

    total_adicionales = 0.0

    for i, row in enumerate(st.session_state.costos_adicionales):
        c1, c2, c3 = st.columns([3, 2, 1])
        concepto_key = f"extras_concepto_{i}"
        importe_key = f"extras_importe_{i}"

        with c1:
            st.text_input("Concepto", value=row.get("Concepto", ""), key=concepto_key, label_visibility="collapsed")
        with c2:
            st.number_input(
                "Importe",
                min_value=0.0,
                step=1.0,
                value=float(row.get("Importe", 0.0)),
                key=importe_key,
                label_visibility="collapsed",
            )
        with c3:
            if st.button("❌", key=f"extras_del_{i}"):
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

    return float(total_adicionales), st.session_state.costos_adicionales

# -------------------------------------------------
# Inputs principales
# -------------------------------------------------
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

piezas_por_lado, orientacion, w_eff, h_eff = calc_piezas_por_lado(
    area_w, area_h,
    ancho_final, alto_final,
    gutter, bleed,
    allow_rotate
)
st.info(f"Cubicación estimada: **{piezas_por_lado} por lado** (orientación: **{orientacion}**)")

# Restricciones
area_huella = area_w * area_h
area_pieza_eff = (ancho_final + 2 * bleed) * (alto_final + 2 * bleed)

restriccion_ok = True
motivo = ""

if piezas_por_lado <= 0:
    restriccion_ok = False
    motivo = "La pieza no cabe en el área útil (huella) del tabloide con estos parámetros."

if tipo_producto == "Libro / Folleto (interiores)":
    if area_pieza_eff > 0.5 * area_huella:
        restriccion_ok = False
        motivo = "Para libro/folleto (doblado), el área final (con sangrado) debe ser ≤ 50% del área útil del tabloide."

if not restriccion_ok:
    st.error(motivo)
    st.stop()

# Papel
st.subheader("Papel")
colP1, colP2 = st.columns(2)
with colP1:
    tipo_papel = st.selectbox("Tipo de papel", ["Couché", "Bond", "Especial"])
with colP2:
    papel_gramaje = st.number_input("Gramaje (g/m²)", min_value=40.0, value=150.0, step=5.0)

papel_costo_kg = float(papel_costos_kg[tipo_papel])

if perms.can_view_costs:
    st.caption(f"Costo aplicado: **${papel_costo_kg:,.2f}/kg** · Merma: **{merma_papel*100:.1f}%**")
else:
    st.caption("Parámetros internos de papel aplicados automáticamente.")

st.divider()

# -------------------------------------------------
# Tiraje / hojas / unidades
# -------------------------------------------------
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

    unidades_carta_lado = float(piezas) * float(factor_carta) * float(lados)

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

    piezas = int(libros)
    descripcion_producto = "Libro / Folleto (interiores)"
    etiqueta_tiraje = "libros"

    paginas_totales = int(libros) * int(paginas)
    unidades_carta_lado = float(paginas_totales) * float(factor_carta)

    paginas_por_hoja_fyv = int(piezas_por_lado) * 2
    hojas_fisicas = math.ceil(int(paginas_totales) / max(paginas_por_hoja_fyv, 1))

# Métricas acabados
sheet_area_m2 = (float(hoja_w) / 100.0) * (float(hoja_h) / 100.0)
sheet_m2_total = sheet_area_m2 * int(hojas_fisicas)

quote_metrics = {
    "sheet_m2_total": float(sheet_m2_total),
    "sheets_total": int(hojas_fisicas),
    "pieces_total": int(piezas),
}

# Clicks
if tipo_producto == "Extendido":
    clicks_maquina = int(hojas_fisicas) * int(lados)
    clicks_facturable = float(unidades_carta_lado)
else:
    clicks_maquina = int(hojas_fisicas) * 2
    clicks_facturable = float(unidades_carta_lado)

# Tintas
n_tintas = st.radio("Tintas", [4, 1], horizontal=True, format_func=lambda x: "CMYK (4)" if x == 4 else "1 tinta")
factor_tintas = float(n_tintas) / 4.0

tinta_unit = tinta_cmyk_base * factor_tintas
click_unit = click_base * factor_tintas

# Costos impresión
costo_mo_dep = unidades_carta_lado * mo_dep
costo_tinta = unidades_carta_lado * tinta_unit
costo_click = unidades_carta_lado * click_unit
costo_cobertura_op = unidades_carta_lado * cobertura_op
costo_impresion = costo_mo_dep + costo_tinta + costo_click + costo_cobertura_op

# Costo papel
area_m2, peso_hoja_kg, costo_hoja = paper_cost_for_sheet(hoja_w, hoja_h, papel_gramaje, papel_costo_kg)
hojas_con_merma = math.ceil(hojas_fisicas * (1 + merma_papel))
costo_papel = hojas_con_merma * costo_hoja

# -------------------------------------------------
# Acabados
# -------------------------------------------------
def _add_finish_and_reset(fdef, preview, user_inputs, selectbox_key: str):
    st.session_state.acabados_items.append({
        "type": "computed",
        "finish_key": fdef["key"],
        "display_name": fdef["display_name"],
        "inputs": user_inputs,
        "total": float(preview["total"]),
        "breakdown": preview,
    })

    # reset select principal
    st.session_state[selectbox_key] = "__none__"

    # limpia inputs del acabado recién usado
    k = fdef.get("key", "")
    for kk in (f"cov_opt_{k}", f"cov_custom_{k}", f"folds_{k}"):
        st.session_state.pop(kk, None)

    st.rerun()

st.subheader("Acabados")
st.session_state.setdefault("acabados_items", [])

finishes_catalog = cfg.get("acabados")
if not isinstance(finishes_catalog, list):
    finishes_catalog = []

# Validación (no obligamos allow_partial ya)
required_keys = ["key", "display_name", "basis", "calc_type", "rate", "minimum", "setup", "qty_rounding"]
for i, f in enumerate(finishes_catalog):
    if not isinstance(f, dict):
        st.error(f"Config inválida: acabados[{i}] no es dict.")
        st.stop()
    missing = [k for k in required_keys if k not in f]
    if missing:
        st.error(f"Config inválida: acabados[{i}] ({f.get('display_name','sin nombre')}) le faltan: {', '.join(missing)}")
        st.stop()
    if "requires" in f and not isinstance(f["requires"], list):
        st.error(f"Config inválida: acabados[{i}] 'requires' debe ser lista.")
        st.stop()

options = [
    {"key": f.get("key", ""), "name": f.get("display_name", "")}
    for f in finishes_catalog
    if isinstance(f, dict) and str(f.get("key", "")).strip() and str(f.get("display_name", "")).strip()
]
key_to_name = {o["key"]: o["name"] for o in options}

if options:
    keys = ["__none__"] + [o["key"] for o in options]

    def _fmt_finish(k: str) -> str:
        if k == "__none__":
            return "— Selecciona —"
        return key_to_name.get(k, k)

    sel_key = st.selectbox(
        "Agregar acabado (catálogo)",
        keys,
        format_func=_fmt_finish,
        key="select_finish_key",
    )

    if sel_key and sel_key != "__none__":
        fdef = next((f for f in finishes_catalog if isinstance(f, dict) and f.get("key") == sel_key), None)
        if fdef is None:
            st.error("No se encontró el acabado seleccionado (revisa Configuración).")
            st.stop()

        user_inputs = {}

        # CAMBIO CLAVE: si basis es m², SIEMPRE pedir cobertura
        if fdef.get("basis") == "sheet_m2_total":
            cov_opt = st.selectbox("Cobertura", ["100%", "50%", "25%", "Custom"], key=f"cov_opt_{sel_key}")
            if cov_opt == "100%":
                user_inputs["coverage"] = 1.0
            elif cov_opt == "50%":
                user_inputs["coverage"] = 0.5
            elif cov_opt == "25%":
                user_inputs["coverage"] = 0.25
            else:
                user_inputs["coverage"] = st.slider(
                    "Cobertura custom (%)", 0, 100, 100, key=f"cov_custom_{sel_key}"
                ) / 100.0

        req = fdef.get("requires", []) or []
        if "folds_per_sheet" in req:
            user_inputs["folds_per_sheet"] = st.number_input(
                "Dobleces por pliego",
                min_value=1.0,
                step=1.0,
                value=1.0,
                key=f"folds_{sel_key}",
            )

        preview = compute_finish_cost(fdef, quote_metrics, user_inputs)
        st.caption(
            f"Base: {preview['basis']} | Qty: {preview['qty_used']:,.3f} | "
            f"Rate: ${preview['rate']:,.4f} | Total: ${preview['total']:,.2f}"
        )

        st.button(
            "➕ Añadir acabado",
            key=f"add_finish_{sel_key}",
            on_click=_add_finish_and_reset,
            args=(fdef, preview, user_inputs, "select_finish_key"),
        )
else:
    st.info("No hay catálogo de acabados. (Puedes agregar un acabado manual abajo).")

# ---------- Acabado manual (importe total) ----------
st.caption("Acabado Extra).")

st.session_state.setdefault("manual_acab_nombre", "")
st.session_state.setdefault("manual_acab_total", 0.0)

def _add_manual_acabado():
    n = str(st.session_state.get("manual_acab_nombre", "")).strip()
    a = float(st.session_state.get("manual_acab_total", 0.0) or 0.0)

    if not n:
        st.warning("Pon un nombre para el acabado manual.")
        return
    if a <= 0:
        st.warning("Pon un importe mayor a 0.")
        return

    st.session_state.acabados_items.append({
        "type": "manual_total",
        "display_name": n,
        "total": a,
        "breakdown": {"manual_total": True},
    })

    st.session_state["manual_acab_nombre"] = ""
    st.session_state["manual_acab_total"] = 0.0

with st.form("form_manual_acabado", clear_on_submit=False):
    cM1, cM2, cM3 = st.columns([3, 2, 1])
    with cM1:
        st.text_input("Nombre", key="manual_acab_nombre")
    with cM2:
        st.number_input("Importe total ($)", min_value=0.0, step=1.0, key="manual_acab_total")
    with cM3:
        st.form_submit_button("➕", on_click=_add_manual_acabado)

st.divider()

# ---------- Tabla + total acabados ----------
total_acabados = 0.0
if st.session_state.acabados_items:
    st.write("**Acabados agregados**")
    for i, it in enumerate(st.session_state.acabados_items):
        c1, c2, c3 = st.columns([4, 2, 1])
        with c1:
            st.write(it.get("display_name", ""))
        with c2:
            st.write(f"${float(it.get('total', 0.0)):,.2f}")
        with c3:
            if st.button("❌", key=f"del_finish_{i}"):
                st.session_state.acabados_items.pop(i)
                st.rerun()

        total_acabados += float(it.get("total", 0.0))

st.metric("Total acabados", f"${total_acabados:,.2f}")

# -------------------------------------------------
# Extras manuales (independientes de Acabados)
# -------------------------------------------------
st.session_state.setdefault("costos_adicionales", [])

extras_ya_capturados = any(
    str(r.get("Concepto", "")).strip() and float(r.get("Importe", 0.0)) > 0
    for r in st.session_state.costos_adicionales
)

if extras_ya_capturados:
    total_adicionales, _extras_items = render_extras_manual()
else:
    total_adicionales = 0.0
    _extras_items = st.session_state.costos_adicionales

# -------------------------------------------------
# Subtotal y precio
# -------------------------------------------------
subtotal_costos = costo_impresion + costo_papel + total_acabados + total_adicionales
precio_total = subtotal_costos * (1 + margen)
precio_unitario = precio_total / piezas

# -------------------------------------------------
# Resultados
# -------------------------------------------------
section_open()
st.subheader("Resultados")

cA, cB = st.columns(2)
with cA:
    st.metric("Precio unitario", f"${precio_unitario:,.4f}")
with cB:
    st.metric("Precio total", f"${precio_total:,.2f}")

hr()

c1, c2, c3, c4 = st.columns(4)

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

if perms.can_view_costs:
    hr()
    c5, c6, c7 = st.columns(3)

    c5.markdown(f"""
    <div class="small-metric">
    <b>Costo impresión</b><br>
    <span class="val">${costo_impresion:,.2f}</span>
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

# -------------------------------------------------
# Guardar cotización
# -------------------------------------------------
section_open()
st.subheader("Guardar cotización")

sb = get_supabase()

if st.button("💾 Guardar cotización en historial"):
    quote_code = make_quote_code()
    created_by = user.username
    created_role = user.role

    cfg_snapshot = copy.deepcopy(cfg)

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

        "tipo_papel": tipo_papel,
        "papel_gramaje_gm2": float(papel_gramaje),
        "papel_costo_kg_aplicado": float(papel_costo_kg),

        "hojas_fisicas": int(hojas_fisicas),
        "clicks_maquina": int(clicks_maquina),
        "clicks_facturable": float(clicks_facturable),
        "hojas_con_merma": int(hojas_con_merma),
        "n_tintas": int(n_tintas),
        "cobertura_tinta_base_pct": float(cov_base),

        "acabados_total": float(total_acabados),
        "acabados_items": st.session_state.get("acabados_items", []),
        "acabados_metrics": quote_metrics,

        "adicionales_total": float(total_adicionales),
        "adicionales_items": [
            {"concepto": r.get("Concepto", ""), "importe": float(r.get("Importe", 0.0))}
            for r in (st.session_state.get("costos_adicionales", []) or [])
            if str(r.get("Concepto", "")).strip()
        ],
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

    costo_unitario_carta_lado = float(mo_dep + tinta_unit + click_unit + cobertura_op)

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
            "clicks_maquina": int(clicks_maquina),
            "formula_clicks_maquina": "clicks_maquina = hojas_fisicas * lados (extendido) | hojas_fisicas * 2 (libro)"
        },
        "acabados": {
            "total": float(total_acabados),
            "items": st.session_state.get("acabados_items", []),
            "metrics": quote_metrics,
            "formula": "total = suma(items.total)"
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
                for r in (st.session_state.get("costos_adicionales", []) or [])
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

    if perms.can_view_costs:
        cfg_snapshot_to_save = cfg_snapshot
        breakdown_to_save = breakdown_payload
    else:
        cfg_snapshot_to_save = None
        inputs_payload.pop("papel_costo_kg_aplicado", None)

        breakdown_to_save = {
            "impresion": {
                "unidades_carta_lado": float(unidades_carta_lado),
                "clicks_maquina": int(clicks_maquina),
                "clicks_facturable": float(clicks_facturable),
                "n_tintas": int(n_tintas),
            },
            "papel": {
                "tipo_papel": tipo_papel,
                "gramaje_gm2": float(papel_gramaje),
                "hojas_fisicas": int(hojas_fisicas),
                "hojas_con_merma": int(hojas_con_merma),
            },
            "acabados": {
                "total": float(total_acabados),
                "items": st.session_state.get("acabados_items", []),
                "metrics": quote_metrics,
            },
            "adicionales": {
                "total": float(total_adicionales),
                "items": [
                    {"concepto": r.get("Concepto", ""), "importe": float(r.get("Importe", 0.0))}
                    for r in (st.session_state.get("costos_adicionales", []) or [])
                    if str(r.get("Concepto", "")).strip()
                ],
            },
            "totales": {
                "precio_unitario": float(precio_unitario),
                "precio_total": float(precio_total),
                "margen": None,
            },
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
        "breakdown": breakdown_to_save,
        "config_snapshot": cfg_snapshot_to_save,
    }

    try:
        sb.table("quotes").insert(row).execute()
        st.success(f"Cotización guardada ✅ ID: {quote_code}")
    except Exception as e:
        st.error("No se pudo guardar en Supabase (revisa secrets / conexión).")
        st.exception(e)

section_close()

# -------------------------------------------------
# Texto copiable
# -------------------------------------------------
texto = build_text(
    perms=perms,
    descripcion_producto=descripcion_producto,
    ancho_final=ancho_final,
    alto_final=alto_final,
    piezas=piezas,
    tipo_producto=tipo_producto,
    lados=locals().get("lados", 2),
    paginas=paginas,
    piezas_por_lado=piezas_por_lado,
    orientacion=orientacion,
    area_w=area_w,
    area_h=area_h,
    hoja_w=hoja_w,
    hoja_h=hoja_h,
    costo_impresion=costo_impresion,
    tipo_papel=tipo_papel,
    papel_gramaje=papel_gramaje,
    papel_costo_kg=papel_costo_kg,
    merma_papel=merma_papel,
    costo_papel=costo_papel,
    total_acabados=total_acabados,
    acabados_items=st.session_state.get("acabados_items", []),
    total_adicionales=total_adicionales,
    costos_adicionales=st.session_state.costos_adicionales,
    subtotal_costos=subtotal_costos,
    margen=margen,
    precio_unitario=precio_unitario,
    precio_total=precio_total,
)

section_open()
st.subheader("Texto para copiar")
st.text_area("Texto para copiar (WhatsApp / correo)", value=texto, height=360)
section_close()

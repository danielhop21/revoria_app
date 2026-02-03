import sys
from pathlib import Path
import copy
import re
import unicodedata

import streamlit as st

# -------------------------------------------------
# Helpers (keys canónicas)
# -------------------------------------------------
def canonical_key(name: str) -> str:
    """Convierte nombre a key canónica: sin acentos, casefold, sin símbolos raros, espacios a '_'."""
    s = (name or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    s = re.sub(r"[^a-z0-9\s_-]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(" ", "_")
    return s

def sentence_case(name: str) -> str:
    s = (name or "").strip()
    if not s:
        return s
    s2 = s.lower()
    return s2[0].upper() + s2[1:]

import math

def compute_finish_cost(fdef: dict, metrics: dict, user_inputs: dict) -> dict:
    basis = fdef.get("basis")
    calc_type = fdef.get("calc_type")

    # 1) qty base
    if basis == "sheet_m2_total":
        qty = float(metrics.get("sheet_m2_total", 0.0))
        if fdef.get("allow_partial", False):
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

# -------------------------------------------------
# Root / imports internos
# -------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth_users_yaml import require_login
from lib.permissions import permissions_for
from lib.config_store import get_config, reset_config, save_config
from lib.ui import inject_global_css, render_header

# -------------------------------------------------
# Page config + auth
# -------------------------------------------------
st.set_page_config(page_title="Configuración — Offset Santiago", layout="centered")
inject_global_css()

user = require_login()
perms = permissions_for(user.role)

if not perms.can_access_settings:
    st.error("No tienes permiso para acceder a Configuración (solo admin).")
    st.stop()

render_header(
    "Configuración",
    "Costos base (admin): impresión, papel, acabados y margen"
)

# -------------------------------------------------
# Load config + defaults defensivos
# -------------------------------------------------
cfg = get_config()
cfg_original = copy.deepcopy(cfg)

cfg.setdefault("impresion", {})
cfg.setdefault("papel", {})
cfg.setdefault("margen", {})
cfg.setdefault("acabados", [])

if not isinstance(cfg["acabados"], list):
    cfg["acabados"] = []

cfg["impresion"].setdefault("mo_dep", 0.0)
cfg["impresion"].setdefault("tinta_cmyk_base", 0.0)
cfg["impresion"].setdefault("click_base", 0.0)
cfg["impresion"].setdefault("cobertura_op", 0.0)
cfg["impresion"].setdefault("cobertura_tinta_base_pct", 7.5)

cfg["papel"].setdefault("merma", 0.0)
cfg["margen"].setdefault("margen", 0.0)

# -------------------------------------------------
# Migraciones legacy
# -------------------------------------------------
if "cobertura_op" not in cfg["impresion"] and "cobertura" in cfg["impresion"]:
    cfg["impresion"]["cobertura_op"] = cfg["impresion"]["cobertura"]

if "tinta_cmyk_base" not in cfg["impresion"] and "tinta" in cfg["impresion"]:
    cfg["impresion"]["tinta_cmyk_base"] = cfg["impresion"]["tinta"]

if "click_base" not in cfg["impresion"] and "click" in cfg["impresion"]:
    cfg["impresion"]["click_base"] = cfg["impresion"]["click"]

# -------------------------------------------------
# UI: Impresión
# -------------------------------------------------
st.subheader("Impresión (por Carta – 1 lado)")

cfg["impresion"]["mo_dep"] = st.number_input(
    "MO + Depreciación",
    min_value=0.0,
    value=float(cfg["impresion"].get("mo_dep", 0.0)),
    step=0.01,
    format="%.4f",
    key="cfg_imp_mo_dep",
)

cfg["impresion"]["tinta_cmyk_base"] = st.number_input(
    "Tinta (base CMYK @ cobertura base)",
    min_value=0.0,
    value=float(cfg["impresion"].get("tinta_cmyk_base", 0.0)),
    step=0.01,
    format="%.4f",
    key="cfg_imp_tinta_cmyk_base",
)

cfg["impresion"]["click_base"] = st.number_input(
    "Click servicio (base @ cobertura base)",
    min_value=0.0,
    value=float(cfg["impresion"].get("click_base", 0.0)),
    step=0.01,
    format="%.4f",
    key="cfg_imp_click_base",
)

cfg["impresion"]["cobertura_op"] = st.number_input(
    "Cobertura operativa (costo fijo por carta-lado)",
    min_value=0.0,
    value=float(cfg["impresion"].get("cobertura_op", 0.0)),
    step=0.01,
    format="%.4f",
    key="cfg_imp_cobertura_op",
)

st.divider()

st.subheader("Cobertura de tinta (%)")

cfg["impresion"]["cobertura_tinta_base_pct"] = st.number_input(
    "Cobertura base real (%)",
    min_value=0.1,
    value=float(cfg["impresion"].get("cobertura_tinta_base_pct", 7.5)),
    step=0.1,
    format="%.2f",
    help="Porcentaje real promedio con el que están calibrados tinta_cmyk_base y click_base (ej. 7.5%).",
    key="cfg_imp_cobertura_tinta_base_pct",
)

st.divider()

# -------------------------------------------------
# UI: Papel
# -------------------------------------------------
st.subheader("Papel")

legacy_costo = float(cfg["papel"].get("costo_kg", 0.0) or 0.0)
cfg["papel"].setdefault("cuche_costo_kg", legacy_costo)
cfg["papel"].setdefault("bond_costo_kg", legacy_costo)
cfg["papel"].setdefault("especial_costo_kg", legacy_costo)

col1, col2, col3 = st.columns(3)

with col1:
    cfg["papel"]["cuche_costo_kg"] = st.number_input(
        "Couché ($/kg)",
        min_value=0.0,
        value=float(cfg["papel"].get("cuche_costo_kg", 0.0)),
        step=0.5,
        format="%.2f",
        key="cfg_papel_cuche_costo_kg",
    )

with col2:
    cfg["papel"]["bond_costo_kg"] = st.number_input(
        "Bond ($/kg)",
        min_value=0.0,
        value=float(cfg["papel"].get("bond_costo_kg", 0.0)),
        step=0.5,
        format="%.2f",
        key="cfg_papel_bond_costo_kg",
    )

with col3:
    cfg["papel"]["especial_costo_kg"] = st.number_input(
        "Especial ($/kg)",
        min_value=0.0,
        value=float(cfg["papel"].get("especial_costo_kg", 0.0)),
        step=0.5,
        format="%.2f",
        key="cfg_papel_especial_costo_kg",
    )

st.divider()

merma_pct = st.number_input(
    "Merma papel (%)",
    min_value=0.0,
    value=float(cfg["papel"].get("merma", 0.0) * 100.0),
    step=0.5,
    format="%.1f",
    key="cfg_papel_merma_pct",
)
cfg["papel"]["merma"] = float(merma_pct) / 100.0

st.divider()

# -------------------------------------------------
# UI: Acabados
# -------------------------------------------------
st.subheader("Acabados")

# Flash message (para mostrar resultado después de rerun)
flash = st.session_state.pop("cfg_flash_msg", None)
flash_type = st.session_state.pop("cfg_flash_type", None)

if flash:
    if flash_type == "success":
        st.success(flash)
    elif flash_type == "error":
        st.error(flash)
    else:
        st.info(flash)

BASIS_OPTIONS = {
    "Área procesada pliego (m²)": "sheet_m2_total",
    "Pliegos (tabloides)": "sheets_total",
    "Piezas (tiraje)": "pieces_total",
}
CALC_OPTIONS = {
    "Unitario (rate * qty)": "unit",
    "Mínimo vs unitario (max(min, rate*qty))": "min_or_unit",
    "Arranque + unitario (setup + rate*qty)": "setup_plus_unit",
    "Arranque + mínimo (max(min, setup + rate*qty))": "setup_plus_min_or_unit",
}
ROUNDING_OPTIONS = {
    "Ninguno": "none",
    "Por millar (ceil(qty/1000))": "ceil_1000",
}

# Normaliza estructura interna (por si vienen acabados viejos incompletos)
for f in cfg["acabados"]:
    if isinstance(f, dict):
        f.setdefault("display_name", "")    
        f.setdefault("key", canonical_key(f.get("display_name", "")))
        f.setdefault("basis", "sheet_m2_total")
        f.setdefault("calc_type", "min_or_unit")
        f.setdefault("rate", 0.0)
        f.setdefault("minimum", 0.0)
        f.setdefault("setup", 0.0)
        f.setdefault("qty_rounding", "none")
        f.setdefault("allow_partial", False)
        f.setdefault("requires", [])

def _norm_name(s: str) -> str:
    """Normaliza para comparar nombres: sin acentos, casefold, espacios colapsados."""
    s = (s or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def find_finish_by_name_insensitive(name: str):
    """Busca por nombre ignorando mayúsculas/acentos/espacios. Retorna (idx, obj) o (None, None)."""
    target = _norm_name(name)
    for i, f in enumerate(cfg["acabados"]):
        if isinstance(f, dict) and _norm_name(f.get("display_name", "")) == target:
            return i, f
    return None, None

def find_finish_by_display_name_exact(display_name: str):
    for i, f in enumerate(cfg["acabados"]):
        if isinstance(f, dict) and f.get("display_name", "") == display_name:
            return i, f
    return None, None

def find_finish_by_key(k: str):
    """Busca por key exacta. Retorna (idx, obj) o (None, None)."""
    k = (k or "").strip()
    if not k:
        return None, None
    for i, f in enumerate(cfg["acabados"]):
        if isinstance(f, dict) and f.get("key") == k:
            return i, f
    return None, None

existing_names = sorted([
    f.get("display_name", "")
    for f in cfg["acabados"]
    if isinstance(f, dict) and f.get("display_name", "").strip()
])

selected_name = st.selectbox(
    "Selecciona un acabado para editar",
    ["— Nuevo acabado —"] + existing_names,
    key="cfg_acab_selected_name",
)

is_new = selected_name == "— Nuevo acabado —"
edit_idx, edit_obj = (None, None)
if not is_new:
    edit_idx, edit_obj = find_finish_by_display_name_exact(selected_name)

# Guardamos la key del acabado seleccionado como "ID estable" para editar seguro
if not is_new and isinstance(edit_obj, dict):
    st.session_state["cfg_acab_edit_key"] = edit_obj.get("key", "")
else:
    st.session_state["cfg_acab_edit_key"] = ""

with st.expander("Editar / crear acabado", expanded=True):
    base = {
        "display_name": "",
        "key": "",
        "basis": "sheet_m2_total",
        "calc_type": "min_or_unit",
        "rate": 0.0,
        "minimum": 0.0,
        "setup": 0.0,
        "qty_rounding": "none",
        "allow_partial": False,
        "requires": [],
    } if is_new else copy.deepcopy(edit_obj)

    nombre = st.text_input(
        "Nombre (se mostrará en Cotizador)",
        value=base.get("display_name", ""),
        key="cfg_acab_nombre",
    )

    display_auto = re.sub(r"\s+", " ", (nombre or "").strip())
    # --- Validación: NO permitir duplicar nombres al crear nuevo ---
    dup_idx, dup_obj = find_finish_by_name_insensitive(display_auto)
    name_conflict_new = is_new and (dup_idx is not None)

    if name_conflict_new:
        st.error("Ya existe un acabado con ese nombre (ignorando mayúsculas/acentos/espacios). Cambia el nombre.")

    key_auto = canonical_key(display_auto)

    st.caption(f"Key (canónica): `{key_auto}`  |  Display: `{display_auto}`")

    basis_label = next((k for k, v in BASIS_OPTIONS.items() if v == base.get("basis")), list(BASIS_OPTIONS.keys())[0])
    calc_label  = next((k for k, v in CALC_OPTIONS.items() if v == base.get("calc_type")), list(CALC_OPTIONS.keys())[1])
    round_label = next((k for k, v in ROUNDING_OPTIONS.items() if v == base.get("qty_rounding")), list(ROUNDING_OPTIONS.keys())[0])

    # 1) ¿Sobre qué se cobra?
    c1, c2 = st.columns(2)
    with c1:
        basis_sel = st.selectbox(
            "¿Sobre qué se cobra?",
            list(BASIS_OPTIONS.keys()),
            index=list(BASIS_OPTIONS.keys()).index(basis_label),
            key="cfg_acab_basis",
        )

    with c2:
        PRICING_SIMPLE = {
            "Por unidad": "unit",
            "Por unidad con mínimo": "min_or_unit",
            "Arranque + por unidad": "setup_plus_unit",
            "Arranque + por unidad con mínimo": "setup_plus_min_or_unit",
        }

        simple_label = next(
            (k for k, v in PRICING_SIMPLE.items() if v == base.get("calc_type")),
            "Por unidad con mínimo"
        )

        pricing_sel_label = st.radio(
            "¿Cómo se cobra?",
            list(PRICING_SIMPLE.keys()),
            index=list(PRICING_SIMPLE.keys()).index(simple_label),
            key="cfg_acab_pricing_simple",
        )

    calc_type_value = PRICING_SIMPLE[pricing_sel_label]

    # 2) Inputs necesarios (solo los que aplican)
    rate = st.number_input(
        "Costo por unidad base ($)",
        min_value=0.0,
        value=float(base.get("rate", 0.0)),
        step=0.1,
        format="%.4f",
        key="cfg_acab_rate",
    )

    setup = 0.0
    minimum = 0.0

    if calc_type_value in ("setup_plus_unit", "setup_plus_min_or_unit"):
        setup = st.number_input(
            "Arranque ($)",
            min_value=0.0,
            value=float(base.get("setup", 0.0)),
            step=1.0,
            format="%.2f",
            key="cfg_acab_setup",
        )

    minimum = 0.0

    if calc_type_value in ("min_or_unit", "setup_plus_min_or_unit"):
        minimum = st.number_input(
            "Mínimo ($)",
            min_value=0.0,
            value=float(base.get("minimum", 0.0)),
            step=1.0,
            format="%.2f",
            key="cfg_acab_minimum",
        )

    with st.expander("Opciones avanzadas", expanded=False):

        rounding_sel = st.selectbox(
            "Redondeo de cantidad",
            list(ROUNDING_OPTIONS.keys()),
            index=list(ROUNDING_OPTIONS.keys()).index(round_label),
            key="cfg_acab_rounding",
        )

        allow_partial = False
        if BASIS_OPTIONS[basis_sel] == "sheet_m2_total":
            allow_partial = st.checkbox(
                "Permitir cobro parcial por cobertura (%)",
                value=bool(base.get("allow_partial", False)),
                key="cfg_acab_allow_partial",
            )

        # Requiere dobleces (solo si la base es pliegos)
        req_folds = False
        if BASIS_OPTIONS[basis_sel] == "sheets_total":
            req_folds = st.checkbox(
                "Requiere dobleces por pliego",
                value=("folds_per_sheet" in base.get("requires", [])),
                key="cfg_acab_req_folds",
            )

  # -------------------------------------------------
    # Validación de nombre duplicado
    # -------------------------------------------------
    dup_idx, dup_obj = find_finish_by_name_insensitive(display_auto)

    if is_new:
        name_conflict = dup_idx is not None
    else:
        # si dup existe pero NO es el mismo key, es conflicto
        same_key = (
            isinstance(dup_obj, dict)
            and dup_obj.get("key") == st.session_state.get("cfg_acab_edit_key")
        )
        name_conflict = (dup_idx is not None) and (not same_key)

    if name_conflict:
        st.warning("Ya existe un acabado con ese nombre (ignorando acentos/mayúsculas).")

    # Base: solo nombre válido y sin conflicto
    can_save = bool(nombre.strip()) and (not name_conflict)

    # -------------------------------------------------
    # Confirmación para EDITAR (modificar existente)
    # -------------------------------------------------
    confirm_edit = True
    if not is_new:
        st.warning(f"Vas a modificar un acabado existente: **{selected_name}**")
        confirm_edit = st.checkbox(
            "Confirmo que quiero sobrescribir este acabado.",
            value=False,
            key="cfg_acab_confirm_edit",
        )

        # 👉 ESTA LÍNEA VA DENTRO DEL IF
        can_save = can_save and bool(confirm_edit)

    b1, b2 = st.columns(2)
    with b1:
        btn_label = "💾 Crear acabado" if is_new else "💾 Actualizar acabado"

        if st.button(btn_label, disabled=(not can_save), key="cfg_acab_save"):
            new_obj = {
                "display_name": display_auto,
                "key": key_auto,
                "basis": BASIS_OPTIONS[basis_sel],
                "calc_type": calc_type_value,
                "rate": float(rate),
                "setup": float(setup),
                "minimum": float(minimum),
                "qty_rounding": ROUNDING_OPTIONS[rounding_sel],
                "allow_partial": bool(allow_partial),
                "requires": (["folds_per_sheet"] if req_folds else []),
            }

            # -------------------------------------------------
            # NEW: crear acabado nuevo
            # -------------------------------------------------
            if is_new:
                # Safety net: no permitir duplicar por nombre (insensible)
                if find_finish_by_name_insensitive(display_auto)[0] is not None:
                    st.session_state["cfg_flash_type"] = "error"
                    st.session_state["cfg_flash_msg"] = "Ya existe un acabado con ese nombre. No se guardó."
                    st.rerun()

                up_idx, up_obj = find_finish_by_key(key_auto)
                if up_idx is None:
                    cfg["acabados"].append(new_obj)
                    save_config(cfg)

                    st.session_state["cfg_flash_type"] = "success"
                    st.session_state["cfg_flash_msg"] = "Acabado nuevo guardado ✅"
                else:
                    st.session_state["cfg_flash_type"] = "error"
                    st.session_state["cfg_flash_msg"] = "Ya existe un acabado con esa key. Cambia el nombre para generar otra key."

            # -------------------------------------------------
            # EDIT: actualizar acabado existente
            # -------------------------------------------------
            else:
                edit_key = st.session_state.get("cfg_acab_edit_key", "")
                up_idx, up_obj = find_finish_by_key(edit_key)

                if up_idx is None:
                    st.session_state["cfg_flash_type"] = "error"
                    st.session_state["cfg_flash_msg"] = (
                        "No se encontró el acabado original por key. "
                        "No se guardó nada (evitamos pisar otro)."
                    )
                else:
                    # Conserva la key original SIEMPRE
                    new_obj["key"] = up_obj.get("key", edit_key)
                    cfg["acabados"][up_idx] = new_obj
                    save_config(cfg)

                    st.session_state["cfg_flash_type"] = "success"
                    st.session_state["cfg_flash_msg"] = (
                        f"Modificación aplicada ✅ Se actualizó el acabado: "
                        f"{new_obj.get('display_name','')}"
                    )

            st.rerun()

    with b2:
        if st.button("🗑️ Eliminar acabado", disabled=is_new, key="cfg_acab_delete"):
            if edit_idx is not None:
                cfg["acabados"].pop(edit_idx)
                save_config(cfg)
                st.success("Acabado eliminado ✅")
                st.rerun()

if not cfg["acabados"]:
    st.info("Aún no hay acabados configurados. (Puedes cotizar sin acabados; usa extras manuales si aplica.)")
else:
    with st.expander("Ver catálogo de acabados (Avanzado)", expanded=False):
        for f in sorted(cfg["acabados"], key=lambda x: x.get("display_name", "")):
            st.write(
                f"- {f.get('display_name','')} · "
                f"base={f.get('basis')} · cobro={f.get('calc_type')} · "
                f"rate=${float(f.get('rate',0.0)):.4f} · arranque=${float(f.get('setup',0.0)):.2f} · mínimo=${float(f.get('minimum',0.0)):.2f}"
            )
# -------------------------------------------------
# Simulador de cálculo (para validar acabados)
# -------------------------------------------------
with st.expander("Simulador de acabados (Avanzado)", expanded=False):

    st.divider()
    st.subheader("Simulador de cálculo (validación rápida)")

    st.caption("Esto NO guarda nada. Solo sirve para validar rate / mínimo / setup / redondeo / requires.")

    cS1, cS2, cS3 = st.columns(3)
    with cS1:
        sim_sheet_m2_total = st.number_input(
            "Área total procesada (m²)",
            min_value=0.0, value=100.0, step=1.0,
            key="sim_sheet_m2_total"
        )
    with cS2:
        sim_sheets_total = st.number_input(
            "Pliegos (tabloides)",
            min_value=0.0, value=1000.0, step=10.0,
            key="sim_sheets_total"
        )
    with cS3:
        sim_pieces_total = st.number_input(
            "Piezas (tiraje)",
            min_value=0.0, value=5000.0, step=50.0,
            key="sim_pieces_total"
        )

    sim_metrics = {
        "sheet_m2_total": float(sim_sheet_m2_total),
        "sheets_total": float(sim_sheets_total),
        "pieces_total": float(sim_pieces_total),
    }

    st.caption("Inputs extra (se usan solo si aplica):")
    cU1, cU2 = st.columns(2)
    with cU1:
        sim_coverage = st.slider(
            "Cobertura (si allow_partial)",
            0, 100, 100,
            key="sim_cov"
        ) / 100.0
    with cU2:
        sim_folds = st.number_input(
            "Dobleces por pliego (si requires folds_per_sheet)",
            min_value=1.0, value=1.0, step=1.0,
            key="sim_folds"
        )

    if cfg.get("acabados"):
        st.write("**Resultados por acabado:**")
        for f in sorted(cfg["acabados"], key=lambda x: str(x.get("display_name",""))):
            if not isinstance(f, dict):
                continue

            user_inputs = {}

            # allow_partial solo aplica si basis es m²
            if f.get("allow_partial", False) and f.get("basis") == "sheet_m2_total":
                user_inputs["coverage"] = float(sim_coverage)

            # requires folds
            req = f.get("requires", []) or []
            if "folds_per_sheet" in req and f.get("basis") == "sheets_total":
                user_inputs["folds_per_sheet"] = float(sim_folds)

            out = compute_finish_cost(f, sim_metrics, user_inputs)

            st.write(
                f"- **{f.get('display_name','(sin nombre)')}** "
                f"| basis={out['basis']} | qty={out['qty_used']:,.3f} "
                f"| rate=${out['rate']:,.4f} | setup=${out['setup']:,.2f} | min=${out['minimum']:,.2f} "
                f"→ **total=${out['total']:,.2f}**"
            )
    else:
        st.info("Aún no hay acabados en el catálogo.")

    st.divider()

# -------------------------------------------------
# UI: Margen
# -------------------------------------------------
st.subheader("Margen")

cfg["margen"]["margen"] = st.number_input(
    "Margen (0.40 = 40%)",
    min_value=0.0,
    value=float(cfg["margen"].get("margen", 0.0)),
    step=0.01,
    format="%.2f",
    key="cfg_margen_value",
)

st.divider()

# -------------------------------------------------
# Diffs + confirmaciones + guardado
# -------------------------------------------------
def _changed(a, b, tol=1e-9):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) > tol
    return a != b

def diff_any(old, new, prefix=""):
    cambios = []
    if isinstance(old, dict) and isinstance(new, dict):
        keys = set(old.keys()) | set(new.keys())
        for k in sorted(keys):
            cambios += diff_any(old.get(k, None), new.get(k, None), prefix + f"{k}.")
        return cambios

    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            cambios.append((prefix[:-1], old, new))
        else:
            for i, (ov, nv) in enumerate(zip(old, new)):
                cambios += diff_any(ov, nv, prefix + f"[{i}].")
        return cambios

    if _changed(old, new):
        cambios.append((prefix[:-1], old, new))
    return cambios

cambios = diff_any(cfg_original, cfg)
hay_cambios = len(cambios) > 0

firma_cambios = tuple((p, str(ov), str(nv)) for p, ov, nv in cambios)
if st.session_state.get("cfg_firma_cambios") != firma_cambios:
    st.session_state["cfg_firma_cambios"] = firma_cambios
    st.session_state["cfg_confirm_general"] = False
    st.session_state["cfg_confirm_base"] = False

st.session_state.setdefault("cfg_confirm_general", False)
st.session_state.setdefault("cfg_confirm_base", False)

st.subheader("Revisión antes de guardar")

if not hay_cambios:
    st.info("No hay cambios por guardar.")
else:
    max_mostrar = 25
    for path, ov, nv in cambios[:max_mostrar]:
        st.write(f"- **{path}**: {ov} → {nv}")
    if len(cambios) > max_mostrar:
        st.caption(f"Mostrando {max_mostrar} de {len(cambios)} cambios.")

confirm_general = st.checkbox(
    "Confirmo que revisé los cambios y deseo guardarlos.",
    key="cfg_confirm_general",
)

base_old = float(cfg_original.get("impresion", {}).get("cobertura_tinta_base_pct", 7.5))
base_new = float(cfg.get("impresion", {}).get("cobertura_tinta_base_pct", 7.5))
cambio_base = _changed(base_old, base_new)

confirm_base = True
if cambio_base:
    impacto = (base_new / max(base_old, 0.0001) - 1.0) * 100
    st.warning(
        f"Estás cambiando **Cobertura base (%)**: {base_old:.2f} → {base_new:.2f}. "
        f"Impacto aproximado en **tinta + click**: {impacto:+.1f}%."
    )
    confirm_base = st.checkbox(
        "Sí, estoy seguro de cambiar la Cobertura base (%).",
        key="cfg_confirm_base",
    )

# Ya NO obligamos a tener acabados para guardar la config general
puede_guardar = hay_cambios and bool(confirm_general) and bool(confirm_base)

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("💾 Guardar configuración", disabled=(not puede_guardar), key="cfg_save_btn"):
        save_config(cfg)
        st.success("Configuración guardada ✅")
        st.session_state["cfg_confirm_general"] = False
        st.session_state["cfg_confirm_base"] = False
        st.rerun()

with c2:
    if st.button("↩️ Restablecer defaults", key="cfg_reset_btn"):
        reset_config()
        st.success("Restablecida ✅")
        st.session_state["cfg_confirm_general"] = False
        st.session_state["cfg_confirm_base"] = False
        st.rerun()

with c3:
    st.info("Tip: guarda después de cambios grandes.")

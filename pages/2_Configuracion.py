import sys
from pathlib import Path
import copy

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth_users_yaml import require_login
from lib.permissions import permissions_for
from lib.config_store import get_config, reset_config, save_config
from lib.ui import inject_global_css, render_header

st.set_page_config(page_title="Configuración — Offset Santiago", layout="centered")
inject_global_css()

# --- Auth + permisos ---
user = require_login()
perms = permissions_for(user.role)

if not perms.can_access_settings:
    st.error("No tienes permiso para acceder a Configuración (solo admin).")
    st.stop()

render_header(
    "Configuración",
    "Costos base (admin): impresión, papel y margen"
)

cfg = get_config()
cfg_original = copy.deepcopy(cfg)

# Asegurar secciones (para evitar KeyError si faltan)
cfg.setdefault("impresion", {})
cfg.setdefault("papel", {})
cfg.setdefault("margen", {})

cfg["impresion"].setdefault("mo_dep", 0.0)
cfg["impresion"].setdefault("tinta_cmyk_base", 0.0)
cfg["impresion"].setdefault("click_base", 0.0)
cfg["impresion"].setdefault("cobertura_op", 0.0)
cfg["impresion"].setdefault("cobertura_tinta_base_pct", 7.5)

cfg["papel"].setdefault("merma", 0.0)
cfg["margen"].setdefault("margen", 0.0)

# -----------------------------
# Backward compatibility / migraciones
# -----------------------------
# si venías usando "cobertura" como costo fijo
if "cobertura_op" not in cfg["impresion"] and "cobertura" in cfg["impresion"]:
    cfg["impresion"]["cobertura_op"] = cfg["impresion"]["cobertura"]

# si venías usando "tinta" como base
if "tinta_cmyk_base" not in cfg["impresion"] and "tinta" in cfg["impresion"]:
    cfg["impresion"]["tinta_cmyk_base"] = cfg["impresion"]["tinta"]

if "click_base" not in cfg["impresion"] and "click" in cfg["impresion"]:
    cfg["impresion"]["click_base"] = cfg["impresion"]["click"]

# -----------------------------
# UI
# -----------------------------
st.subheader("Impresión (por Carta – 1 lado)")

cfg["impresion"]["mo_dep"] = st.number_input(
    "MO + Depreciación",
    min_value=0.0,
    value=float(cfg["impresion"].get("mo_dep", 0.0)),
    step=0.01,
    format="%.4f"
)

cfg["impresion"]["tinta_cmyk_base"] = st.number_input(
    "Tinta (base CMYK @ cobertura base)",
    min_value=0.0,
    value=float(cfg["impresion"].get("tinta_cmyk_base", 0.0)),
    step=0.01,
    format="%.4f"
)

cfg["impresion"]["click_base"] = st.number_input(
    "Click servicio (base @ cobertura base)",
    min_value=0.0,
    value=float(cfg["impresion"].get("click_base", 0.0)),
    step=0.01,
    format="%.4f"
)

cfg["impresion"]["cobertura_op"] = st.number_input(
    "Cobertura operativa (costo fijo por carta-lado)",
    min_value=0.0,
    value=float(cfg["impresion"].get("cobertura_op", 0.0)),
    step=0.01,
    format="%.4f"
)

st.divider()

# --- Este es el único bloque de cobertura (quitamos el duplicado) ---
st.subheader("Cobertura de tinta (%)")

cfg["impresion"]["cobertura_tinta_base_pct"] = st.number_input(
    "Cobertura base real (%)",
    min_value=0.1,
    value=float(cfg["impresion"].get("cobertura_tinta_base_pct", 7.5)),
    step=0.1,
    format="%.2f",
    help="Porcentaje real promedio con el que están calibrados tinta_cmyk_base y click_base (ej. 7.5%)."
)

st.divider()

st.subheader("Papel")

# Si antes existía un solo costo_kg, úsalo como fallback inicial
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
        format="%.2f"
    )

with col2:
    cfg["papel"]["bond_costo_kg"] = st.number_input(
        "Bond ($/kg)",
        min_value=0.0,
        value=float(cfg["papel"].get("bond_costo_kg", 0.0)),
        step=0.5,
        format="%.2f"
    )

with col3:
    cfg["papel"]["especial_costo_kg"] = st.number_input(
        "Especial ($/kg)",
        min_value=0.0,
        value=float(cfg["papel"].get("especial_costo_kg", 0.0)),
        step=0.5,
        format="%.2f"
    )

st.divider()

merma_pct = st.number_input(
    "Merma papel (%)",
    min_value=0.0,
    value=float(cfg["papel"].get("merma", 0.0) * 100.0),
    step=0.5,
    format="%.1f"
)
cfg["papel"]["merma"] = merma_pct / 100.0

st.divider()

st.subheader("Margen")

cfg["margen"]["margen"] = st.number_input(
    "Margen (0.40 = 40%)",
    min_value=0.0,
    value=float(cfg["margen"].get("margen", 0.0)),
    step=0.01,
    format="%.2f"
)

st.divider()

# -----------------------------
# Diffs y confirmaciones (fuera de funciones; antes estaba mal indentado)
# -----------------------------
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

# Cambios sobre TODO el cfg
cambios = diff_any(cfg_original, cfg)
hay_cambios = len(cambios) > 0

# Resetear confirmaciones si cambió el set de cambios
firma_cambios = tuple((p, str(ov), str(nv)) for p, ov, nv in cambios)
if st.session_state.get("firma_cambios") != firma_cambios:
    st.session_state["firma_cambios"] = firma_cambios
    st.session_state["confirm_general"] = False
    st.session_state["confirm_base"] = False

st.session_state.setdefault("confirm_general", False)
st.session_state.setdefault("confirm_base", False)

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
    key="confirm_general"
)

# Confirmación adicional: cobertura base
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
        key="confirm_base"
    )

puede_guardar = hay_cambios and confirm_general and confirm_base

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("💾 Guardar configuración", disabled=(not puede_guardar)):
        save_config(cfg)
        st.success("Configuración guardada.")
        st.session_state["confirm_general"] = False
        st.session_state["confirm_base"] = False
        st.rerun()

with c2:
    if st.button("↩️ Restablecer defaults"):
        reset_config()
        st.success("Restablecida.")
        st.session_state["confirm_general"] = False
        st.session_state["confirm_base"] = False
        st.rerun()

with c3:
    st.info("Tip: guarda después de cambios grandes.")

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import require_role
from lib.config_store import get_config, reset_config, save_config
from lib.ui import inject_global_css, render_header

st.set_page_config(page_title="Configuración — Offset Santiago", layout="centered")
inject_global_css()
require_role({"admin"})
render_header(
    "Configuración",
    "Costos base (admin): impresión, papel y margen"
)

cfg = get_config()

st.subheader("Impresión (por Carta – 1 lado)")
cfg["impresion"]["mo_dep"] = st.number_input("MO + Depreciación", min_value=0.0, value=float(cfg["impresion"]["mo_dep"]), step=0.01, format="%.4f")
cfg["impresion"]["tinta"] = st.number_input("Tinta CMYK", min_value=0.0, value=float(cfg["impresion"]["tinta"]), step=0.01, format="%.4f")
cfg["impresion"]["click"] = st.number_input("Click servicio", min_value=0.0, value=float(cfg["impresion"]["click"]), step=0.01, format="%.4f")
cfg["impresion"]["cobertura"] = st.number_input("Cobertura", min_value=0.0, value=float(cfg["impresion"]["cobertura"]), step=0.01, format="%.4f")

st.divider()

st.subheader("Papel")

# Asegurar claves (backward compatible + migración)
cfg.setdefault("papel", {})

# Si antes existía un solo costo_kg, úsalo como fallback inicial (no obligatorio)
legacy_costo = float(cfg["papel"].get("costo_kg", 0.0) or 0.0)

cfg["papel"].setdefault("cuche_costo_kg", legacy_costo)
cfg["papel"].setdefault("bond_costo_kg", legacy_costo)
cfg["papel"].setdefault("especial_costo_kg", legacy_costo)
cfg["papel"].setdefault("merma", 0.0)


col1, col2, col3 = st.columns(3)

with col1:
    cfg["papel"]["cuche_costo_kg"] = st.number_input(
        "Couché ($/kg)",
        min_value=0.0,
        value=float(cfg["papel"]["cuche_costo_kg"]),
        step=0.5,
        format="%.2f"
    )

with col2:
    cfg["papel"]["bond_costo_kg"] = st.number_input(
        "Bond ($/kg)",
        min_value=0.0,
        value=float(cfg["papel"]["bond_costo_kg"]),
        step=0.5,
        format="%.2f"
    )

with col3:
    cfg["papel"]["especial_costo_kg"] = st.number_input(
        "Especial ($/kg)",
        min_value=0.0,
        value=float(cfg["papel"]["especial_costo_kg"]),
        step=0.5,
        format="%.2f"
    )

st.divider()

merma_pct = st.number_input(
    "Merma papel (%)",
    min_value=0.0,
    value=float(cfg["papel"]["merma"] * 100.0),
    step=0.5,
    format="%.1f"
)
cfg["papel"]["merma"] = merma_pct / 100.0


st.divider()

st.subheader("Margen")
cfg["margen"]["margen"] = st.number_input("Margen (0.40 = 40%)", min_value=0.0, value=float(cfg["margen"]["margen"]), step=0.01, format="%.2f")

st.divider()
c1, c2, c3 = st.columns(3)

with c1:
    if st.button("💾 Guardar configuración"):
        save_config(cfg)
        st.success("Configuración guardada.")
        st.rerun()

with c2:
    if st.button("↩️ Restablecer defaults"):
        reset_config()
        st.success("Restablecida.")
        st.rerun()

with c3:
    st.info("Tip: guarda después de cambios grandes.")


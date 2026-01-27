import sys
from pathlib import Path
from lib.auth import require_role

ROOT = Path(__file__).resolve().parents[1]  # carpeta revoria_app
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from lib.config_store import get_config, reset_config, save_config

st.set_page_config(page_title="Configuración", layout="centered")
require_role({"admin"})

st.title("Configuración de costos (Admin)")
st.caption("Estos valores alimentan el cotizador. Por ahora se guardan en memoria (session).")

cfg = get_config()

st.subheader("Impresión (por Carta – 1 lado)")
cfg["impresion"]["mo_dep"] = st.number_input("MO + Depreciación", min_value=0.0, value=float(cfg["impresion"]["mo_dep"]), step=0.01, format="%.4f")
cfg["impresion"]["tinta"] = st.number_input("Tinta CMYK", min_value=0.0, value=float(cfg["impresion"]["tinta"]), step=0.01, format="%.4f")
cfg["impresion"]["click"] = st.number_input("Click servicio", min_value=0.0, value=float(cfg["impresion"]["click"]), step=0.01, format="%.4f")
cfg["impresion"]["cobertura"] = st.number_input("Cobertura", min_value=0.0, value=float(cfg["impresion"]["cobertura"]), step=0.01, format="%.4f")

st.divider()

st.subheader("Papel")
cfg["papel"]["costo_kg"] = st.number_input("Costo papel ($/kg)", min_value=0.0, value=float(cfg["papel"]["costo_kg"]), step=0.5, format="%.2f")
cfg["papel"]["gramaje"] = st.number_input("Gramaje (g/m²)", min_value=0.0, value=float(cfg["papel"]["gramaje"]), step=5.0, format="%.1f")

merma_pct = st.number_input("Merma papel (%)", min_value=0.0, value=float(cfg["papel"]["merma"] * 100.0), step=0.5, format="%.1f")
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


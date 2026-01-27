import streamlit as st
from lib.config_store import get_config, reset_config

st.set_page_config(page_title="Configuración", layout="centered")

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

c1, c2 = st.columns(2)
with c1:
    if st.button("Restablecer defaults"):
        reset_config()
        st.success("Configuración restablecida.")
        st.rerun()

with c2:
    st.success("Guardado automático: los cambios quedan en sesión al momento.")

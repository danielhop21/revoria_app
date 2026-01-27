import streamlit as st
from lib.auth import login_box

st.set_page_config(page_title="Revoria App", layout="centered")

st.title("Revoria – Offset Santiago")
st.write("Landing (entrada).")

login_box()

st.page_link("pages/1_Cotizador.py", label="🧾 Ir al Cotizador")
st.page_link("pages/2_Configuracion.py", label="⚙️ Configuración (admin)")


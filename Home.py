import streamlit as st
from lib.auth import login_box
from lib.ui import inject_global_css, render_header, card_open, card_close, section_open, section_close

st.set_page_config(page_title="Revoria App — Offset Santiago", layout="centered")
inject_global_css()
render_header("Revoria App", "Acceso y navegación")

login_box()

# Lee rol si ya se logueó
role = ""
if "auth" in st.session_state:
    role = st.session_state.auth.get("role", "")


#section_open()
#c1, c2 = st.columns(2)

#with c1:
#    if st.button("🧾 Ir al Cotizador", use_container_width=True):
#        st.switch_page("pages/1_Cotizador.py")

#with c2:
#    if role == "admin":
#        if st.button("⚙️ Configuración (admin)", use_container_width=True):
#            st.switch_page("pages/2_Configuracion.py")
#    else:
#        st.caption("Configuración: solo admin")

#section_close()


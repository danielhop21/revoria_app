import streamlit as st

from lib.auth_users_yaml import require_login, logout
from lib.ui import (
    inject_global_css,
    render_header,
    card_open,
    card_close,
    section_open,
    section_close,
)

st.set_page_config(page_title="Revoria App — Offset Santiago", layout="centered")
inject_global_css()
render_header("Cotizador Revoria", "Acceso y navegación")

# Login gate (si no está logueado, muestra login y detiene la app)
user = require_login()

# Rol del usuario ya autenticado
role = user.role or ""

# Sidebar mínimo (opcional pero útil)
with st.sidebar:
    st.markdown(f"**Usuario:** {user.name}")
    st.markdown(f"**Rol:** {role}")
    if st.button("Salir", use_container_width=True):
        logout()
        st.rerun()

# --- Tu navegación (la dejo igual como la tenías, comentada) ---

# section_open()
# c1, c2 = st.columns(2)
#
# with c1:
#     if st.button("🧾 Ir al Cotizador", use_container_width=True):
#         st.switch_page("pages/1_Cotizador.py")
#
# with c2:
#     if role == "admin":
#         if st.button("⚙️ Configuración (admin)", use_container_width=True):
#             st.switch_page("pages/2_Configuracion.py")
#     else:
#         st.caption("Configuración: solo admin")
#
# section_close()


import streamlit as st

def init_auth():
    if "auth" not in st.session_state:
        st.session_state.auth = {"is_logged": False, "user": None, "role": None}

def login_box():
    """
    Login simple con st.secrets["users"].
    En secrets:
      [users]
      daniel = {password="...", role="admin"}
    """
    init_auth()

    if st.session_state.auth["is_logged"]:
        st.success(f"Sesión activa: {st.session_state.auth['user']} ({st.session_state.auth['role']})")
        if st.button("Cerrar sesión"):
            st.session_state.auth = {"is_logged": False, "user": None, "role": None}
            st.rerun()
        return

    users = st.secrets.get("users", {})

    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Entrar")

    if ok:
        if u in users and str(users[u].get("password")) == str(p):
            st.session_state.auth = {"is_logged": True, "user": u, "role": users[u].get("role", "sales")}
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

def require_role(roles: set):
    init_auth()
    a = st.session_state.auth
    if not a["is_logged"]:
        st.warning("Necesitas iniciar sesión para ver esta página.")
        st.stop()
    if a["role"] not in roles:
        st.error("No tienes permisos para ver esta página.")
        st.stop()

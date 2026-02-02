from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

import bcrypt
import streamlit as st
import yaml

# Fallback opcional (si algún día quieres usar users.yaml en local)
USERS_PATH = Path(__file__).resolve().parents[1] / "users.yaml"


@dataclass(frozen=True)
class User:
    username: str
    name: str
    role: str


def _load_users() -> Dict[str, Any]:
    """
    Fuente preferida: st.secrets["users"] (dict TOML).
    Fallback opcional: users.yaml en raíz.
    Normaliza a {"users": {username: {...}}}.
    """
    # 1) Preferir secrets.toml / Streamlit Cloud Secrets
    try:
        if "users" in st.secrets:
            users = dict(st.secrets["users"])
            return {"users": users}
    except Exception:
        # Si por alguna razón st.secrets falla, seguimos al fallback
        pass

    # 2) Fallback a users.yaml
    if USERS_PATH.exists():
        with USERS_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"users": {}}

    return {"users": {}}


def _verify_password(password: str, entry: Dict[str, Any]) -> bool:
    """
    Valida password con bcrypt (password_hash).
    Soporta 'password' plano (legacy) por compatibilidad.
    """
    ph = entry.get("password_hash")
    if ph:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), str(ph).encode("utf-8"))
        except Exception:
            return False

    # Legacy (no recomendado)
    pw_plain = entry.get("password")
    if pw_plain is not None:
        return password == str(pw_plain)

    return False


def current_user() -> Optional[User]:
    u = st.session_state.get("user")
    if not u:
        return None
    return User(**u)


def logout() -> None:
    st.session_state.pop("user", None)
    st.session_state.pop("auth_error", None)


def require_login() -> User:
    user = current_user()
    if user:
        return user

    st.title("Login")
    users_doc = _load_users()

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Usuario", value="", autocomplete="username")
        password = st.text_input(
            "Password",
            value="",
            type="password",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button("Entrar")

    if submitted:
        entry = users_doc.get("users", {}).get(username)

        if not entry:
            st.session_state["auth_error"] = "Usuario inválido."
        else:
            is_active = entry.get("is_active", True)
            if not is_active:
                st.session_state["auth_error"] = "Usuario inactivo."
            else:
                ok = _verify_password(password, entry)
                if not ok:
                    st.session_state["auth_error"] = "Password incorrecto."
                else:
                    role = (entry.get("role", "vendedor") or "").strip().lower()
                    # compat si alguien dejó "sales" por ahí
                    if role == "sales":
                        role = "vendedor"

                    st.session_state["user"] = {
                        "username": username,
                        "name": entry.get("name", username),
                        "role": role,
                    }
                    st.session_state.pop("auth_error", None)
                    st.rerun()

    err = st.session_state.get("auth_error")
    if err:
        st.error(err)

    st.stop()

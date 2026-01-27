import copy
import streamlit as st

DEFAULT_CONFIG = {
    "impresion": {
        "mo_dep": 0.06,
        "tinta": 0.39,
        "click": 0.35,
        "cobertura": 0.10,
    },
    "papel": {
        "costo_kg": 21.0,
        "gramaje": 130.0,
        "merma": 0.0,  # aquí guardamos ya como decimal: 0.05 = 5%
    },
    "margen": {
        "margen": 0.40,  # 0.40 = 40%
    }
}

def get_config() -> dict:
    """Devuelve config y la inicializa si no existe."""
    if "config" not in st.session_state:
        st.session_state.config = copy.deepcopy(DEFAULT_CONFIG)
    return st.session_state.config

def reset_config():
    st.session_state.config = copy.deepcopy(DEFAULT_CONFIG)

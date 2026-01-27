import copy
import json
from pathlib import Path
import streamlit as st

DATA_DIR = Path("data")
DEFAULT_PATH = DATA_DIR / "config.default.json"
CONFIG_PATH = DATA_DIR / "config.json"

# Fallback por si falta el default (pero lo vamos a tener)
DEFAULT_CONFIG = {
    "impresion": {"mo_dep": 0.06, "tinta": 0.39, "click": 0.35, "cobertura": 0.10},
    "papel": {"costo_kg": 21.0, "gramaje": 130.0, "merma": 0.0},
    "margen": {"margen": 0.40},
}

def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def _write_json(path: Path, data: dict) -> None:
    _ensure_data_dir()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _get_default_config() -> dict:
    default = _load_json(DEFAULT_PATH)
    if isinstance(default, dict):
        return default
    return copy.deepcopy(DEFAULT_CONFIG)

def get_config() -> dict:
    """
    Devuelve config desde session_state.
    Si no existe en sesión:
      - intenta leer data/config.json
      - si no existe, copia default a config.json y lo usa
    """
    if "config" in st.session_state:
        return st.session_state.config

    default = _get_default_config()

    cfg = _load_json(CONFIG_PATH)
    if not isinstance(cfg, dict):
        # Primer uso: crear config.json desde default
        _write_json(CONFIG_PATH, default)
        cfg = copy.deepcopy(default)

    st.session_state.config = cfg
    return st.session_state.config

def save_config(cfg: dict) -> None:
    """Guarda a disco + actualiza session_state."""
    st.session_state.config = cfg
    _write_json(CONFIG_PATH, cfg)

def reset_config() -> None:
    """Restaura defaults y guarda."""
    default = _get_default_config()
    save_config(copy.deepcopy(default))

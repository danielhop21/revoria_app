import copy
import json
from pathlib import Path
import streamlit as st
from typing import Optional, Dict, Any


DATA_DIR = Path("data")
DEFAULT_PATH = DATA_DIR / "config.default.json"
CONFIG_PATH = DATA_DIR / "config.json"

# NUEVO DEFAULT: papel con costos por tipo (gramaje ya NO va en config)
DEFAULT_CONFIG = {
    "impresion": {"mo_dep": 0.06, "tinta": 0.39, "click": 0.35, "cobertura": 0.10},
    "papel": {
        "cuche_costo_kg": 21.0,
        "bond_costo_kg": 21.0,
        "especial_costo_kg": 21.0,
        "merma": 0.0
    },
    "margen": {"margen": 0.40},
}


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
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


def _normalize_config(cfg: dict, default: dict) -> dict:
    """
    Normaliza y migra config vieja a la nueva estructura.
    Objetivo: que el cotizador nunca truene por llaves faltantes.
    """

    # Asegurar secciones base
    cfg.setdefault("impresion", {})
    cfg.setdefault("papel", {})
    cfg.setdefault("margen", {})

    # Impresión defaults (por si faltan)
    cfg["impresion"].setdefault("mo_dep", default["impresion"]["mo_dep"])
    cfg["impresion"].setdefault("tinta", default["impresion"]["tinta"])
    cfg["impresion"].setdefault("click", default["impresion"]["click"])
    cfg["impresion"].setdefault("cobertura", default["impresion"]["cobertura"])

    # Papel: migrar desde estructura vieja si existía costo_kg
    legacy_costo = cfg["papel"].get("costo_kg", None)
    if legacy_costo is None:
        legacy_costo = default["papel"].get("cuche_costo_kg", 0.0)

    try:
        legacy_costo = float(legacy_costo)
    except Exception:
        legacy_costo = float(default["papel"].get("cuche_costo_kg", 0.0))

    # Nuevas llaves obligatorias
    cfg["papel"].setdefault("cuche_costo_kg", legacy_costo)
    cfg["papel"].setdefault("bond_costo_kg", legacy_costo)
    cfg["papel"].setdefault("especial_costo_kg", legacy_costo)

    # Merma
    merma = cfg["papel"].get("merma", default["papel"].get("merma", 0.0))
    try:
        cfg["papel"]["merma"] = float(merma)
    except Exception:
        cfg["papel"]["merma"] = float(default["papel"].get("merma", 0.0))

    # Margen
    cfg["margen"].setdefault("margen", default["margen"]["margen"])
    try:
        cfg["margen"]["margen"] = float(cfg["margen"]["margen"])
    except Exception:
        cfg["margen"]["margen"] = float(default["margen"]["margen"])

    # Nota: "papel.gramaje" ya no aplica. Si existe en config viejo, lo dejamos (no estorba),
    # pero el cotizador ya no lo usa.

    return cfg


def get_config() -> dict:
    """
    Devuelve config desde session_state.
    Si no existe en sesión:
      - intenta leer data/config.json
      - si no existe, copia default a config.json y lo usa
    Además:
      - normaliza/migra a nueva estructura (papel por tipo)
    """
    if "config" in st.session_state:
        # Asegura que si cambiaste defaults/versiones, también normalice en caliente
        default = _get_default_config()
        st.session_state.config = _normalize_config(st.session_state.config, default)
        return st.session_state.config

    default = _get_default_config()

    cfg = _load_json(CONFIG_PATH)
    if not isinstance(cfg, dict):
        # Primer uso: crear config.json desde default
        _write_json(CONFIG_PATH, default)
        cfg = copy.deepcopy(default)

    # Normalizar/migrar
    cfg = _normalize_config(cfg, default)

    # Persistir si la migración agregó llaves nuevas
    _write_json(CONFIG_PATH, cfg)

    st.session_state.config = cfg
    return st.session_state.config


def save_config(cfg: dict) -> None:
    """Guarda a disco + actualiza session_state (normalizado)."""
    default = _get_default_config()
    cfg = _normalize_config(cfg, default)
    st.session_state.config = cfg
    _write_json(CONFIG_PATH, cfg)


def reset_config() -> None:
    """Restaura defaults y guarda."""
    default = _get_default_config()
    save_config(copy.deepcopy(default))

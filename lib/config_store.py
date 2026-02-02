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
    "impresion": {
        # base por carta-lado
        "mo_dep": 0.06,

        # costos calibrados a "cobertura base"
        "tinta_cmyk_base": 0.39,
        "click_base": 0.35,

        # tu concepto fijo por carta-lado (antes "cobertura")
        "cobertura_op": 0.10,

        # % de cobertura de tinta
        "cobertura_tinta_base_pct": 10.0,
        "cobertura_tinta_pct": 10.0,

        # legacy (los dejamos para no romper nada viejo)
        "tinta": 0.39,
        "click": 0.35,
        "cobertura": 0.10,
    },
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

    # -------------------------
    # Impresión: defaults + migración a llaves nuevas
    # -------------------------
    imp = cfg["impresion"]
    def_imp = default["impresion"]

    # Siempre asegurar mo_dep
    imp.setdefault("mo_dep", def_imp.get("mo_dep", 0.0))

    # Migrar cobertura_op (antes "cobertura")
    if "cobertura_op" not in imp and "cobertura" in imp:
        imp["cobertura_op"] = imp["cobertura"]
    imp.setdefault("cobertura_op", def_imp.get("cobertura_op", def_imp.get("cobertura", 0.0)))

    # Migrar tinta_cmyk_base (antes "tinta")
    if "tinta_cmyk_base" not in imp and "tinta" in imp:
        imp["tinta_cmyk_base"] = imp["tinta"]
    imp.setdefault("tinta_cmyk_base", def_imp.get("tinta_cmyk_base", def_imp.get("tinta", 0.0)))

    # Migrar click_base (antes "click")
    if "click_base" not in imp and "click" in imp:
        imp["click_base"] = imp["click"]
    imp.setdefault("click_base", def_imp.get("click_base", def_imp.get("click", 0.0)))

    # Cobertura de tinta (%): base + vigente
    imp.setdefault("cobertura_tinta_base_pct", def_imp.get("cobertura_tinta_base_pct", 10.0))
    imp.setdefault("cobertura_tinta_pct", imp["cobertura_tinta_base_pct"])

    # Normalizar tipos (floats)
    for k in ["mo_dep", "cobertura_op", "tinta_cmyk_base", "click_base", "cobertura_tinta_base_pct", "cobertura_tinta_pct"]:
        try:
            imp[k] = float(imp[k])
        except Exception:
            imp[k] = float(def_imp.get(k, 0.0))

    # (Opcional) mantener legacy, no estorba
    imp.setdefault("tinta", imp.get("tinta_cmyk_base", 0.0))
    imp.setdefault("click", imp.get("click_base", 0.0))
    imp.setdefault("cobertura", imp.get("cobertura_op", 0.0))


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

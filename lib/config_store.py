import copy
import json
import re
from pathlib import Path
import streamlit as st
from typing import Optional, Dict, Any


DATA_DIR = Path("data")
DEFAULT_PATH = DATA_DIR / "config.default.json"
CONFIG_PATH = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "impresion": {
        "mo_dep": 0.06,
        "tinta_cmyk_base": 0.39,
        "click_base": 0.35,
        "cobertura_op": 0.10,
        "cobertura_tinta_base_pct": 7.5,

        # legacy
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
    # OJO: aquí “acabados” es el CATÁLOGO que tu Cotizador consume
    "acabados": [],
    "margen": {"margen": 0.40},
}

# -------------------------
# Helpers generales
# -------------------------
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

    # backup simple
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        try:
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _get_default_config() -> dict:
    default = _load_json(DEFAULT_PATH)
    if isinstance(default, dict):
        return default
    return copy.deepcopy(DEFAULT_CONFIG)

def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9\-_]", "", s)
    return s or "finish"

def _to_float(x: Any, fallback: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(fallback)

def _to_bool(x: Any, fallback: bool = False) -> bool:
    try:
        return bool(x)
    except Exception:
        return bool(fallback)

# -------------------------
# ACABADOS (CATÁLOGO) — compatible con tu Cotizador.py
# -------------------------
REQUIRED_CATALOG_KEYS = ["key", "display_name", "basis", "calc_type", "rate", "minimum", "setup", "qty_rounding", "allow_partial"]

def _is_advanced_finish_dict(d: dict) -> bool:
    # Detecta el formato que tu Cotizador espera (con basis/calc_type)
    return isinstance(d, dict) and ("basis" in d or "calc_type" in d or "display_name" in d or "key" in d)

def _normalize_one_finish_advanced(f: dict) -> dict:
    """
    Normaliza 1 acabado en formato ADVANCED (el de tu cotizador).
    No elimina llaves extra.
    """
    out = dict(f)  # conserva extras

    # display_name
    out["display_name"] = str(out.get("display_name", "")).strip()

    # key: si falta, derivarlo de display_name
    key = str(out.get("key", "")).strip()
    if not key:
        key = _slugify(out["display_name"])
    out["key"] = key

    # basis / calc_type
    out["basis"] = str(out.get("basis", "sheets_total")).strip()
    out["calc_type"] = str(out.get("calc_type", "unit")).strip()

    # qty_rounding
    out["qty_rounding"] = str(out.get("qty_rounding", "none")).strip()

    # allow_partial
    out["allow_partial"] = _to_bool(out.get("allow_partial", False), False)

    # requires: si existe, debe ser lista
    req = out.get("requires", [])
    if req is None:
        req = []
    if not isinstance(req, list):
        req = []
    out["requires"] = req

    # rate/setup/minimum: float
    out["rate"] = _to_float(out.get("rate", 0.0), 0.0)
    out["setup"] = _to_float(out.get("setup", 0.0), 0.0)
    out["minimum"] = _to_float(out.get("minimum", 0.0), 0.0)

    # Validación defensiva mínima (sin matar: solo corrige defaults)
    for k in REQUIRED_CATALOG_KEYS:
        if k not in out:
            # esto no debería pasar ya, pero por seguridad
            if k in ("rate", "setup", "minimum"):
                out[k] = 0.0
            elif k == "allow_partial":
                out[k] = False
            elif k == "qty_rounding":
                out[k] = "none"
            elif k == "basis":
                out[k] = "sheets_total"
            elif k == "calc_type":
                out[k] = "unit"
            else:
                out[k] = ""

    return out

def _normalize_acabados_catalog(acabados: Any) -> list[dict]:
    """
    Devuelve SIEMPRE una lista de dicts en formato catálogo ADVANCED,
    compatible con Cotizador.py.

    Soporta legacy:
      - None -> []
      - list[str] -> lo convierte a acabados tipo "unit" por lote (rate=0) para no tronar
      - dict {"Barniz": 120} -> lo convierte a "unit" (rate=120) con basis=sheets_total por default
      - list[dict] -> normaliza advanced y conserva extras
    """
    if acabados is None:
        return []

    # Legacy dict tipo {"Barniz": 120, "Laminado": 300}
    if isinstance(acabados, dict):
        tmp = []
        for name, rate in acabados.items():
            tmp.append({
                "key": _slugify(str(name)),
                "display_name": str(name),
                "basis": "sheets_total",
                "calc_type": "unit",
                "rate": _to_float(rate, 0.0),
                "minimum": 0.0,
                "setup": 0.0,
                "qty_rounding": "none",
                "allow_partial": False,
                "requires": [],
            })
        acabados = tmp

    if not isinstance(acabados, list):
        return []

    out: list[dict] = []
    used_keys: set[str] = set()

    for item in acabados:
        # Legacy: string
        if isinstance(item, str):
            name = item.strip()
            if not name:
                continue
            f = {
                "key": _slugify(name),
                "display_name": name,
                "basis": "sheets_total",
                "calc_type": "unit",
                "rate": 0.0,
                "minimum": 0.0,
                "setup": 0.0,
                "qty_rounding": "none",
                "allow_partial": False,
                "requires": [],
            }
            f = _normalize_one_finish_advanced(f)
        elif isinstance(item, dict) and _is_advanced_finish_dict(item):
            f = _normalize_one_finish_advanced(item)
        else:
            continue

        # Evitar colisiones de key
        k = f.get("key", "")
        if k in used_keys:
            # sufijo incremental simple
            base = k or "finish"
            n = 2
            kk = f"{base}_{n}"
            while kk in used_keys:
                n += 1
                kk = f"{base}_{n}"
            f["key"] = kk
        used_keys.add(f["key"])

        out.append(f)

    return out

# -------------------------
# Normalización global
# -------------------------
def _normalize_config(cfg: dict, default: dict) -> dict:
    if not isinstance(cfg, dict):
        cfg = {}

    # Secciones base
    cfg.setdefault("impresion", {})
    cfg.setdefault("papel", {})
    cfg.setdefault("margen", {})

    # Acabados catálogo: SIEMPRE dejarlo compatible con Cotizador.py
    cfg["acabados"] = _normalize_acabados_catalog(cfg.get("acabados", default.get("acabados", [])))

    # -------------------------
    # Impresión
    # -------------------------
    imp = cfg["impresion"]
    def_imp = default.get("impresion", {})

    imp.setdefault("mo_dep", def_imp.get("mo_dep", 0.0))

    if "cobertura_op" not in imp and "cobertura" in imp:
        imp["cobertura_op"] = imp["cobertura"]
    imp.setdefault("cobertura_op", def_imp.get("cobertura_op", def_imp.get("cobertura", 0.0)))

    if "tinta_cmyk_base" not in imp and "tinta" in imp:
        imp["tinta_cmyk_base"] = imp["tinta"]
    imp.setdefault("tinta_cmyk_base", def_imp.get("tinta_cmyk_base", def_imp.get("tinta", 0.0)))

    if "click_base" not in imp and "click" in imp:
        imp["click_base"] = imp["click"]
    imp.setdefault("click_base", def_imp.get("click_base", def_imp.get("click", 0.0)))

    imp.setdefault("cobertura_tinta_base_pct", def_imp.get("cobertura_tinta_base_pct", 7.5))

    for k in ["mo_dep", "cobertura_op", "tinta_cmyk_base", "click_base", "cobertura_tinta_base_pct"]:
        imp[k] = _to_float(imp.get(k, def_imp.get(k, 0.0)), def_imp.get(k, 0.0))

    imp.pop("cobertura_tinta_pct", None)

    # legacy
    imp.setdefault("tinta", imp.get("tinta_cmyk_base", 0.0))
    imp.setdefault("click", imp.get("click_base", 0.0))
    imp.setdefault("cobertura", imp.get("cobertura_op", 0.0))

    # -------------------------
    # Papel
    # -------------------------
    pap = cfg["papel"]
    def_pap = default.get("papel", {})

    legacy_costo = pap.get("costo_kg", None)
    if legacy_costo is None:
        legacy_costo = def_pap.get("cuche_costo_kg", 0.0)
    legacy_costo = _to_float(legacy_costo, def_pap.get("cuche_costo_kg", 0.0))

    pap.setdefault("cuche_costo_kg", legacy_costo)
    pap.setdefault("bond_costo_kg", legacy_costo)
    pap.setdefault("especial_costo_kg", legacy_costo)

    for k in ["cuche_costo_kg", "bond_costo_kg", "especial_costo_kg"]:
        pap[k] = _to_float(pap.get(k, def_pap.get(k, legacy_costo)), def_pap.get(k, legacy_costo))

    pap["merma"] = _to_float(pap.get("merma", def_pap.get("merma", 0.0)), def_pap.get("merma", 0.0))

    # -------------------------
    # Margen
    # -------------------------
    cfg["margen"].setdefault("margen", default.get("margen", {}).get("margen", 0.0))
    cfg["margen"]["margen"] = _to_float(cfg["margen"].get("margen", 0.0), default.get("margen", {}).get("margen", 0.0))

    return cfg


# -------------------------
# API pública
# -------------------------
def get_config() -> dict:
    if "config" in st.session_state:
        default = _get_default_config()
        st.session_state.config = _normalize_config(st.session_state.config, default)
        return st.session_state.config

    default = _get_default_config()

    cfg = _load_json(CONFIG_PATH)
    if not isinstance(cfg, dict):
        _write_json(CONFIG_PATH, default)
        cfg = copy.deepcopy(default)

    cfg = _normalize_config(cfg, default)
    _write_json(CONFIG_PATH, cfg)

    st.session_state.config = cfg
    return st.session_state.config


def save_config(cfg: dict) -> None:
    default = _get_default_config()
    cfg = _normalize_config(cfg, default)
    st.session_state.config = cfg
    _write_json(CONFIG_PATH, cfg)


def reset_config() -> None:
    default = _get_default_config()
    save_config(copy.deepcopy(default))

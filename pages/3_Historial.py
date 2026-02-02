import sys
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth_users_yaml import require_login
from lib.permissions import permissions_for, normalize_role
from lib.supa import get_supabase
from lib.excel_exporter import build_quote_excel_bytes
from lib.pdf_exporter import build_quote_pdf_bytes
from lib.ui import inject_global_css, render_header, hr, section_open, section_close

st.set_page_config(page_title="Historial — Offset Santiago", layout="wide")
inject_global_css()

user = require_login()
perms = permissions_for(user.role)

render_header(
    "Historial de cotizaciones",
    "Busca, abre detalle y exporta PDF/Excel (según permisos)"
)

sb = get_supabase()
role = normalize_role(user.role)   # admin/cotizador/vendedor
username = user.username


# -----------------------------
# Helpers (seguridad)
# -----------------------------
SAFE_INPUT_KEYS_FOR_VENDEDOR = {
    "tipo_producto",
    "tiraje_piezas",
    "tiraje_libros",
    "paginas_por_libro",
    "paginas_totales",
    "lados",
    "ancho_final_cm",
    "alto_final_cm",
    "hoja_w_cm",
    "hoja_h_cm",
    "area_w_cm",
    "area_h_cm",
    "bleed_cm",
    "gutter_cm",
    "allow_rotate",
    "piezas_por_lado",
    "orientacion",
    "tipo_papel",
    "papel_gramaje_gm2",
    "n_tintas",
    "clicks_maquina",
    "clicks_facturable",
    "hojas_fisicas",
    "hojas_con_merma",
    "factor_carta",
}

def sanitize_row_for_vendedor(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evita fugas: quita breakdown/config_snapshot y limpia inputs (costos aplicados, etc.).
    Mantiene price_total/price_unit y campos básicos para PDF cliente.
    """
    out = dict(row or {})
    out.pop("config_snapshot", None)

    # breakdown fuera
    out["breakdown"] = {}

    # inputs limitados
    inputs = out.get("inputs") or {}
    safe_inputs = {k: inputs.get(k) for k in SAFE_INPUT_KEYS_FOR_VENDEDOR if k in inputs}
    out["inputs"] = safe_inputs

    return out

def money(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return str(x)


# -----------------------------
# Fetchers
# -----------------------------
def fetch_quotes(limit: int = 200, only_mine: bool = False):
    # NOTA: tu tabla parece traer quote_number; si no existe, igual funciona sin ese campo.
    cols = "quote_code, created_at, created_by, created_role, customer_name, price_unit, price_total, currency, quote_number"
    q = sb.table("quotes").select(cols)

    # Orden: si existe quote_number úsalo; si no, usa created_at
    try:
        q = q.order("quote_number", desc=True)
    except Exception:
        try:
            q = q.order("created_at", desc=True)
        except Exception:
            pass

    q = q.limit(limit)

    if only_mine:
        q = q.eq("created_by", username)

    res = q.execute()
    return res.data or []

from postgrest.exceptions import APIError

def fetch_quote_detail(quote_code: str):
    try:
        res = (
            sb.table("quotes")
            .select("*")
            .eq("quote_code", quote_code)
            .limit(1)
            .execute()
        )
        data = getattr(res, "data", None) or []
        return data[0] if data else None

    except APIError as e:
        st.error("Supabase rechazó la consulta al abrir detalle.")
        # PostgREST suele traer un dict con message/details/hint
        st.write("Detalle del error (APIError):")
        st.json(getattr(e, "message", None) or getattr(e, "args", None) or {"error": str(e)})
        return None

    except Exception as e:
        st.error("Error inesperado al abrir detalle.")
        st.exception(e)
        return None



# -----------------------------
# Filtros
# -----------------------------
st.subheader("Filtros")

c1, c2, c3, c4 = st.columns([1, 1, 1, 2])

with c1:
    limit = st.number_input("Máximo a mostrar", min_value=20, max_value=1000, value=200, step=20)

with c2:
    only_mine_default = True if role == "vendedor" else False
    only_mine = st.checkbox("Solo mis cotizaciones", value=only_mine_default)

with c3:
    search_number = st.text_input("Buscar por No. de cotización", placeholder="00000")

# -----------------------------
# Lista
# -----------------------------
data = fetch_quotes(limit=int(limit), only_mine=only_mine)
df = pd.DataFrame(data)

if df.empty:
    st.info("Aún no hay cotizaciones guardadas.")
    st.stop()

# -----------------------------
# Dropdown de usuarios (desde los datos)
# -----------------------------
users = sorted([u for u in df.get("created_by", pd.Series([])).dropna().unique().tolist() if str(u).strip()])
user_options = ["(Todos)"] + users

with c4:
    search_user = st.selectbox("Filtrar por usuario", options=user_options, index=0, key="user_filter")

# -----------------------------
# Filtros client-side
# -----------------------------
if search_number.strip():
    try:
        n = int(search_number.strip())
        if "quote_number" in df.columns:
            df = df[df["quote_number"] == n]
        else:
            st.warning("Esta base no tiene quote_number; filtra por ID (quote_code).")
    except ValueError:
        st.warning("El No. de cotización debe ser un número (ej. 154).")

if search_user != "(Todos)" and "created_by" in df.columns:
    df = df[df["created_by"] == search_user]

# -----------------------------
# Formato para mostrar
# -----------------------------
df_show = df.copy()

if "created_at" in df_show.columns:
    df_show["created_at"] = pd.to_datetime(df_show["created_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")

if "price_unit" in df_show.columns:
    df_show["price_unit"] = df_show["price_unit"].apply(money)

if "price_total" in df_show.columns:
    df_show["price_total"] = df_show["price_total"].apply(money)

st.subheader("Cotizaciones")
st.caption("Tip: busca por No. (si existe) o filtra por usuario.")

# Column config robusta (si faltan columnas, Streamlit ignora)
st.dataframe(
    df_show,
    use_container_width=True,
    hide_index=True,
    column_config={
        "quote_number": st.column_config.NumberColumn("No."),
        "quote_code": st.column_config.TextColumn("ID"),
        "created_at": st.column_config.TextColumn("Fecha"),
        "created_by": st.column_config.TextColumn("Usuario"),
        "created_role": st.column_config.TextColumn("Rol"),
        "customer_name": st.column_config.TextColumn("Cliente"),
        "price_unit": st.column_config.TextColumn("Unitario"),
        "price_total": st.column_config.TextColumn("Total"),
        "currency": st.column_config.TextColumn("Moneda"),
    },
)

# -----------------------------
# Abrir detalle
# -----------------------------
st.divider()
st.subheader("Abrir cotización")

ids = df["quote_code"].astype(str).tolist() if "quote_code" in df.columns else []
if not ids:
    st.info("No hay IDs disponibles.")
    st.stop()

pick = st.selectbox("Selecciona una cotización", options=ids, index=0)
open_btn = st.button("📄 Abrir detalle")

if not open_btn:
    st.stop()

row = fetch_quote_detail(pick)
if not row:
    st.error("No se encontró esa cotización en la base.")
    st.stop()

st.success(f"Cotización: {row.get('quote_code')}")

# -----------------------------
# Preparar exports (según permisos)
# -----------------------------
row_for_pdf = row
if not perms.can_view_costs:
    # vendedor: pasamos payload sanitizado al exporter para evitar fugas involuntarias
    row_for_pdf = sanitize_row_for_vendedor(row)

pdf_bytes = build_quote_pdf_bytes(row) # PDF cliente: permitido para todos

excel_bytes = None
if perms.can_export_tech:
    excel_bytes = build_quote_excel_bytes(row, role=role)  # técnico: solo admin/cotizador

# -----------------------------
# Job Card (Detalle)
# -----------------------------
inputs = row.get("inputs") or {}
breakdown = row.get("breakdown") or {}
tot = (breakdown.get("totales") or {}) if isinstance(breakdown, dict) else {}

tipo = inputs.get("tipo_producto", "")
ancho = inputs.get("ancho_final_cm")
alto = inputs.get("alto_final_cm")
lados = inputs.get("lados", 2 if "Libro" in str(tipo) else 1)

piezas_por_lado = inputs.get("piezas_por_lado")
orient = inputs.get("orientacion")
hojas_fisicas = inputs.get("hojas_fisicas") or ((breakdown.get("papel", {}) or {}).get("hojas_fisicas") if isinstance(breakdown, dict) else None)

price_unit = tot.get("precio_unitario", row.get("price_unit"))
price_total = tot.get("precio_total", row.get("price_total"))

created_by = str(row.get("created_by") or "")
created_role = str(row.get("created_role") or "")
created_at = str(row.get("created_at") or "")

def fmt_cm(x):
    try:
        return f"{float(x):.1f}"
    except Exception:
        return ""

if tipo == "Extendido":
    tiraje_txt = f"{inputs.get('tiraje_piezas', '')} pzas"
    imp_txt = "Frente" if int(lados) == 1 else "Frente y vuelta"
else:
    tiraje_txt = f"{inputs.get('tiraje_libros', '')} libros"
    pags = inputs.get("paginas_por_libro")
    if pags:
        tiraje_txt += f" · {pags} pág"
    imp_txt = "Frente y vuelta"

section_open()

colL, colR = st.columns([3, 2], vertical_alignment="center")
with colL:
    st.markdown(
        f"""
        <div class="h1">Cotización {row.get('quote_code')}</div>
        <div class="sub">{tipo} · {fmt_cm(ancho)} × {fmt_cm(alto)} cm · {tiraje_txt}</div>
        <div style="margin-top:10px;">
          <span class="pill">Impresión: {imp_txt}</span>
          <span class="pill">UP: {piezas_por_lado} ({orient})</span>
          <span class="pill">Tabloides: {hojas_fisicas}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

with colR:
    st.markdown(
        f"""
        <div class="small-metric"><b>Precio unitario</b><br><span class="val">{money(price_unit)}</span></div>
        <div style="height:10px;"></div>
        <div class="small-metric"><b>Precio total</b><br><span class="val">{money(price_total)}</span></div>
        """,
        unsafe_allow_html=True
    )

hr()

a1, a2 = st.columns([1.2, 1.0], vertical_alignment="center")

with a1:
    st.download_button(
        label="📄 PDF cliente",
        data=pdf_bytes,
        file_name=f"Cotizacion_{row.get('quote_code')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

with a2:
    if excel_bytes is not None:
        st.download_button(
            label="📊 Excel técnico",
            data=excel_bytes,
            file_name=f"Cotizacion_{row.get('quote_code')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.caption("Excel: solo admin/cotizador")

hr()

tab1, tab2 = st.tabs(["🧾 Comercial", "🛠️ Técnico"])

with tab1:
    cA, cB, cC, cD = st.columns(4)
    cA.metric("Precio unitario", money(row.get("price_unit")))
    cB.metric("Precio total", money(row.get("price_total")))
    cC.metric("Usuario", created_by)
    cD.metric("Rol", created_role)

    if created_at:
        st.write(f"**Fecha:** {created_at}")
    if row.get("customer_name"):
        st.write(f"**Cliente:** {row.get('customer_name')}")
    if row.get("notes"):
        st.write(f"**Notas:** {row.get('notes')}")

with tab2:
    if not perms.can_view_costs:
        st.info("Vista técnica disponible solo para admin/cotizador.")
    else:
        papel = (breakdown.get("papel", {}) or {}) if isinstance(breakdown, dict) else {}
        imp = (breakdown.get("impresion", {}) or {}) if isinstance(breakdown, dict) else {}
        adic = (breakdown.get("adicionales", {}) or {}) if isinstance(breakdown, dict) else {}

        st.write("### Operación")
        st.write({
            "Carta-lado (facturable)": imp.get("unidades_carta_lado"),
            "Clicks máquina": inputs.get("clicks_maquina") or imp.get("clicks_maquina"),
            "Tabloides (papel)": hojas_fisicas,
            "UP por lado": piezas_por_lado,
            "Orientación": orient,
            "Huella (cm)": f"{inputs.get('area_w_cm')} x {inputs.get('area_h_cm')}",
            "Hoja (cm)": f"{inputs.get('hoja_w_cm')} x {inputs.get('hoja_h_cm')}",
            "Bleed (cm)": inputs.get("bleed_cm"),
            "Gutter (cm)": inputs.get("gutter_cm"),
        })

        st.write("### Costos (resumen)")
        st.write({
            "Impresión": imp.get("total"),
            "Papel": papel.get("total"),
            "Adicionales": adic.get("total"),
            "Subtotal antes margen": tot.get("subtotal_antes_margen"),
            "Margen": tot.get("margen"),
            "Precio total": tot.get("precio_total"),
        })

section_close()

# -----------------------------
# Detalle técnico (JSON) — solo admin/cotizador
# -----------------------------
if not perms.can_view_costs:
    st.info("Vista vendedor: ocultando desglose y snapshot.")
    st.stop()

st.divider()
st.subheader("Detalle técnico (Admin/Cotizador)")

snapshot = row.get("config_snapshot") or {}

with st.expander("Inputs (lo que se capturó)", expanded=True):
    st.json(inputs)

with st.expander("Desglose (impresión / papel / adicionales / totales)", expanded=True):
    st.json(breakdown)

with st.expander("Snapshot de configuración usada (para que el pasado no cambie)", expanded=False):
    st.json(snapshot)

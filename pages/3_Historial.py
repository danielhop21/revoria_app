import streamlit as st
import pandas as pd
from lib.supa import get_supabase
from lib.auth import require_role

st.set_page_config(page_title="Historial", layout="wide")

# Permisos: todos los roles que pueden ver historial
require_role({"admin", "cotizador", "sales"})

sb = get_supabase()
role = st.session_state.auth.get("role")
user = st.session_state.auth.get("user")

st.title("Historial de cotizaciones")

# -----------------------------
# Helpers
# -----------------------------
def fetch_quotes(limit: int = 200, only_mine: bool = False):
    q = sb.table("quotes").select(
        "quote_number, quote_code, created_at, created_by, created_role, customer_name, price_unit, price_total, currency"
    ).order("quote_number", desc=True).limit(limit)

    if only_mine:
        q = q.eq("created_by", user)

    res = q.execute()
    return res.data or []

def fetch_quote_detail(quote_code: str):
    res = sb.table("quotes").select("*").eq("quote_code", quote_code).limit(1).execute()
    data = res.data or []
    return data[0] if data else None

def money(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return str(x)

# -----------------------------
# Filtros
# -----------------------------
st.subheader("Filtros")

c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1:
    limit = st.number_input("Máximo a mostrar", min_value=20, max_value=1000, value=200, step=20)
with c2:
    only_mine_default = True if role == "sales" else False
    only_mine = st.checkbox("Solo mis cotizaciones", value=only_mine_default)
with c3:
    search_code = st.text_input("Buscar por ID (quote_code)", placeholder="Q-20260128-153012-AB12")
with c4:
    search_user = st.text_input("Filtrar por usuario", placeholder="daniel / ventas1 (opcional)")

# -----------------------------
# Lista
# -----------------------------
data = fetch_quotes(limit=int(limit), only_mine=only_mine)
df = pd.DataFrame(data)

if df.empty:
    st.info("Aún no hay cotizaciones guardadas.")
    st.stop()

# filtros client-side
if search_code.strip():
    df = df[df["quote_code"].astype(str).str.contains(search_code.strip(), case=False, na=False)]

if search_user.strip():
    df = df[df["created_by"].astype(str).str.contains(search_user.strip(), case=False, na=False)]

# Formato simple para mostrar
df_show = df.copy()
df_show["created_at"] = pd.to_datetime(df_show["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
df_show["price_unit"] = df_show["price_unit"].apply(money)
df_show["price_total"] = df_show["price_total"].apply(money)

st.subheader("Cotizaciones")
st.caption("Tip: copia el ID y pégalo en el buscador si quieres abrir una específica rápido.")

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

# selector rápido con los primeros IDs en la tabla actual
ids = df["quote_code"].astype(str).tolist()
default_id = ids[0] if ids else ""
pick = st.selectbox("Selecciona una cotización", options=ids, index=0)

open_btn = st.button("📄 Abrir detalle")

if not open_btn:
    st.stop()

row = fetch_quote_detail(pick)

if not row:
    st.error("No se encontró esa cotización en la base.")
    st.stop()

st.success(f"Cotización: {row['quote_code']}")

# Vista comercial (todos)
cA, cB, cC, cD = st.columns(4)
cA.metric("Precio unitario", money(row.get("price_unit")))
cB.metric("Precio total", money(row.get("price_total")))
cC.metric("Usuario", str(row.get("created_by")))
cD.metric("Rol", str(row.get("created_role")))

st.write(f"**Fecha:** {str(row.get('created_at'))}")
if row.get("customer_name"):
    st.write(f"**Cliente:** {row.get('customer_name')}")

# -----------------------------
# Permisos de detalle
# -----------------------------
if role == "sales":
    st.info("Vista de ventas: solo totales. (Admin/Cotizador ven desglose completo).")
    st.stop()

# Admin/Cotizador: detalle técnico
st.divider()
st.subheader("Detalle técnico (Admin/Cotizador)")

inputs = row.get("inputs") or {}
breakdown = row.get("breakdown") or {}
snapshot = row.get("config_snapshot") or {}

with st.expander("Inputs (lo que se capturó)", expanded=True):
    st.json(inputs)

with st.expander("Desglose (impresión / papel / adicionales / totales)", expanded=True):
    st.json(breakdown)

with st.expander("Snapshot de configuración usada (para que el pasado no cambie)", expanded=False):
    st.json(snapshot)

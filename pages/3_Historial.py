import streamlit as st
import pandas as pd

from lib.supa import get_supabase
from lib.auth import require_role
from lib.excel_exporter import build_quote_excel_bytes
from lib.pdf_exporter import build_quote_pdf_bytes
from lib.ui import inject_global_css, render_header, card_open, card_close, hr

st.set_page_config(page_title="Historial — Offset Santiago", layout="wide")
inject_global_css()
require_role({"admin", "cotizador", "sales"})

render_header(
    "Historial de cotizaciones",
    "Busca, abre detalle y exporta PDF/Excel"
)

sb = get_supabase()
role = st.session_state.auth.get("role")
user = st.session_state.auth.get("user")

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

def fetch_quote_by_code(quote_code: str) -> dict | None:
    sb = get_supabase()
    res = sb.table("quotes").select("*").eq("quote_code", quote_code).limit(1).execute()
    data = getattr(res, "data", None) or []
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
users = sorted([u for u in df["created_by"].dropna().unique().tolist() if str(u).strip()])
user_options = ["(Todos)"] + users

search_user = st.selectbox(
    "Filtrar por usuario",
    options=user_options,
    index=0,
    key="user_filter"
)

# -----------------------------
# Filtros client-side
# -----------------------------
# 1) Buscar por No. de cotización (en vez de ID)
# Asegúrate de que arriba en Filtros tienes: search_number = st.text_input(...)
if search_number.strip():
    try:
        n = int(search_number.strip())
        df = df[df["quote_number"] == n]
    except ValueError:
        st.warning("El No. de cotización debe ser un número (ej. 154).")

# 2) Filtrar por usuario (dropdown)
if search_user != "(Todos)":
    df = df[df["created_by"] == search_user]

# -----------------------------
# Formato simple para mostrar
# -----------------------------
df_show = df.copy()
df_show["created_at"] = pd.to_datetime(df_show["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
df_show["price_unit"] = df_show["price_unit"].apply(money)
df_show["price_total"] = df_show["price_total"].apply(money)

st.subheader("Cotizaciones")
st.caption("Tip: busca por No. (ej. 154) o filtra por usuario.")

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

# -----------------------------
# Exportar (PDF / Excel)
# -----------------------------
role = st.session_state.auth.get("role", "")

# PDF cliente: sales + admin/cotizador
if role in {"admin", "cotizador", "sales"}:
    pdf_bytes = build_quote_pdf_bytes(row)
    st.download_button(
        label="⬇️ Descargar PDF (cliente)",
        data=pdf_bytes,
        file_name=f"Cotizacion_{row['quote_code']}.pdf",
        mime="application/pdf"
    )

# Excel técnico: solo admin/cotizador
if role in {"admin", "cotizador"}:
    excel_bytes = build_quote_excel_bytes(row, role=role)
    st.download_button(
        label="⬇️ Descargar Excel (desglose técnico)",
        data=excel_bytes,
        file_name=f"Cotizacion_{row['quote_code']}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Ventas puede descargar PDF (cliente). Excel solo admin/cotizador.")

# -----------------------------
# Job Card (Detalle)
# -----------------------------
inputs = row.get("inputs") or {}
breakdown = row.get("breakdown") or {}
tot = breakdown.get("totales") or {}

tipo = inputs.get("tipo_producto", "")
ancho = inputs.get("ancho_final_cm")
alto = inputs.get("alto_final_cm")
lados = inputs.get("lados", 2 if "Libro" in str(tipo) else 1)

piezas_por_lado = inputs.get("piezas_por_lado")
orient = inputs.get("orientacion")
hojas_fisicas = inputs.get("hojas_fisicas") or (breakdown.get("papel", {}) or {}).get("hojas_fisicas")

price_unit = tot.get("precio_unitario", row.get("price_unit"))
price_total = tot.get("precio_total", row.get("price_total"))

role = st.session_state.auth.get("role", "")
created_by = str(row.get("created_by") or "")
created_role = str(row.get("created_role") or "")
created_at = str(row.get("created_at") or "")

def fmt_cm(x):
    try:
        return f"{float(x):.1f}"
    except Exception:
        return ""

# Tiraje / impresión legible
if tipo == "Extendido":
    tiraje_txt = f"{inputs.get('tiraje_piezas', '')} pzas"
    imp_txt = "Frente" if int(lados) == 1 else "Frente y vuelta"
else:
    tiraje_txt = f"{inputs.get('tiraje_libros', '')} libros"
    pags = inputs.get("paginas_por_libro")
    if pags:
        tiraje_txt += f" · {pags} pág"
    imp_txt = "Frente y vuelta"

# Card
card_open()

colL, colR = st.columns([3, 2], vertical_alignment="center")
with colL:
    st.markdown(
        f"""
        <div class="h1">Cotización {row['quote_code']}</div>
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

# Action bar (PDF primero = primario)
st.markdown('<div class="actionbar">', unsafe_allow_html=True)
a1, a2 = st.columns([1.2, 1.0], vertical_alignment="center")

with a1:
    # PDF cliente: sales + admin/cotizador
    if role in {"admin", "cotizador", "sales"}:
        pdf_bytes = build_quote_pdf_bytes(row)
        st.download_button(
            label="📄 PDF cliente",
            data=pdf_bytes,
            file_name=f"Cotizacion_{row['quote_code']}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

with a2:
    # Excel técnico: solo admin/cotizador
    if role in {"admin", "cotizador"}:
        excel_bytes = build_quote_excel_bytes(row, role=role)
        st.download_button(
            label="📊 Excel técnico",
            data=excel_bytes,
            file_name=f"Cotizacion_{row['quote_code']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.caption("Excel: solo admin/cotizador")

st.markdown('</div>', unsafe_allow_html=True)

hr()

# Tabs: Comercial vs Técnico
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
    if role not in {"admin", "cotizador"}:
        st.info("Vista técnica disponible solo para admin/cotizador.")
    else:
        papel = breakdown.get("papel", {}) or {}
        imp = breakdown.get("impresion", {}) or {}
        adic = breakdown.get("adicionales", {}) or {}

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

card_close()


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

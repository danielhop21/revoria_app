import streamlit as st
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO_PATH = ASSETS / "logo_offset_santiago.png"


def inject_global_css() -> None:
    st.markdown("""
    <style>
      :root{
        --radius: 16px;
        --card-bg: #FFFFFF;
        --card-border: rgba(17,24,39,0.08);
        --shadow: 0 8px 20px rgba(17,24,39,0.06);
        --muted: rgba(17,24,39,0.55);

      }

      /* Contenedor general */
      .block-container {
        padding-top: 2.5rem;
        padding-bottom: 2.5rem;
        max-width: 1180px;
      }

      /* Cards */
      .os-card{
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: var(--radius);
        padding: 16px 16px;
        box-shadow: var(--shadow);
      }

      /* Encabezados */
      .os-h1{
        font-size: 1.25rem;
        font-weight: 750;
        margin: 0 0 4px 0;
        letter-spacing: -0.2px;
      }
      .os-sub{
        font-size: 0.95rem;
        margin: 0;
        color: var(--muted);
      }

      /* Pills */
      .os-pill{
        display:inline-block;
        padding: 5px 10px;
        border-radius: 999px;
        border: 1px solid rgba(15,23,34,0.12);
        font-size: 0.82rem;
        color: rgba(15,23,34,0.82);
        margin-right: 6px;
        margin-bottom: 6px;
        background: rgba(15,23,34,0.03);
      }

      /* Separador editorial (muy ligero) */
      .os-hr{
        height:1px;
        background: rgba(17,24,39,0.06);
        border:none;
        margin: 16px 0;
      }

      }

      /* Barra de acciones: botones más “producto” */
      .actionbar div.stDownloadButton > button,
      .actionbar div.stButton > button{
        border-radius: 12px !important;
        padding: 10px 14px !important;
        font-weight: 650 !important;
      }

      /* El primer botón del actionbar = primario */
      .actionbar div.stDownloadButton:first-child > button{
        border: 1px solid rgba(79,70,229,0.25) !important;
      }

      /* Métrica compacta (nuevo: compatible con tu código actual) */
      .small-metric {
        font-size: 0.85rem;
        opacity: 0.90;
        line-height: 1.2;
      }
      .small-metric b {
        font-size: 0.85rem;
      }
      .small-metric .val {
        font-size: 1.05rem;
        font-weight: 800;
        letter-spacing: -0.2px;
      }

      /* Métrica compacta (OS style) */
      .os-metric-label{
        font-size: 0.85rem;
        color: var(--muted);
        margin: 0;
      }
      .os-metric-val{
        font-size: 1.15rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.2px;
      }
      /* ==============================
        Inputs (login, text, password)
        ============================== */

      /* Contenedor del input (Streamlit / BaseWeb) */
      div[data-baseweb="input"] > div {
        background-color: rgba(17, 24, 39, 0.07) !important;   /* ⬅️ MÁS OSCURO */
        border: 1px solid rgba(17, 24, 39, 0.35) !important;   /* ⬅️ borde visible */
        border-radius: 10px !important;
      }
  
      /* Texto dentro del input */
      input {
        background-color: transparent !important;
        color: #111827 !important;
        font-weight: 500;
      }

      /* Placeholder */
      input::placeholder {
        color: rgba(17, 24, 39, 0.55) !important;
      }

      /* Focus */
      div[data-baseweb="input"] > div:focus-within {
        background-color: rgba(17, 24, 39, 0.14) !important;   /* ⬅️ aún más oscuro */
        border: 1px solid rgba(79, 70, 229, 0.55) !important;
        box-shadow: 0 0 0 1px rgba(79, 70, 229, 0.18) !important;
      }
      
    </style>
    """, unsafe_allow_html=True)


def card_open() -> None:
    st.markdown('<div class="os-card">', unsafe_allow_html=True)


def card_close() -> None:
    st.markdown('</div>', unsafe_allow_html=True)

def section_open() -> None:
    st.markdown('<div style="border-top:1px solid rgba(17,24,39,0.06); padding-top:14px;">', unsafe_allow_html=True)

def section_close() -> None:
    st.markdown('</div>', unsafe_allow_html=True)

def hr() -> None:
    st.markdown('<hr class="os-hr" />', unsafe_allow_html=True)


def render_header(title: str, subtitle: str | None = None) -> None:
    """Header consistente para TODAS las páginas."""
    cols = st.columns([1.2, 6], vertical_alignment="center")
    with cols[0]:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
        else:
            st.write("Offset Santiago")
    with cols[1]:
        st.markdown(f"<div class='os-h1'>{title}</div>", unsafe_allow_html=True)
        if subtitle:
            st.markdown(f"<p class='os-sub'>{subtitle}</p>", unsafe_allow_html=True)
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

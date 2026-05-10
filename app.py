"""
app.py — Punto de entrada App Ofertas Knauf Industries.
Streamlit Cloud + Snowflake.
"""
import streamlit as st

st.set_page_config(page_title="Ofertas — Knauf Industries", page_icon="📄",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main .block-container { padding-top: 1rem; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a5276 0%, #2c3e50 100%);
    }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] .stRadio label {
        background: rgba(255,255,255,0.08); border-radius: 8px;
        padding: 8px 12px; margin: 2px 0; transition: all 0.2s;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.18);
    }
    [data-testid="stMetricValue"] { font-size: 1.4rem; color: #1a5276; }
    .stDataFrame { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

from auth import init_session, render_login
init_session()

if not st.session_state.authenticated:
    render_login()
    st.stop()

# Sidebar
with st.sidebar:
    st.markdown(f"### 👋 {st.session_state.user_nombre}")
    st.caption(f"📧 {st.session_state.user_email}")
    st.caption(f"🏷️ Rol: **{st.session_state.user_rol.upper()}**")
    st.markdown("---")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Routing
if st.session_state.user_rol == "admin":
    modo = st.sidebar.radio("Modo", ["⚙️ Administración", "🆕 Crear Oferta"])
    if modo.startswith("⚙"):
        from views_admin import render_admin
        render_admin()
    else:
        from views_comercial import render_comercial
        render_comercial()
else:
    from views_comercial import render_comercial
    render_comercial()

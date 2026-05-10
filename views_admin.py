"""
views_admin.py — Panel de administración.
"""
import streamlit as st
import pandas as pd
from data import (
    load_precios, save_precios_from_df,
    load_logistica, save_logistica_from_df,
    load_plantas, load_calidades, save_calidades_from_df,
    load_ofertas, load_oferta_lineas, load_users, save_users_from_df,
    get_config, set_config, GRUPOS_COMPRA
)


def render_admin():
    st.sidebar.markdown("### ⚙️ Panel Admin")
    menu = st.sidebar.radio("Sección", [
        "📋 Todas las Ofertas", "💰 Gestión Precios", "📦 Logística",
        "🏭 Plantas", "🏷️ Calidades", "👥 Usuarios", "⚙️ Configuración",
    ])
    if menu.startswith("📋"):   _section_ofertas()
    elif menu.startswith("💰"): _section_precios()
    elif menu.startswith("📦"): _section_logistica()
    elif menu.startswith("🏭"): _section_plantas()
    elif menu.startswith("🏷"):  _section_calidades()
    elif menu.startswith("👥"): _section_usuarios()
    elif menu.startswith("⚙"):  _section_config()


def _section_ofertas():
    st.markdown("## 📋 Histórico de Ofertas")
    df = load_ofertas()
    if df.empty:
        st.info("No hay ofertas registradas todavía.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        comerciales = ["Todos"] + sorted(df["COMERCIAL"].unique().tolist())
        sel_com = st.selectbox("Comercial", comerciales)
    with col2:
        estados = ["Todos"] + sorted(df["ESTADO"].unique().tolist())
        sel_est = st.selectbox("Estado", estados)
    with col3:
        grupos = ["Todos"] + sorted([g for g in df["GRUPO_COMPRA"].unique() if g])
        sel_grp = st.selectbox("Grupo de compra", grupos)

    filtered = df.copy()
    if sel_com != "Todos": filtered = filtered[filtered["COMERCIAL"] == sel_com]
    if sel_est != "Todos": filtered = filtered[filtered["ESTADO"] == sel_est]
    if sel_grp != "Todos": filtered = filtered[filtered["GRUPO_COMPRA"] == sel_grp]

    st.metric("Total ofertas", len(filtered), delta=f"{filtered['TOTAL'].sum():,.2f}€ acumulado")

    show_cols = ["NUMERO_OFERTA", "REVISION", "COMERCIAL", "FECHA",
                 "CLIENTE_NOMBRE", "GRUPO_COMPRA", "TOTAL", "ESTADO"]
    show_cols = [c for c in show_cols if c in filtered.columns]
    st.dataframe(filtered[show_cols].reset_index(drop=True), use_container_width=True, hide_index=True)

    if not filtered.empty:
        st.markdown("---")
        ids = filtered["NUMERO_OFERTA"].tolist()
        sel_id = st.selectbox("Ver detalle de oferta", ids)
        if sel_id:
            of_row = filtered[filtered["NUMERO_OFERTA"] == sel_id].iloc[0]
            oferta_id = int(of_row["ID"])
            lineas = load_oferta_lineas(oferta_id)
            st.json({k: str(v) for k, v in of_row.to_dict().items()})
            if not lineas.empty:
                st.dataframe(lineas, use_container_width=True, hide_index=True)


def _section_precios():
    st.markdown("## 💰 Gestión de Precios")
    st.caption("Sube un Excel con: PRODUCTO, CALIDAD, MINIMO_M3, BIGMAT, GAMMA, DAVSA, EMCCAT, ESTRATEGIAS_BIGMAT, IBRICKS, IDAPLAC")

    df_actual = load_precios()
    if not df_actual.empty:
        st.markdown("### Precios actuales")
        st.dataframe(df_actual, use_container_width=True, hide_index=True)

    uploaded = st.file_uploader("📁 Subir Excel de precios", type=["xlsx", "xls"], key="upload_precios")
    if uploaded:
        try:
            df_new = pd.read_excel(uploaded)
            df_new.columns = [c.strip().upper().replace(" ", "_") for c in df_new.columns]
            required = ["PRODUCTO", "CALIDAD", "MINIMO_M3"]
            if not all(c in df_new.columns for c in required):
                st.error(f"❌ Faltan columnas: {required}")
                return
            st.dataframe(df_new, use_container_width=True, hide_index=True)
            if st.button("✅ Guardar precios", key="save_precios"):
                save_precios_from_df(df_new)
                st.success(f"✅ {len(df_new)} precios actualizados")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")

    st.markdown("---")
    st.markdown("### Incremento clientes sin grupo de compra")
    inc_actual = float(get_config("incremento_no_grupo", "0") or 0)
    new_inc = st.number_input("Incremento sobre MÍNIMO M3 (€/m³)", value=inc_actual, step=0.5, format="%.2f")
    if st.button("Guardar incremento", key="save_inc"):
        set_config("incremento_no_grupo", str(new_inc))
        st.success(f"✅ Incremento: +{new_inc}€/m³")


def _section_logistica():
    st.markdown("## 📦 Logística")
    st.caption("Sube un Excel con: PRODUCTO, DIMENSION, ESPESOR, PZAS_PAQUETE, PZAS_BLOQUE")
    df = load_logistica()
    if not df.empty:
        productos = ["Todos"] + sorted(df["PRODUCTO"].unique().tolist())
        sel = st.selectbox("Filtrar por producto", productos)
        show = df if sel == "Todos" else df[df["PRODUCTO"] == sel]
        st.dataframe(show, use_container_width=True, hide_index=True)

    uploaded = st.file_uploader("📁 Subir Excel de logística", type=["xlsx", "xls"], key="upload_log")
    if uploaded:
        try:
            df_new = pd.read_excel(uploaded)
            df_new.columns = [c.strip().upper().replace(" ", "_") for c in df_new.columns]
            st.dataframe(df_new, use_container_width=True, hide_index=True)
            if st.button("✅ Guardar logística", key="save_log"):
                save_logistica_from_df(df_new)
                st.success(f"✅ {len(df_new)} registros actualizados")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")


def _section_plantas():
    st.markdown("## 🏭 Plantas de Producción")
    st.dataframe(load_plantas(), use_container_width=True, hide_index=True)


def _section_calidades():
    st.markdown("## 🏷️ Calidades por Producto")
    df = load_calidades()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    uploaded = st.file_uploader("📁 Subir Excel de calidades", type=["xlsx", "xls"], key="upload_cal")
    if uploaded:
        try:
            df_new = pd.read_excel(uploaded)
            df_new.columns = [c.strip().upper() for c in df_new.columns]
            st.dataframe(df_new, use_container_width=True, hide_index=True)
            if st.button("✅ Guardar calidades", key="save_cal"):
                save_calidades_from_df(df_new)
                st.success("✅ Calidades actualizadas")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")


def _section_usuarios():
    st.markdown("## 👥 Gestión de Usuarios")
    st.caption("Sube un Excel con: Email, Password, Nombre")
    users = load_users()
    if users:
        user_list = [{"Email": k, "Nombre": v["nombre"], "Rol": v["rol"]} for k, v in users.items()]
        st.dataframe(pd.DataFrame(user_list), use_container_width=True, hide_index=True)
    uploaded = st.file_uploader("📁 Subir Excel de usuarios", type=["xlsx", "xls"], key="upload_users")
    if uploaded:
        try:
            df_new = pd.read_excel(uploaded)
            st.dataframe(df_new, use_container_width=True, hide_index=True)
            if st.button("✅ Guardar usuarios", key="save_users"):
                save_users_from_df(df_new)
                st.success("✅ Usuarios actualizados")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")


def _section_config():
    st.markdown("## ⚙️ Configuración")

    st.markdown("### 🖼️ Logo de la empresa")
    logo_file = st.file_uploader("Subir logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="upload_logo")
    if logo_file:
        import base64
        logo_b64 = base64.b64encode(logo_file.read()).decode()
        set_config("logo_base64", logo_b64)
        st.success("✅ Logo actualizado")

    st.markdown("### 🏷️ Impuesto al plástico")
    imp_actual = float(get_config("impuesto_plastico_kg", "0.45") or 0.45)
    new_imp = st.number_input("€/kg", value=imp_actual, step=0.01, format="%.2f")
    if st.button("Guardar impuesto", key="save_imp"):
        set_config("impuesto_plastico_kg", str(new_imp))
        st.success("✅ Actualizado")

    st.markdown("### 📜 Condiciones legales")
    cond = get_config("condiciones_legales", "")
    new_cond = st.text_area("Texto de condiciones", value=cond, height=200)
    if st.button("Guardar condiciones", key="save_cond"):
        set_config("condiciones_legales", new_cond)
        st.success("✅ Actualizado")

    st.markdown("### 🏢 Datos empresa (pie PDF)")
    for key, label in [("empresa_nombre", "Nombre"), ("empresa_direccion", "Dirección"),
                       ("empresa_cif", "CIF"), ("empresa_registro", "Registro mercantil")]:
        val = get_config(key, "")
        new_val = st.text_input(label, value=val, key=f"cfg_{key}")
        if new_val != val:
            set_config(key, new_val)

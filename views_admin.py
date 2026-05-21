"""
views_admin.py — Panel de administración v2 (KTM integrado).
"""
import streamlit as st
import pandas as pd
from data import (
    load_tarifas, save_tarifas_from_df,
    load_clientes, save_clientes_from_df,
    load_transporte, save_transporte,
    load_materias_primas, save_materia_prima,
    load_logistica, save_logistica_from_df,
    load_plantas, load_ofertas, load_oferta_lineas,
    load_users, save_users_from_df,
    get_config, set_config, PLANTAS,
    update_oferta_estado, load_ofertas_pendientes,
    load_precios_grupos
)


def render_admin():
    st.sidebar.markdown("### ⚙️ Panel Admin")
    menu = st.sidebar.radio("Sección", [
        "✅ Validar Ofertas",
        "📋 Todas las Ofertas",
        "📊 Tarifas (€/m³)",
        "🏷️ Tarifas Grupos",
        "🏢 Clientes",
        "🧪 Materias Primas",
        "🚚 Transporte",
        "📦 Logística (Múltiplos)",
        "🏭 Plantas",
        "👥 Usuarios",
        "⚙️ Configuración",
    ])
    sections = {
        "✅": _section_validar,
        "📋": _section_ofertas,
        "📊": _section_tarifas,
        "🏷️": _section_tarifas_grupos,
        "🏢": _section_clientes,
        "🧪": _section_materias_primas,
        "🚚": _section_transporte,
        "📦": _section_logistica,
        "🏭": _section_plantas,
        "👥": _section_usuarios,
        "⚙": _section_config,
    }
    for key, func in sections.items():
        if menu.startswith(key):
            func()
            break


# ── OFERTAS ───────────────────────────────────────────────────────────────────

def _section_ofertas():
    st.markdown("## 📋 Histórico de Ofertas")
    df = load_ofertas()
    if df.empty:
        st.info("No hay ofertas registradas todavía.")
        return

    col1, col2 = st.columns(2)
    with col1:
        comerciales = ["Todos"] + sorted(df["COMERCIAL"].unique().tolist())
        sel_com = st.selectbox("Comercial", comerciales)
    with col2:
        estados = ["Todos"] + sorted(df["ESTADO"].unique().tolist())
        sel_est = st.selectbox("Estado", estados)

    filtered = df.copy()
    if sel_com != "Todos": filtered = filtered[filtered["COMERCIAL"] == sel_com]
    if sel_est != "Todos": filtered = filtered[filtered["ESTADO"] == sel_est]

    st.metric("Total ofertas", len(filtered), delta=f"{filtered['TOTAL'].sum():,.2f}€ acumulado")

    show_cols = ["NUMERO_OFERTA", "REVISION", "COMERCIAL", "FECHA",
                 "CLIENTE_NOMBRE", "TIPO_PRECIO", "TOTAL", "ESTADO"]
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


# ── VALIDAR OFERTAS ───────────────────────────────────────────────────────────

def _section_validar():
    st.markdown("## ✅ Validar Ofertas (Precio SIN Scrap)")
    st.caption("Ofertas que requieren aprobación antes de que el comercial pueda generar el PDF.")
    
    df = load_ofertas_pendientes()
    if df.empty:
        st.success("🎉 No hay ofertas pendientes de validación.")
        return
    
    st.metric("Ofertas pendientes", len(df))
    
    for idx, row in df.iterrows():
        oferta_id = int(row["ID"])
        numero = row.get("NUMERO_OFERTA", "?")
        cliente = row.get("CLIENTE_NOMBRE", "?")
        comercial_name = row.get("COMERCIAL_NOMBRE", row.get("COMERCIAL", "?"))
        total = float(row.get("TOTAL", 0))
        fecha = row.get("FECHA", "?")
        tipo_precio = row.get("TIPO_PRECIO", "SIN Scrap")
        
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            with col1:
                st.markdown(f"**{numero}**")
                st.caption(f"👤 {comercial_name} — 📅 {fecha}")
            with col2:
                st.markdown(f"🏢 {cliente}")
                st.caption(f"💰 Tipo: **{tipo_precio}**")
            with col3:
                st.metric("Total", f"{total:,.2f}€")
            with col4:
                # Detalle
                lineas_df = load_oferta_lineas(oferta_id)
                if not lineas_df.empty:
                    with st.expander("📄 Detalle"):
                        line_cols = ["TIPO_PRODUCTO", "CALIDAD", "DESCRIPCION", "CANTIDAD", "TOTAL_LINEA"]
                        line_cols = [c for c in line_cols if c in lineas_df.columns]
                        st.dataframe(lineas_df[line_cols], use_container_width=True, hide_index=True)
            
            col_a, col_r = st.columns(2)
            with col_a:
                if st.button("✅ Aprobar", key=f"approve_{oferta_id}", type="primary", use_container_width=True):
                    update_oferta_estado(oferta_id, "Validada")
                    st.success(f"✅ Oferta {numero} aprobada")
                    st.rerun()
            with col_r:
                if st.button("❌ Rechazar", key=f"reject_{oferta_id}", use_container_width=True):
                    update_oferta_estado(oferta_id, "Rechazada")
                    st.warning(f"❌ Oferta {numero} rechazada")
                    st.rerun()


# ── TARIFAS ───────────────────────────────────────────────────────────────────

def _section_tarifas():
    st.markdown("## 📊 Tarifas (€/m³ por familia, artículo y planta)")
    st.caption(
        "Sube un Excel con columnas: FAMILIA, ARTICULO, MATERIA_PRIMA, DENSIDAD, "
        "LAMBDA, PRECIO_VILAFRANCA, PRECIO_VALENCIA, PRECIO_VALLADOLID"
    )

    df = load_tarifas()
    if not df.empty:
        # Filtro por familia
        familias = ["Todas"] + sorted(df["FAMILIA"].unique().tolist())
        sel = st.selectbox("Filtrar por familia", familias)
        show = df if sel == "Todas" else df[df["FAMILIA"] == sel]
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.caption(f"📊 {len(df)} artículos en total")

    uploaded = st.file_uploader("📁 Subir Excel de tarifas", type=["xlsx", "xls"], key="upload_tarifas")
    if uploaded:
        try:
            df_new = pd.read_excel(uploaded)
            df_new.columns = [c.strip().upper().replace(" ", "_") for c in df_new.columns]
            required = ["FAMILIA", "ARTICULO", "MATERIA_PRIMA", "DENSIDAD"]
            missing = [c for c in required if c not in df_new.columns]
            if missing:
                st.error(f"❌ Faltan columnas: {missing}")
                return
            # Asegurar columnas de precio
            for col in ["PRECIO_VILAFRANCA", "PRECIO_VALENCIA", "PRECIO_VALLADOLID"]:
                if col not in df_new.columns:
                    df_new[col] = 0
            if "LAMBDA" not in df_new.columns:
                df_new["LAMBDA"] = 0
            st.dataframe(df_new, use_container_width=True, hide_index=True)
            st.caption(f"📊 {len(df_new)} artículos a importar")
            if st.button("✅ Guardar tarifas", key="save_tarifas"):
                save_tarifas_from_df(df_new)
                st.success(f"✅ {len(df_new)} tarifas actualizadas")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")


# ── CLIENTES ──────────────────────────────────────────────────────────────────

def _section_clientes():
    st.markdown("## 🏢 Base de Datos de Clientes")
    st.caption(
        "Sube un Excel con columnas: EMPRESA, CIF, CONTACTO_NOMBRE, "
        "CONTACTO_APELLIDO, EMAIL, TELEFONO, MOVIL, DIRECCION, CP_CIUDAD, "
        "COMERCIAL_ASIGNADO, MERCADO"
    )

    df = load_clientes()
    if not df.empty:
        busqueda = st.text_input("🔍 Buscar empresa", placeholder="Escribe nombre...")
        if busqueda:
            show = df[df["EMPRESA"].str.contains(busqueda.upper(), case=False, na=False)]
        else:
            show = df.head(50)
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.caption(f"📊 {len(df)} clientes en total")

    uploaded = st.file_uploader("📁 Subir Excel de clientes", type=["xlsx", "xls"], key="upload_clientes")
    if uploaded:
        try:
            df_new = pd.read_excel(uploaded)
            st.dataframe(df_new.head(20), use_container_width=True, hide_index=True)
            st.caption(f"📊 {len(df_new)} clientes a importar")
            if st.button("✅ Guardar clientes", key="save_clientes"):
                save_clientes_from_df(df_new)
                st.success(f"✅ {len(df_new)} clientes importados")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")


# ── MATERIAS PRIMAS ───────────────────────────────────────────────────────────

def _section_materias_primas():
    st.markdown("## 🧪 Precios Actuales de Materia Prima (€/kg)")
    st.info(
        "**Referencia KTM:** El sistema calcula el sobrecoste comparando tus precios actuales "
        "contra los valores base del KTM: **1.45€** (Blanco), **1.75€** (Grafito) y **3.00€** (Sostenible)."
    )
    st.caption(
        "Introduce aquí los precios reales de este mes. El incremento se calculará automáticamente "
        "como: (Precio Actual - Precio Referencia) × Densidad."
    )

    df = load_materias_primas()
    if not df.empty:
        st.dataframe(df[["TIPO", "PRECIO_BASE_KG"]].rename(columns={"PRECIO_BASE_KG": "PRECIO_ACTUAL_KG"}), 
                     use_container_width=True, hide_index=True)

    st.markdown("### ✏️ Actualizar Precios del Mes")
    tipos = ["EPS_Blanco", "EPS_Grafito", "EPS_SOSTENIBLES"]
    labels = {"EPS_Blanco": "EPS Blanco", "EPS_Grafito": "EPS Grafito", "EPS_SOSTENIBLES": "EPS Sostenibles"}
    defaults = {"EPS_Blanco": 1.45, "EPS_Grafito": 1.75, "EPS_SOSTENIBLES": 3.00}

    for tipo in tipos:
        current = defaults[tipo]
        if not df.empty:
            match = df[df["TIPO"] == tipo]
            if not match.empty:
                current = float(match.iloc[0]["PRECIO_BASE_KG"])
        new_val = st.number_input(
            f"Precio ACTUAL {labels[tipo]} (€/kg)", value=current, step=0.05,
            format="%.2f", key=f"mp_{tipo}"
        )
        if new_val != current:
            save_materia_prima(tipo, new_val)
            st.success(f"✅ {labels[tipo]} actualizado a {new_val} €/kg")


# ── TRANSPORTE ────────────────────────────────────────────────────────────────

def _section_transporte():
    st.markdown("## 🚚 Costes de Transporte por Planta")
    st.caption("€/m³ por defecto. Si el comercial no introduce un valor en € en la oferta, se aplica este coste.")

    df = load_transporte()
    defaults_min = {"Vilafranca": 110.0, "Valencia": 140.0, "Valladolid": 150.0}

    for planta in PLANTAS:
        st.markdown(f"### 🏭 {planta}")
        current_m3 = 0.0
        current_grp = 0.0
        current_min = defaults_min.get(planta, 0.0)
        if not df.empty:
            match = df[df["PLANTA"] == planta]
            if not match.empty:
                current_m3 = float(match.iloc[0].get("COSTE_M3", 0) or 0)
                current_grp = float(match.iloc[0].get("COSTE_GRUPAJE_M3", 0) or 0)
                current_min = float(match.iloc[0].get("MINIMO_TRANSPORTE", 0) or 0) or defaults_min.get(planta, 0.0)

        col1, col2, col3 = st.columns(3)
        with col1:
            new_m3 = st.number_input(f"Coste €/m³ ({planta})", value=current_m3,
                                     step=0.1, format="%.2f", key=f"tr_{planta}")
        with col2:
            new_grp = st.number_input(f"Grupaje €/m³ ({planta})", value=current_grp,
                                      step=0.1, format="%.2f", key=f"grp_{planta}")
        with col3:
            new_min = st.number_input(f"Mínimo € ({planta})", value=current_min,
                                      step=5.0, format="%.2f", key=f"min_{planta}")
        if new_m3 != current_m3 or new_grp != current_grp or new_min != current_min:
            save_transporte(planta, new_m3, new_grp, new_min)
            st.success(f"✅ {planta} actualizado")


# ── LOGÍSTICA (MÚLTIPLOS) ────────────────────────────────────────────────────

def _section_logistica():
    st.markdown("## 📦 Logística — Múltiplos de Empaquetado")
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


# ── PLANTAS ───────────────────────────────────────────────────────────────────

def _section_plantas():
    st.markdown("## 🏭 Plantas de Producción")
    st.caption("Dimensiones máximas de bloque por planta (largo × ancho × grueso en mm)")
    st.dataframe(load_plantas(), use_container_width=True, hide_index=True)


# ── USUARIOS ──────────────────────────────────────────────────────────────────

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


# ── CONFIG ────────────────────────────────────────────────────────────────────

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

    st.markdown("### 🏢 Datos empresa (cabecera y pie PDF)")
    for key, label in [("empresa_nombre", "Nombre"), ("empresa_direccion", "Dirección"),
                       ("empresa_telefono", "Teléfono"), ("empresa_cif", "CIF"),
                       ("empresa_registro", "Registro mercantil")]:
        val = get_config(key, "")
        new_val = st.text_input(label, value=val, key=f"cfg_{key}")
        if new_val != val:
            set_config(key, new_val)


# ── TARIFAS GRUPOS ───────────────────────────────────────────────────────────

def _section_tarifas_grupos():
    st.markdown("## 🏷️ Tarifas de Grupos de Compra")
    st.caption("Tarifas especiales cargadas desde el archivo de Precios de Grupos de Compra.")
    
    df = load_precios_grupos()
    if df.empty:
        st.warning("⚠️ No se han encontrado tarifas de grupos de compra en el sistema. Asegúrate de que el archivo Excel existe en la raíz del proyecto.")
        return

    # Filtro por artículo / familia
    articulos = ["Todos"] + sorted(df["ARTÍCULO"].unique().tolist())
    sel_art = st.selectbox("Filtrar por Familia / Artículo", articulos)
    
    filtered_df = df.copy()
    if sel_art != "Todos":
        filtered_df = filtered_df[filtered_df["ARTÍCULO"] == sel_art]
        
    st.metric("Total combinaciones con precio", len(filtered_df))
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

"""
views_comercial.py — Panel comercial: crear oferta → PDF → descargar.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from data import (
    load_ofertas, load_oferta_lineas,
    save_oferta, next_oferta_number, get_max_revision,
    get_calidades_producto, get_config, GRUPOS_COMPRA, load_plantas
)
from calculator import (
    calcular_linea_estandar, calcular_linea_medida,
    PRODUCTOS_ESTANDAR, PRODUCTOS_MEDIDA, TODOS_PRODUCTOS,
    get_dimensiones_disponibles, get_espesores_disponibles
)
from pdf_generator import generar_pdf_oferta


def render_comercial():
    st.sidebar.markdown(f"### 👤 {st.session_state.user_nombre}")
    menu = st.sidebar.radio("Menú", ["🆕 Nueva Oferta", "📋 Mis Ofertas"])
    if menu.startswith("🆕"):
        _new_oferta()
    else:
        _my_ofertas()


def _my_ofertas():
    st.markdown("## 📋 Mis Ofertas")
    df = load_ofertas(comercial=st.session_state.user_nombre)
    if df.empty:
        st.info("No tienes ofertas registradas.")
        return

    show_cols = ["NUMERO_OFERTA", "REVISION", "FECHA", "CLIENTE_NOMBRE",
                 "GRUPO_COMPRA", "TOTAL", "ESTADO"]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols].reset_index(drop=True), use_container_width=True, hide_index=True)

    st.markdown("---")
    sel = st.selectbox("Seleccionar oferta", df["NUMERO_OFERTA"].tolist())
    if sel:
        of_row = df[df["NUMERO_OFERTA"] == sel].iloc[0]
        oferta_id = int(of_row["ID"])
        lineas = load_oferta_lineas(oferta_id)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 Generar PDF"):
                config = _load_config_dict()
                pdf_bytes = generar_pdf_oferta(of_row.to_dict(), lineas, config)
                st.download_button("⬇️ Descargar PDF", data=pdf_bytes,
                                   file_name=f"{sel}_REV{of_row.get('REVISION',1)}.pdf",
                                   mime="application/pdf")
        with col2:
            if st.button("🔄 Nueva revisión"):
                _init_revision(of_row)
                st.rerun()


def _new_oferta():
    st.markdown("## 🆕 Nueva Oferta")
    if "oferta_lineas" not in st.session_state:
        st.session_state.oferta_lineas = []

    # Datos generales
    with st.expander("📌 Datos de la oferta", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha oferta", value=datetime.now().date())
            dias_validez = st.number_input("Días de validez", value=14, min_value=1, max_value=90)
            validez = fecha + timedelta(days=dias_validez)
            st.caption(f"Válida hasta: {validez.strftime('%d/%m/%Y')}")
        with col2:
            grupos = ["Sin grupo (MÍNIMO M3)"] + [g for g in GRUPOS_COMPRA if g != "MINIMO_M3"]
            grupo = st.selectbox("Grupo de compra", grupos)
            grupo_key = "MINIMO_M3" if "Sin grupo" in grupo else grupo
            plantas = load_plantas()
            planta_nombres = plantas["PLANTA"].tolist() if not plantas.empty else []
            planta = st.selectbox("Planta de producción", planta_nombres)

    # Datos del cliente
    with st.expander("🏢 Datos del cliente", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            cl_nombre = st.text_input("Nombre de la empresa")
            cl_razon = st.text_input("Razón social")
            cl_dir = st.text_input("Dirección")
            cl_cp = st.text_input("CP y Ciudad")
            cl_nif = st.text_input("NIF / CIF")
        with col2:
            cl_contacto = st.text_input("Persona de contacto")
            cl_tel = st.text_input("Teléfono contacto")
            cl_email = st.text_input("Email contacto")

    # Añadir líneas
    with st.expander("📦 Añadir productos", expanded=True):
        tipo = st.selectbox("Tipo de producto", TODOS_PRODUCTOS)
        calidades = get_calidades_producto(tipo)
        calidad = st.selectbox("Calidad", calidades) if calidades else ""
        if tipo in PRODUCTOS_ESTANDAR:
            _add_line_estandar(tipo, calidad, grupo_key, planta)
        else:
            _add_line_medida(tipo, calidad, grupo_key, planta)

    # Resumen
    if st.session_state.oferta_lineas:
        st.markdown("### 📝 Líneas de la oferta")
        df_lineas = pd.DataFrame(st.session_state.oferta_lineas)
        display_cols = ["TIPO_PRODUCTO", "CALIDAD", "DESCRIPCION", "CANTIDAD",
                        "PRECIO_M3", "M3_PIEZA", "PRECIO_UNITARIO", "TOTAL_LINEA"]
        display_cols = [c for c in display_cols if c in df_lineas.columns]
        st.dataframe(df_lineas[display_cols], use_container_width=True, hide_index=True)

        subtotal = sum(ln.get("TOTAL_LINEA", 0) for ln in st.session_state.oferta_lineas)
        st.metric("Subtotal", f"{subtotal:,.2f}€")

        col_del1, col_del2 = st.columns(2)
        with col_del1:
            if st.button("🗑️ Limpiar todas las líneas"):
                st.session_state.oferta_lineas = []
                st.rerun()
        with col_del2:
            idx_del = st.number_input("Eliminar línea nº", min_value=1,
                                      max_value=max(1, len(st.session_state.oferta_lineas)),
                                      value=1, step=1)
            if st.button("🗑️ Eliminar línea"):
                st.session_state.oferta_lineas.pop(int(idx_del) - 1)
                st.rerun()

    # Condiciones y totales
    if st.session_state.oferta_lineas:
        st.markdown("---")
        with st.expander("🚚 Condiciones y totales", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                forma_entrega = st.text_input("Forma de entrega", value="RECOGIDA / ENVÍO - Incoterm: DPP")
                plazo_entrega = st.text_input("Plazo de entrega", value="3 semanas laborales desde aceptación de pedido")
            with col2:
                cond_pago = st.text_input("Condiciones de pago", value="Transferencia bancaria")
                plazo_pago = st.text_input("Plazo de pago", value="60 días FF")

            subtotal = sum(ln.get("TOTAL_LINEA", 0) for ln in st.session_state.oferta_lineas)
            coste_transporte = st.number_input("Coste de transporte (€)", value=0.0, step=10.0, format="%.2f")
            descuento_pctg = st.number_input("Descuento (%)", value=0.0, step=0.5, format="%.1f", max_value=100.0)
            imp_plastico = st.number_input("Impuesto plástico (€)", value=0.0, step=0.01, format="%.2f")

            descuento_val = subtotal * descuento_pctg / 100
            total = subtotal + coste_transporte + imp_plastico - descuento_val

            c1, c2, c3 = st.columns(3)
            c1.metric("Subtotal", f"{subtotal:,.2f}€")
            c2.metric("Descuento", f"-{descuento_val:,.2f}€")
            c3.metric("Total s/IVA", f"{total:,.2f}€")
            observaciones = st.text_area("Observaciones", height=80)

        # Guardar y PDF
        st.markdown("---")
        if st.button("💾 Guardar oferta y generar PDF", use_container_width=True, type="primary"):
            if not cl_nombre:
                st.error("❌ Introduce al menos el nombre de la empresa")
                return

            numero = st.session_state.get("revision_numero") or next_oferta_number()
            revision = st.session_state.get("revision_rev", 1)

            oferta_dict = {
                "NUMERO_OFERTA": numero, "REVISION": revision,
                "COMERCIAL": st.session_state.user_nombre,
                "FECHA": fecha, "VALIDEZ": validez,
                "GRUPO_COMPRA": grupo_key, "PLANTA": planta,
                "CLIENTE_NOMBRE": cl_nombre, "CLIENTE_RAZON_SOCIAL": cl_razon,
                "CLIENTE_DIRECCION": cl_dir, "CLIENTE_CP_CIUDAD": cl_cp,
                "CLIENTE_NIF": cl_nif, "CLIENTE_CONTACTO": cl_contacto,
                "CLIENTE_TELEFONO": cl_tel, "CLIENTE_EMAIL": cl_email,
                "FORMA_ENTREGA": forma_entrega, "PLAZO_ENTREGA": plazo_entrega,
                "CONDICIONES_PAGO": cond_pago, "PLAZO_PAGO": plazo_pago,
                "OBSERVACIONES": observaciones, "SUBTOTAL": subtotal,
                "COSTE_TRANSPORTE": coste_transporte,
                "IMPUESTO_PLASTICO": imp_plastico,
                "DESCUENTO_PCTG": descuento_pctg, "TOTAL": total,
                "ESTADO": "Generada",
            }

            df_lineas = pd.DataFrame(st.session_state.oferta_lineas)
            save_oferta(oferta_dict, df_lineas)
            st.success(f"✅ Oferta **{numero}** (Rev. {revision}) guardada")

            config = _load_config_dict()
            pdf_bytes = generar_pdf_oferta(oferta_dict, df_lineas, config)
            st.download_button("⬇️ Descargar PDF", data=pdf_bytes,
                               file_name=f"{numero}_REV{revision}.pdf",
                               mime="application/pdf")
            st.session_state.oferta_lineas = []
            st.session_state.pop("revision_numero", None)
            st.session_state.pop("revision_rev", None)


def _add_line_estandar(tipo, calidad, grupo, planta):
    dims = get_dimensiones_disponibles(tipo)
    if not dims:
        st.warning(f"No hay dimensiones configuradas para {tipo}")
        return
    dimension = st.selectbox("Dimensión", dims, key=f"dim_{tipo}")
    espesores = get_espesores_disponibles(tipo, dimension)
    if not espesores:
        st.warning("No hay espesores disponibles")
        return
    espesor = st.selectbox("Espesor (mm)", [int(e) for e in espesores], key=f"esp_{tipo}")
    cantidad = st.number_input("Cantidad (piezas)", min_value=1, value=100, step=1, key=f"qty_{tipo}")

    if st.button("➕ Añadir línea", key=f"add_{tipo}"):
        result = calcular_linea_estandar(tipo, calidad, dimension, espesor, cantidad, grupo, planta)
        if "error" in result:
            st.error(result["error"])
        else:
            st.session_state.oferta_lineas.append(result)
            if result.get("AJUSTE_INFO"):
                st.info(result["AJUSTE_INFO"])
            st.rerun()


def _add_line_medida(tipo, calidad, grupo, planta):
    st.caption("Dimensiones de la pieza a cortar del bloque")
    col1, col2, col3 = st.columns(3)
    with col1:
        largo = st.number_input("Largo (mm)", min_value=10, value=1000, step=10, key=f"largo_{tipo}")
    with col2:
        ancho = st.number_input("Ancho (mm)", min_value=10, value=500, step=10, key=f"ancho_{tipo}")
    with col3:
        alto = st.number_input("Alto (mm)", min_value=10, value=100, step=10, key=f"alto_{tipo}")
    cantidad = st.number_input("Cantidad (piezas)", min_value=1, value=100, step=1, key=f"qty_{tipo}")

    if planta:
        from data import get_planta
        p = get_planta(planta)
        if p:
            st.caption(f"🏭 Bloque {planta}: {int(p['LARGO_MAX'])}×{int(p['ANCHO_MAX'])}×{int(p['GRUESO_MAX'])} mm — Mín: {p['MIN_M3']} m³")

    if st.button("➕ Añadir línea", key=f"add_{tipo}"):
        result = calcular_linea_medida(tipo, calidad, largo, ancho, alto, cantidad, grupo, planta)
        if "error" in result:
            st.error(result["error"])
        else:
            st.session_state.oferta_lineas.append(result)
            if result.get("BLOQUE_INFO"):
                st.info(f"🏭 {result['BLOQUE_INFO']}")
            if result.get("AJUSTE_INFO"):
                st.info(result["AJUSTE_INFO"])
            st.rerun()


def _init_revision(of_row):
    num = of_row["NUMERO_OFERTA"]
    max_rev = get_max_revision(num)
    st.session_state["revision_numero"] = num
    st.session_state["revision_rev"] = max_rev + 1
    oferta_id = int(of_row["ID"])
    lineas = load_oferta_lineas(oferta_id)
    st.session_state.oferta_lineas = lineas.to_dict("records") if not lineas.empty else []


def _load_config_dict():
    keys = ["empresa_nombre", "empresa_direccion", "empresa_cif",
            "empresa_registro", "impuesto_plastico_kg", "condiciones_legales"]
    return {k: get_config(k, "") for k in keys}

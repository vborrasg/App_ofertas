"""
views_comercial.py — Panel comercial v2 (KTM integrado).
Flujo: Seleccionar cliente → Configurar pieza → Calcular → Añadir líneas → Generar oferta.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from data import (
    load_tarifas, load_clientes, buscar_cliente, get_familias_por_materia,
    get_articulos_familia, get_coste_transporte, load_materias_primas,
    save_oferta, next_oferta_number, get_config, set_config, load_ofertas,
    PLANTAS, TIPOS_MATERIA_PRIMA
)
from calculator import calcular_linea
from pdf_generator import generar_pdf_oferta


def render_comercial():
    st.sidebar.markdown("### 🧑‍💼 Panel Comercial")
    menu = st.sidebar.radio("Menú", ["📝 Crear Oferta", "📋 Mis Ofertas"])
    if menu == "📝 Crear Oferta":
        _crear_oferta()
    else:
        _mis_ofertas()


# ── MIS OFERTAS ───────────────────────────────────────────────────────────────

def _mis_ofertas():
    st.markdown("## 📋 Mis Ofertas")
    comercial = st.session_state.get("user_email", "")
    df = load_ofertas(comercial)
    if df.empty:
        st.info("No tienes ofertas todavía.")
        return
    show_cols = ["NUMERO_OFERTA", "FECHA", "CLIENTE_NOMBRE", "TOTAL", "ESTADO"]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols].reset_index(drop=True), use_container_width=True, hide_index=True)


# ── CREAR OFERTA ──────────────────────────────────────────────────────────────

def _crear_oferta():
    st.markdown("## 📝 Nueva Oferta KTM")

    # Inicializar session state
    if "lineas_oferta" not in st.session_state:
        st.session_state.lineas_oferta = []

    # ── PASO 1: CLIENTE ───────────────────────────────────────────────────
    with st.expander("🏢 **Paso 1: Datos del cliente**", expanded=True):
        modo_cliente = st.radio(
            "Fuente de datos", ["🔍 Buscar en BD", "✏️ Escribir manualmente"],
            horizontal=True, key="modo_cliente"
        )

        if modo_cliente == "🔍 Buscar en BD":
            busqueda = st.text_input("Buscar empresa", placeholder="Escribe nombre de empresa...")
            cli_data = {}
            if busqueda and len(busqueda) >= 2:
                resultados = buscar_cliente(busqueda)
                if not resultados.empty:
                    opciones = resultados["EMPRESA"].tolist()
                    seleccion = st.selectbox("Seleccionar empresa", opciones)
                    if seleccion:
                        cli_row = resultados[resultados["EMPRESA"] == seleccion].iloc[0]
                        cli_data = cli_row.to_dict()
                        col1, col2 = st.columns(2)
                        with col1:
                            st.text_input("Empresa", value=cli_data.get("EMPRESA", ""), disabled=True, key="cli_emp")
                            st.text_input("CIF", value=cli_data.get("CIF", ""), disabled=True, key="cli_cif")
                            st.text_input("Contacto", value=f"{cli_data.get('CONTACTO_NOMBRE','')} {cli_data.get('CONTACTO_APELLIDO','')}", disabled=True, key="cli_nombre")
                        with col2:
                            st.text_input("Email", value=cli_data.get("EMAIL", ""), disabled=True, key="cli_email")
                            st.text_input("Teléfono", value=cli_data.get("TELEFONO", ""), disabled=True, key="cli_tel")
                            st.text_input("Mercado", value=cli_data.get("MERCADO", ""), disabled=True, key="cli_merc")
                else:
                    st.warning("No se encontraron resultados. Puedes escribir manualmente.")
            st.session_state["cliente_datos"] = cli_data
        else:
            col1, col2 = st.columns(2)
            with col1:
                cli_nombre = st.text_input("Nombre empresa *", key="man_emp")
                cli_cif = st.text_input("CIF", key="man_cif")
                cli_contacto = st.text_input("Persona de contacto", key="man_cont")
            with col2:
                cli_email = st.text_input("Email", key="man_email")
                cli_tel = st.text_input("Teléfono", key="man_tel")
                cli_dir = st.text_input("Dirección", key="man_dir")
            st.session_state["cliente_datos"] = {
                "EMPRESA": cli_nombre, "CIF": cli_cif,
                "CONTACTO_NOMBRE": cli_contacto, "EMAIL": cli_email,
                "TELEFONO": cli_tel, "DIRECCION": cli_dir
            }

    # ── PASO 2: CONFIGURAR PIEZA ─────────────────────────────────────────
    with st.expander("🔧 **Paso 2: Configurar pieza**", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            planta = st.selectbox("🏭 Planta", PLANTAS, key="sel_planta")
        with col2:
            materia = st.selectbox("🧪 Materia Prima", TIPOS_MATERIA_PRIMA,
                                   format_func=lambda x: x.replace("_", " "),
                                   key="sel_materia")
            
            # Mostrar el precio actual para información del comercial
            mps = load_materias_primas()
            if not mps.empty:
                val_mp = mps[mps["TIPO"] == materia]["PRECIO_BASE_KG"].iloc[0]
                st.caption(f"💰 Precio actual: **{val_mp:.2f} €/kg**")
        with col3:
            # Margen bruto con mínimo 15%
            margen = st.number_input("📈 Margen bruto (%)", min_value=15.0,
                                     value=15.0, step=1.0, key="sel_margen")

        # Familias disponibles para la materia prima seleccionada
        familias = get_familias_por_materia(materia)
        if not familias:
            st.warning("⚠️ No hay tarifas cargadas para esta materia prima. El admin debe subir las tarifas.")
            return

        col1, col2 = st.columns(2)
        with col1:
            familia = st.selectbox("📦 Familia de producto", familias, key="sel_familia")
        with col2:
            articulos = get_articulos_familia(familia) if familia else []
            articulo = st.selectbox("🏷️ Artículo / Calidad", articulos, key="sel_articulo") if articulos else None

        if articulo:
            # Obtener densidad del artículo (de tarifas)
            df_tar = load_tarifas()
            match_tar = df_tar[(df_tar["FAMILIA"] == familia) & (df_tar["ARTICULO"] == articulo)]
            densidad = float(match_tar.iloc[0]["DENSIDAD"]) if not match_tar.empty else 0

            st.markdown("#### 📐 Dimensiones de la pieza (mm)")
            col1, col2, col3 = st.columns(3)
            with col1:
                largo = st.number_input("Longitud", min_value=1, value=1000, step=10, key="dim_largo")
            with col2:
                ancho = st.number_input("Profundidad", min_value=1, value=600, step=10, key="dim_ancho")
            with col3:
                espesor = st.number_input("Espesor", min_value=1, value=50, step=5, key="dim_espesor")

            cantidad = st.number_input("🔢 Cantidad de piezas", min_value=1, value=100, step=1, key="cant_input")
            
            # ── Validar múltiplo logístico ──
            res_preview = calcular_linea(familia, articulo, planta, densidad, largo, ancho, espesor, cantidad, margen, materia)
            cant_ajustada = res_preview.get("CANTIDAD", cantidad)
            
            if "error" not in res_preview and cant_ajustada != cantidad:
                st.warning(f"💡 Embalaje: La cantidad mínima sugerida es **{cant_ajustada}** piezas (múltiplo logístico).")
                st.button(
                    f"✅ Ajustar a {cant_ajustada} piezas",
                    on_click=lambda v=cant_ajustada: st.session_state.update(
                        {"cant_input": v, "ultimo_calculo": None}
                    ),
                )

            # ── CALCULAR ─────────────────────────────────────────────────
            if st.button("🧮 Calcular", type="primary", key="btn_calc"):
                resultado = calcular_linea(
                    familia=familia, articulo=articulo, planta_nombre=planta,
                    densidad=densidad, largo_pieza=largo, ancho_pieza=ancho,
                    espesor_pieza=espesor, cantidad_pedida=cantidad,
                    margen_pctg=margen, materia_prima=materia
                )
                if "error" in resultado:
                    st.error(resultado["error"])
                else:
                    st.session_state["ultimo_calculo"] = resultado

            # Mostrar resultado
            if st.session_state.get("ultimo_calculo"):
                res = st.session_state["ultimo_calculo"]
                st.markdown("---")
                st.markdown("### 📊 Resultado del cálculo")
                st.info(res.get("BLOQUE_INFO", ""))

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Piezas/Bloque", res["PZAS_BLOQUE"])
                    st.metric("m³ pieza", f"{res['M3_PIEZA']:.6f}")
                with col2:
                    st.metric("€/m³ CON Scrap", f"{res['EUR_M3_CON_SCRAP']:.2f}")
                    st.metric("€/pza CON Scrap", f"{res['PRECIO_PIEZA_CON_SCRAP']:.4f}")
                with col3:
                    st.metric("€/m³ SIN Scrap", f"{res['EUR_M3_SIN_SCRAP']:.2f}")
                    st.metric("€/pza SIN Scrap", f"{res['PRECIO_PIEZA_SIN_SCRAP']:.4f}")
                with col4:
                    st.metric("Scrap", f"{res['SCRAP_PCTG']:.1f}%")
                    st.metric("Margen bruto", f"{res['MARGEN_PCTG']:.1f}%")

                # Solo mostrar ajuste si realmente se ajustó
                ajuste_info = res.get("AJUSTE_INFO", "")
                if ajuste_info:
                    st.caption(ajuste_info)
                    
                st.metric("💰 Total línea (con scrap)", f"{res['TOTAL_LINEA']:,.2f} €")

                if st.button("➕ Añadir línea a la oferta", key="btn_add_line"):
                    st.session_state.lineas_oferta.append(res)
                    st.session_state["ultimo_calculo"] = None
                    st.success("✅ Línea añadida")
                    st.rerun()

    # ── PASO 3: RESUMEN + GENERAR OFERTA ──────────────────────────────────
    lineas = st.session_state.get("lineas_oferta", [])
    if lineas:
        with st.expander(f"📄 **Paso 3: Resumen de la oferta ({len(lineas)} líneas)**", expanded=True):
            df_lineas = pd.DataFrame(lineas)
            show_cols = ["CALIDAD", "DIMENSION", "PLANTA", "CANTIDAD", "MATERIA_PRIMA",
                         "PRECIO_PIEZA_CON_SCRAP", "PRECIO_PIEZA_SIN_SCRAP", "TOTAL_LINEA"]
            show_cols = [c for c in show_cols if c in df_lineas.columns]
            st.dataframe(df_lineas[show_cols], use_container_width=True, hide_index=True)

            subtotal = sum(l["TOTAL_LINEA"] for l in lineas)
            m3_total = sum(l["M3_PIEZA"] * l["CANTIDAD"] for l in lineas)

            # Eliminar línea
            if len(lineas) > 1:
                idx_del = st.number_input("Eliminar línea nº", min_value=1, max_value=len(lineas), value=1, key="del_line")
                if st.button("🗑️ Eliminar línea", key="btn_del_line"):
                    st.session_state.lineas_oferta.pop(int(idx_del) - 1)
                    st.rerun()

            st.markdown("---")
            st.markdown("### 🚚 Portes y ajustes")
            col1, col2 = st.columns(2)
            with col1:
                # Transporte: comercial introduce € absolutos o se calcula por defecto
                planta_ref = lineas[0].get("PLANTA", "Valencia") if lineas else "Valencia"
                transp_default_m3 = lineas[0].get("TRANSPORTE_M3_PLANTA", 0) if lineas else 0
                minimo_transp = lineas[0].get("MINIMO_TRANSPORTE", 0) if lineas else 0
                porte_default = round(transp_default_m3 * m3_total, 2)
                st.caption(f"💡 Porte por defecto: {porte_default:.2f}€ ({transp_default_m3:.2f} €/m³ × {m3_total:.4f} m³)")
                if minimo_transp > 0:
                    st.caption(f"🚚 Mínimo de transporte {planta_ref}: **{minimo_transp:.0f}€**")
                porte_manual = st.number_input(
                    "Porte (€) — dejar vacío para usar el por defecto",
                    min_value=0.0, value=0.0, step=10.0,
                    format="%.2f", key="porte_manual",
                    help="Si NO introduces un valor (o dejas 0), se aplica el porte por defecto de la planta."
                )
                # Si el comercial no pone nada (0), se usa el default
                porte_final = porte_manual if porte_manual > 0 else porte_default
                # Aplicar mínimo de transporte de la planta
                if minimo_transp > 0 and porte_final < minimo_transp:
                    st.warning(f"⚠️ Porte ajustado al mínimo de {planta_ref}: **{minimo_transp:.0f}€** (era {porte_final:.2f}€)")
                    porte_final = minimo_transp

            with col2:
                descuento = st.number_input("Descuento (%)", min_value=0.0, value=0.0,
                                            step=0.5, format="%.1f", key="descuento")
                imp_plast_kg = float(get_config("impuesto_plastico_kg", "0.45") or 0.45)
                aplicar_imp = st.checkbox("Aplicar impuesto al plástico", value=False, key="chk_imp")

            imp_plastico_total = 0
            if aplicar_imp:
                # Calcular kg estimados
                for l in lineas:
                    densidad = l.get("DENSIDAD", 15)
                    m3_linea = l["M3_PIEZA"] * l["CANTIDAD"]
                    imp_plastico_total += m3_linea * densidad * imp_plast_kg

            descuento_valor = subtotal * descuento / 100
            total_final = subtotal + porte_final + imp_plastico_total - descuento_valor

            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("Subtotal", f"{subtotal:,.2f}€")
            with col2: st.metric("Portes", f"{porte_final:,.2f}€")
            with col3: st.metric("Imp. plástico", f"{imp_plastico_total:,.2f}€")
            with col4: st.metric("**TOTAL**", f"{total_final:,.2f}€")

            if descuento > 0:
                st.caption(f"Descuento aplicado: -{descuento_valor:,.2f}€ ({descuento}%)")

            st.markdown("---")
            st.markdown("### 📝 Observaciones")
            observaciones = st.text_area("Notas para la oferta", key="obs_oferta")

            # ── BLOQUE DE GENERACIÓN DE OFERTA ──
            st.markdown("---")
            st.subheader("📝 Finalizar Oferta")
            
            # Calcular total global
            total_oferta = subtotal
            total_con_portes = total_final
            
            col_t1, col_t2 = st.columns(2)
            col_t1.metric("Total Material (Ex Works)", f"{total_oferta:,.2f} €")
            col_t2.metric("Total con Portes/Impuestos", f"{total_con_portes:,.2f} €")
            
            # Validación pedido mínimo 500€
            bloqueo_pdf = False
            if total_con_portes < 500:
                st.warning("⚠️ **AVISO DE PEDIDO MÍNIMO**: Esta oferta es inferior a **500€** (sin IVA).")
                verificado_minimo = st.checkbox("✅ He verificado y acepto que el importe es inferior a 500€")
                if not verificado_minimo:
                    bloqueo_pdf = True
                    st.info("Debes marcar el check de verificación para poder generar el PDF.")

            # ── GENERAR OFERTA ────────────────────────────────────────────
            if st.button("📄 Generar PDF de Oferta", type="primary", disabled=bloqueo_pdf, use_container_width=True):
                cli = st.session_state.get("cliente_datos", {})
                if not cli.get("EMPRESA"):
                    st.error("❌ Introduce los datos del cliente primero")
                else:
                    from datetime import datetime
                    from data import save_oferta, next_oferta_number
                    
                    numero = next_oferta_number()
                    comercial = st.session_state.get("user_name", "Comercial")
                    email_com = st.session_state.get("user_email", "")

                    oferta_dict = {
                        "NUMERO_OFERTA": numero,
                        "REVISION": 0,
                        "FECHA": datetime.now().strftime("%Y-%m-%d"),
                        "COMERCIAL": email_com,
                        "COMERCIAL_NOMBRE": comercial,
                        "CLIENTE_NOMBRE": cli.get("EMPRESA", ""),
                        "CLIENTE_CIF": cli.get("CIF", ""),
                        "CLIENTE_CONTACTO": cli.get("CONTACTO_NOMBRE", ""),
                        "CLIENTE_EMAIL": cli.get("EMAIL", ""),
                        "CLIENTE_TELEFONO": cli.get("TELEFONO", ""),
                        "CLIENTE_DIRECCION": cli.get("DIRECCION", ""),
                        "SUBTOTAL": round(subtotal, 2),
                        "PORTES": round(porte_final, 2),
                        "IMPUESTO_PLASTICO_TOTAL": round(imp_plastico_total, 2),
                        "DESCUENTO_PCTG": 0, # Por ahora 0
                        "DESCUENTO_VALOR": 0,
                        "TOTAL": round(total_final, 2),
                        "OBSERVACIONES": observaciones,
                        "ESTADO": "Borrador",
                    }

                    df_lineas_save = pd.DataFrame(lineas)
                    try:
                        oferta_id = save_oferta(oferta_dict, df_lineas_save)
                        st.success(f"✅ Oferta {numero} guardada correctamente")
                        
                        # Generar PDF
                        from pdf_generator import generar_pdf_oferta
                        cliente_pdf = {
                            "nombre": cli.get("EMPRESA", ""),
                            "direccion": cli.get("DIRECCION", ""),
                            "poblacion": cli.get("POBLACION", ""),
                            "cp": cli.get("CP", "")
                        }
                        pdf_bytes = generar_pdf_oferta(cliente_pdf, lineas, portes_total=porte_final)
                        
                        st.download_button(
                            label="⬇️ Descargar PDF de Oferta",
                            data=pdf_bytes,
                            file_name=f"Oferta_{numero}_{cli.get('EMPRESA','')}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.warning(f"⚠️ PDF no generado: {e}")

                    # Limpiar
                    st.session_state.lineas_oferta = []

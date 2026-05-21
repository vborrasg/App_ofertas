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
    load_oferta_lineas, PLANTAS, TIPOS_MATERIA_PRIMA,
    update_oferta_estado, send_validation_email,
    get_productos_grupo, get_calidades_producto_grupo
)
from calculator import calcular_linea
from pdf_generator import generar_pdf_oferta


def _infer_density(quality):
    """Infiere la densidad aproximada a partir del nombre de la calidad en grupos de compra."""
    q = quality.upper().strip()
    if "250" in q:
        return 35.0
    elif "200" in q:
        return 30.0
    elif "150" in q:
        return 25.0
    elif "100" in q:
        return 20.0
    elif "60" in q:
        return 15.0
    elif "30" in q:
        return 12.0
    elif "BATIMENT" in q:
        return 10.0
    elif "TH 39" in q or "TH39" in q:
        return 15.0
    elif "TH 37" in q or "TH37" in q or "ETIX 37" in q:
        return 15.0
    elif "TH 35" in q or "TH35" in q:
        return 20.0
    elif "TH 34" in q or "TH34" in q:
        return 30.0
    elif "S3" in q or "EPS S" in q:
        return 10.0
    elif "ETIX 32" in q:
        return 15.0
    return 15.0


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

    show_cols = ["NUMERO_OFERTA", "FECHA", "CLIENTE_NOMBRE", "TIPO_PRECIO", "TOTAL", "ESTADO"]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols].reset_index(drop=True), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 🔎 Ver / Reimprimir oferta")
    ids = df["NUMERO_OFERTA"].tolist()
    sel_oferta = st.selectbox("Seleccionar oferta", ids, key="sel_mis_oferta")
    if sel_oferta:
        of_row = df[df["NUMERO_OFERTA"] == sel_oferta].iloc[0]
        oferta_id = int(of_row["ID"])
        oferta_dict = of_row.to_dict()
        lineas_df = load_oferta_lineas(oferta_id)

        # Detalle de la oferta
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Cliente", oferta_dict.get("CLIENTE_NOMBRE", ""))
        col2.metric("Subtotal", f"{float(oferta_dict.get('SUBTOTAL', 0)):,.2f}€")
        col3.metric("Portes", f"{float(oferta_dict.get('PORTES', 0)):,.2f}€")
        col4.metric("Total", f"{float(oferta_dict.get('TOTAL', 0)):,.2f}€")

        # Líneas
        if not lineas_df.empty:
            line_cols = ["TIPO_PRODUCTO", "CALIDAD", "DESCRIPCION", "PLANTA",
                         "CANTIDAD", "PRECIO_PIEZA_CON_SCRAP", "TOTAL_LINEA"]
            line_cols = [c for c in line_cols if c in lineas_df.columns]
            st.dataframe(lineas_df[line_cols].reset_index(drop=True),
                         use_container_width=True, hide_index=True)

        # Estado de la oferta
        estado = str(oferta_dict.get("ESTADO", "Borrador"))
        tipo_precio = str(oferta_dict.get("TIPO_PRECIO", "CON Scrap"))
        
        if estado == "Pendiente Validación":
            st.warning(f"⏳ Esta oferta está **pendiente de validación** (precio {tipo_precio}). No se puede descargar el PDF hasta que sea aprobada.")
        elif estado == "Rechazada":
            st.error("❌ Esta oferta ha sido **rechazada**. Contacta con tu responsable.")
        else:
            # Botón reimprimir PDF (solo si validada o con scrap)
            if st.button("📄 Descargar PDF", key="btn_reprint", type="primary", use_container_width=True):
                try:
                    from pdf_generator import generar_pdf_oferta
                    lineas_list = lineas_df.to_dict("records") if not lineas_df.empty else []
                    pdf_bytes = generar_pdf_oferta(oferta_dict, lineas_list)
                    st.download_button(
                        label="⬇️ Descargar PDF",
                        data=pdf_bytes,
                        file_name=f"Oferta_{sel_oferta}_{oferta_dict.get('CLIENTE_NOMBRE','')}.pdf",
                        mime="application/pdf",
                        key="dl_reprint"
                    )
                except Exception as e:
                    st.error(f"❌ Error al generar PDF: {e}")


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
                        st.caption("✏️ Puedes editar los campos si falta información.")
                        col1, col2 = st.columns(2)
                        with col1:
                            cli_data["EMPRESA"] = st.text_input("Empresa", value=cli_data.get("EMPRESA", ""), key="cli_emp")
                            cli_data["CIF"] = st.text_input("CIF", value=cli_data.get("CIF", ""), key="cli_cif")
                            cli_data["CONTACTO_NOMBRE"] = st.text_input("Contacto", value=f"{cli_data.get('CONTACTO_NOMBRE','')} {cli_data.get('CONTACTO_APELLIDO','')}".strip(), key="cli_nombre")
                            cli_data["DIRECCION"] = st.text_input("Dirección", value=cli_data.get("DIRECCION", ""), key="cli_dir")
                        with col2:
                            cli_data["EMAIL"] = st.text_input("Email", value=cli_data.get("EMAIL", ""), key="cli_email")
                            cli_data["TELEFONO"] = st.text_input("Teléfono", value=cli_data.get("TELEFONO", cli_data.get("MOVIL", "")), key="cli_tel")
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

        st.markdown("---")
        st.markdown("### 🏷️ Grupo de Compra")
        grupos_list = [
            "Ninguno",
            "BIG MAT",
            "ESTRAT. BIG MAT",
            "EMCCAT",
            "GRUP GAMMA",
            "IDAPLAC",
            "DAVSA",
            "GRUP IBRICKS"
        ]
        if "grupo_compra" not in st.session_state:
            st.session_state["grupo_compra"] = "Ninguno"
        
        try:
            grupo_compra_index = grupos_list.index(st.session_state["grupo_compra"])
        except ValueError:
            grupo_compra_index = 0
            
        grupo_compra = st.selectbox(
            "Seleccionar Grupo de Compra global para la oferta",
            grupos_list,
            index=grupo_compra_index,
            key="sel_grupo_compra_global",
            help="Al seleccionar un grupo, todos los artículos de la oferta se tasarán según ese grupo y no se pueden mezclar líneas normales con líneas de grupo."
        )
        if grupo_compra != st.session_state["grupo_compra"]:
            st.session_state["grupo_compra"] = grupo_compra
            if st.session_state.get("lineas_oferta"):
                st.session_state.lineas_oferta = []
                st.info("🔄 Se ha cambiado el grupo de compra. Las líneas anteriores se han eliminado para evitar ofertas mixtas.")

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

        # Si hay grupo de compra activo, cargamos desde el Excel de grupos de compra
        grupo_compra = st.session_state.get("grupo_compra", "Ninguno")
        
        if grupo_compra != "Ninguno":
            familias = get_productos_grupo(grupo_compra)
            if not familias:
                st.warning(f"⚠️ No hay productos con tarifas definidas para el grupo de compra '{grupo_compra}'.")
                return
            st.info(f"🏷️ **Grupo de Compra Activo: {grupo_compra}**. Se aplicará la tarifa de grupo directamente (Opción A - Tarifa Plana Sin Scrap).")
        else:
            familias = get_familias_por_materia(materia)
            if not familias:
                st.warning("⚠️ No hay tarifas cargadas para esta materia prima. El admin debe subir las tarifas.")
                return

        col1, col2 = st.columns(2)
        with col1:
            familia = st.selectbox("📦 Familia de producto", familias, key="sel_familia")
        with col2:
            if grupo_compra != "Ninguno":
                articulos = get_calidades_producto_grupo(grupo_compra, familia) if familia else []
            else:
                articulos = get_articulos_familia(familia) if familia else []
            articulo = st.selectbox("🏷️ Artículo / Calidad", articulos, key="sel_articulo") if articulos else None

        if articulo:
            if grupo_compra != "Ninguno":
                densidad = _infer_density(articulo)
            else:
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

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                cantidad = st.number_input("🔢 Cantidad de piezas", min_value=1, value=100, step=1, key="cant_input")
            with col_c2:
                descuento_linea = st.number_input(
                    "💸 Descuento absoluto (€/m³)",
                    min_value=0.00,
                    value=0.00,
                    step=0.50,
                    format="%.2f",
                    key="dto_linea_m3",
                    help="Descuento que se restará directamente del precio de la línea en €/m³."
                )
            
            # ── Validar múltiplo logístico ──
            res_preview = calcular_linea(
                familia=familia, articulo=articulo, planta_nombre=planta,
                densidad=densidad, largo_pieza=largo, ancho_pieza=ancho,
                espesor_pieza=espesor, cantidad_pedida=cantidad,
                margen_pctg=margen, materia_prima=materia,
                grupo_compra=grupo_compra, descuento_absoluto_m3=descuento_linea
            )
            cant_ajustada = res_preview.get("CANTIDAD", cantidad)
            
            if "error" not in res_preview and cant_ajustada != cantidad:
                st.info(f"📦 **Ajuste logístico automático:** {cantidad} → **{cant_ajustada}** piezas (múltiplo de {res_preview.get('PZAS_PAQUETE', '?')} pzas/paquete).")

            # ── CALCULAR (siempre con cantidad ajustada) ──────────────────
            if st.button("🧮 Calcular", type="primary", key="btn_calc"):
                resultado = calcular_linea(
                    familia=familia, articulo=articulo, planta_nombre=planta,
                    densidad=densidad, largo_pieza=largo, ancho_pieza=ancho,
                    espesor_pieza=espesor, cantidad_pedida=cant_ajustada,
                    margen_pctg=margen, materia_prima=materia,
                    grupo_compra=grupo_compra, descuento_absoluto_m3=descuento_linea
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
                    st.metric("TARIFA Catálogo", f"{res.get('TARIFA_FINAL', 0):.2f} €/m³")
                    st.metric("Piezas/Bloque", res["PZAS_BLOQUE"])
                with col2:
                    st.metric("€/m³ CON Scrap", f"{res['EUR_M3_CON_SCRAP']:.2f}")
                    st.metric("€/pza CON Scrap", f"{res['PRECIO_PIEZA_CON_SCRAP']:.4f}")
                with col3:
                    st.metric("€/m³ SIN Scrap", f"{res['EUR_M3_SIN_SCRAP']:.2f}")
                    st.metric("€/pza SIN Scrap", f"{res['PRECIO_PIEZA_SIN_SCRAP']:.4f}")
                with col4:
                    st.metric("Scrap", f"{res['SCRAP_PCTG']:.2f}%")
                    st.metric("Margen bruto", f"{res['MARGEN_PCTG']:.1f}%")

                ajuste_info = res.get("AJUSTE_INFO", "")
                if ajuste_info:
                    st.caption(ajuste_info)
                    
                with st.expander("🔍 Ver desglose de cálculo (Debug)"):
                    st.markdown(f"""
                    - **Tarifa Base Planta:** {res.get('TARIFA_BASE_PLANTA', 0):.4f} €
                    - **Precio MP Original (Blanco):** {res.get('PRECIO_MP_ORIGINAL', 0):.4f} €/kg
                    - **Precio MP Actual:** {res.get('PRECIO_MP_ACTUAL', 0):.4f} €/kg
                    - **Incremento MP:** {res.get('INCREMENTO_MP', 0):.4f} €/m³
                    - **Precio Ex Works (Sin Scrap):** {res.get('PRECIO_EXWORKS_M3', 0):.4f} €/m³
                    """)
                    
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
            # ── Selector CON/SIN Scrap ──
            grupo_compra = st.session_state.get("grupo_compra", "Ninguno")
            if grupo_compra != "Ninguno":
                st.info(f"🏷️ **Grupo de Compra: {grupo_compra}**. Se aplica precio **SIN SCRAP** (Tarifa Plana) obligatoriamente.")
                es_sin_scrap = True
                tipo_precio = "PRECIO SIN Scrap"
            else:
                tipo_precio = st.radio(
                    "💰 Tipo de precio",
                    ["PRECIO CON Scrap", "PRECIO SIN Scrap"],
                    horizontal=True, key="sel_tipo_precio",
                    help="SIN Scrap requiere validación de dirección antes de poder generar el PDF."
                )
                es_sin_scrap = tipo_precio == "PRECIO SIN Scrap"
                
                if es_sin_scrap:
                    st.warning("⚠️ Has seleccionado **PRECIO SIN Scrap**. Esta oferta requerirá validación de dirección antes de poder descargar el PDF.")

            df_lineas = pd.DataFrame(lineas)
            # Recalcular totales según tipo de precio
            if es_sin_scrap:
                for i, l in enumerate(lineas):
                    lineas[i]["_PRECIO_DISPLAY"] = l.get("PRECIO_PIEZA_SIN_SCRAP", l.get("PRECIO_PIEZA_CON_SCRAP", 0))
                    lineas[i]["_TOTAL_DISPLAY"] = lineas[i]["_PRECIO_DISPLAY"] * l.get("CANTIDAD", 0)
                df_lineas = pd.DataFrame(lineas)
                show_cols = ["CALIDAD", "DIMENSION", "PLANTA", "CANTIDAD", "MATERIA_PRIMA",
                             "PRECIO_PIEZA_SIN_SCRAP", "_TOTAL_DISPLAY"]
            else:
                for i, l in enumerate(lineas):
                    lineas[i]["_PRECIO_DISPLAY"] = l.get("PRECIO_PIEZA_CON_SCRAP", 0)
                    lineas[i]["_TOTAL_DISPLAY"] = l.get("TOTAL_LINEA", 0)
                df_lineas = pd.DataFrame(lineas)
                show_cols = ["CALIDAD", "DIMENSION", "PLANTA", "CANTIDAD", "MATERIA_PRIMA",
                             "PRECIO_PIEZA_CON_SCRAP", "TOTAL_LINEA"]
            show_cols = [c for c in show_cols if c in df_lineas.columns]
            st.dataframe(df_lineas[show_cols], use_container_width=True, hide_index=True)

            total_descuento = sum(l.get("DESCUENTO_ABSOLUTO_M3", 0.0) * l["M3_PIEZA"] * l["CANTIDAD"] for l in lineas)
            subtotal_neto = sum(l["_TOTAL_DISPLAY"] for l in lineas)
            subtotal_bruto = subtotal_neto + total_descuento
            subtotal = subtotal_neto
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
                st.write("**Descuento aplicado**")
                equiv_pctg = (total_descuento / subtotal_bruto * 100) if subtotal_bruto > 0 else 0.0
                st.info(f"💸 Dto. acumulado por líneas: **{total_descuento:,.2f} €** ({equiv_pctg:.1f}%)")
                imp_plast_kg = float(get_config("impuesto_plastico_kg", "0.45") or 0.45)
                aplicar_imp = st.checkbox("Aplicar impuesto al plástico", value=False, key="chk_imp")

            imp_plastico_total = 0
            if aplicar_imp:
                # Calcular kg estimados
                for l in lineas:
                    densidad = l.get("DENSIDAD", 15)
                    m3_linea = l["M3_PIEZA"] * l["CANTIDAD"]
                    imp_plastico_total += m3_linea * densidad * imp_plast_kg

            descuento_valor = total_descuento
            descuento = equiv_pctg
            subtotal_con_dto = subtotal_neto
            total_final = subtotal_neto + porte_final + imp_plastico_total

            st.markdown("---")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: st.metric("Subtotal bruto", f"{subtotal_bruto:,.2f}€")
            with col2:
                if total_descuento > 0:
                    st.metric("Dto. total", f"-{total_descuento:,.2f}€", delta=f"-{equiv_pctg:.1f}%")
                else:
                    st.metric("Dto. total", "0,00€")
            with col3: st.metric("Portes", f"{porte_final:,.2f}€")
            with col4: st.metric("Imp. plástico", f"{imp_plastico_total:,.2f}€")
            with col5: st.metric("**TOTAL**", f"{total_final:,.2f}€")

            st.markdown("---")
            st.markdown("### 📝 Condiciones y observaciones")
            
            proyecto_obra = ""
            if total_descuento > 0:
                st.markdown("#### 🏷️ Proyecto / Obra Especial")
                proyecto_obra = st.text_input(
                    "Nombre del Proyecto u Obra Especial *",
                    placeholder="Introduce el nombre del proyecto u obra (obligatorio por tener descuento aplicado)",
                    key="proyecto_obra_input"
                )
                if not proyecto_obra.strip():
                    st.warning("⚠️ **ATENCIÓN**: El campo 'Nombre del Proyecto u Obra Especial' es obligatorio porque esta oferta incluye descuentos.")
                st.markdown("---")

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                fecha_validez = st.date_input("📅 Fecha de validez de la oferta", key="fecha_validez")
                cond_pago = st.text_input("💳 Condiciones de pago", placeholder="Ej: 30 días fecha factura", key="cond_pago")
            with col_c2:
                cond_transporte = st.text_input("🚚 Condiciones de transporte", placeholder="Ej: Portes pagados, destino...", key="cond_transporte")
                observaciones = st.text_area("📋 Observaciones", key="obs_oferta")

            # ── BLOQUE DE GENERACIÓN DE OFERTA ──
            st.markdown("---")
            st.subheader("📝 Finalizar Oferta")
            
            # Calcular total global
            total_oferta = subtotal
            total_con_portes = total_final
            
            col_t1, col_t2 = st.columns(2)
            col_t1.metric("Total Material (Ex Works)", f"{total_oferta:,.2f} €")
            col_t2.metric("Total con Portes/Impuestos", f"{total_con_portes:,.2f} €")
            
            # Validación de bloqueo de PDF y de estado
            bloqueo_pdf = False
            requiere_validacion = es_sin_scrap or (total_con_portes < 500) or (total_descuento > 0)
            
            if total_con_portes < 500:
                st.warning("⚠️ **AVISO DE PEDIDO MÍNIMO**: El total de esta oferta es inferior a **500€** (con portes y sin IVA) y requiere validación de dirección.")
                
            if total_descuento > 0:
                if not proyecto_obra.strip():
                    bloqueo_pdf = True
                    st.error("❌ El nombre de Proyecto/Obra Especial es obligatorio cuando hay descuentos.")
                else:
                    st.info("ℹ️ Esta oferta incluye descuentos y requiere validación de dirección.")
                    
            if es_sin_scrap and grupo_compra == "Ninguno":
                st.info("ℹ️ Has seleccionado precio SIN Scrap, por lo que requiere validación de dirección.")

            # ── GENERAR OFERTA ────────────────────────────────────────────
            if st.button("📄 Generar PDF de Oferta", type="primary", disabled=bloqueo_pdf, use_container_width=True):
                    # Leer datos del cliente desde session state (widgets)
                    cli = st.session_state.get("cliente_datos", {})
                    # Sobreescribir con valores actuales de los widgets (por si el expander se colapsó)
                    if st.session_state.get("modo_cliente", "").startswith("✏️"):
                        cli = {
                            "EMPRESA": st.session_state.get("man_emp", cli.get("EMPRESA", "")),
                            "CIF": st.session_state.get("man_cif", cli.get("CIF", "")),
                            "CONTACTO_NOMBRE": st.session_state.get("man_cont", cli.get("CONTACTO_NOMBRE", "")),
                            "EMAIL": st.session_state.get("man_email", cli.get("EMAIL", "")),
                            "TELEFONO": st.session_state.get("man_tel", cli.get("TELEFONO", "")),
                            "DIRECCION": st.session_state.get("man_dir", cli.get("DIRECCION", "")),
                        }
                    elif st.session_state.get("modo_cliente", "").startswith("🔍"):
                        cli["EMPRESA"] = st.session_state.get("cli_emp", cli.get("EMPRESA", ""))
                        cli["CIF"] = st.session_state.get("cli_cif", cli.get("CIF", ""))
                        cli["CONTACTO_NOMBRE"] = st.session_state.get("cli_nombre", cli.get("CONTACTO_NOMBRE", ""))
                        cli["EMAIL"] = st.session_state.get("cli_email", cli.get("EMAIL", ""))
                        cli["TELEFONO"] = st.session_state.get("cli_tel", cli.get("TELEFONO", ""))
                        cli["DIRECCION"] = st.session_state.get("cli_dir", cli.get("DIRECCION", ""))

                    if not cli.get("EMPRESA"):
                        st.error("❌ Introduce los datos del cliente primero")
                    else:
                        from datetime import datetime
                        from data import save_oferta, next_oferta_number
                        
                        numero = next_oferta_number()
                        comercial = st.session_state.get("user_name", "Comercial")
                        email_com = st.session_state.get("user_email", "")

                        estado_oferta = "Pendiente Validación" if requiere_validacion else "Borrador"
                        
                        # Guardar proyecto/obra en observaciones también por si acaso
                        obs_final = observaciones
                        if total_descuento > 0 and proyecto_obra.strip():
                            obs_final = f"[Proyecto/Obra: {proyecto_obra.strip()}]\n{obs_final}"
                        
                        oferta_dict = {
                            "NUMERO_OFERTA": numero,
                            "REVISION": 0,
                            "FECHA": datetime.now().strftime("%Y-%m-%d"),
                            "FECHA_VALIDEZ": fecha_validez.strftime("%Y-%m-%d"),
                            "COMERCIAL": email_com,
                            "COMERCIAL_NOMBRE": comercial,
                            "CLIENTE_NOMBRE": cli.get("EMPRESA", ""),
                            "CLIENTE_CIF": cli.get("CIF", ""),
                            "CLIENTE_CONTACTO": cli.get("CONTACTO_NOMBRE", ""),
                            "CLIENTE_EMAIL": cli.get("EMAIL", ""),
                            "CLIENTE_TELEFONO": cli.get("TELEFONO", ""),
                            "CLIENTE_DIRECCION": cli.get("DIRECCION", ""),
                            "SUBTOTAL": round(subtotal_bruto, 2),
                            "PORTES": round(porte_final, 2),
                            "IMPUESTO_PLASTICO_TOTAL": round(imp_plastico_total, 2),
                            "DESCUENTO_PCTG": round(descuento, 1),
                            "DESCUENTO_VALOR": round(descuento_valor, 2),
                            "TOTAL": round(total_final, 2),
                            "CONDICIONES_PAGO": cond_pago,
                            "CONDICIONES_TRANSPORTE": cond_transporte,
                            "OBSERVACIONES": obs_final,
                            "TIPO_PRECIO": tipo_precio,
                            "ESTADO": estado_oferta,
                            "GRUPO_COMPRA": grupo_compra,
                            "PROYECTO_OBRA": proyecto_obra.strip() if total_descuento > 0 else "",
                        }

                        # Si es SIN Scrap, actualizar TODOS los precios de cada línea
                        if es_sin_scrap:
                            for i, l in enumerate(lineas):
                                precio_sin = l.get("PRECIO_PIEZA_SIN_SCRAP", l.get("PRECIO_PIEZA_CON_SCRAP", 0))
                                lineas[i]["PRECIO_PIEZA_CON_SCRAP"] = precio_sin
                                lineas[i]["PRECIO_UNITARIO"] = precio_sin
                                lineas[i]["TOTAL_LINEA"] = precio_sin * l.get("CANTIDAD", 0)
                                # Actualizar también €/m³
                                lineas[i]["EUR_M3_CON_SCRAP"] = l.get("EUR_M3_SIN_SCRAP", l.get("EUR_M3_CON_SCRAP", 0))
                                lineas[i]["PRECIO_M3"] = l.get("EUR_M3_SIN_SCRAP", l.get("PRECIO_M3", 0))

                        df_lineas_save = pd.DataFrame(lineas)
                        try:
                            oferta_id = save_oferta(oferta_dict, df_lineas_save)
                            
                            # Si requiere validación, enviar email de validación
                            if requiere_validacion:
                                from data import send_validation_email
                                email_ok = send_validation_email(oferta_dict)
                                if email_ok:
                                    st.info("📧 Se ha enviado un email de validación a dirección.")
                                else:
                                    st.warning("⚠️ No se pudo enviar el email de validación. La oferta queda pendiente igualmente.")
                            st.success(f"✅ Oferta {numero} guardada correctamente")
                            
                            if requiere_validacion:
                                st.warning("⏳ Esta oferta está **pendiente de validación**. Podrás descargar el PDF desde 'Mis Ofertas' una vez sea aprobada por un administrador.")
                            else:
                                # Generar PDF directamente (no requiere validación)
                                from pdf_generator import generar_pdf_oferta
                                pdf_bytes = generar_pdf_oferta(oferta_dict, lineas)
                                
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

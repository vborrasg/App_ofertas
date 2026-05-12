"""
pdf_generator.py — Generación del PDF de oferta con reportlab.
Formato ODP de Knauf Industries + logo + scrap/margen.
"""
import io
import base64
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from data import get_config


def generar_pdf_oferta(oferta, lineas):
    """Genera el PDF de oferta. Retorna bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=15*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    elements = []

    # Colores
    AZUL = HexColor("#1a5276")
    AZUL_CLARO = HexColor("#eaf2f8")
    GRIS_BORDE = HexColor("#b0c4de")
    FONDO_HDR = HexColor("#2c3e50")

    # Estilos
    s_title = ParagraphStyle("title_knauf", parent=styles["Title"],
                             fontSize=18, textColor=AZUL, spaceAfter=2*mm)
    s_normal = ParagraphStyle("normal_k", parent=styles["Normal"], fontSize=8)
    s_small = ParagraphStyle("small_k", parent=styles["Normal"], fontSize=7)
    s_footer = ParagraphStyle("footer_k", parent=styles["Normal"],
                              fontSize=6, textColor=HexColor("#888888"),
                              alignment=TA_CENTER)

    # ── CABECERA CON LOGO ────────────────────────────────────────
    def safe_str(val, default=""):
        """Convierte cualquier valor (float, None, NaN) a string limpio."""
        if val is None:
            return default
        s = str(val)
        if s in ("nan", "None", "NaT"):
            return default
        return s

    num = safe_str(oferta.get("NUMERO_OFERTA", ""))
    rev = safe_str(oferta.get("REVISION", 0))
    fecha = oferta.get("FECHA", "")
    if hasattr(fecha, "strftime"):
        fecha = fecha.strftime("%d/%m/%Y")
    else:
        fecha = safe_str(fecha)
    comercial = safe_str(oferta.get("COMERCIAL_NOMBRE", oferta.get("COMERCIAL", "")))

    # Logo
    logo_element = Paragraph("<b>KNAUF INDUSTRIES</b>", s_title)
    logo_b64 = get_config("logo_base64", "")
    if logo_b64:
        try:
            logo_data = base64.b64decode(logo_b64)
            logo_io = io.BytesIO(logo_data)
            logo_element = Image(logo_io, width=45*mm, height=15*mm)
        except Exception:
            pass

    emp_nombre = get_config("empresa_nombre", "KNAUF MIRET, S.L.")
    emp_dir = get_config("empresa_direccion", "")
    emp_tel = get_config("empresa_telefono", "")

    fecha_validez = oferta.get("FECHA_VALIDEZ", "")
    if hasattr(fecha_validez, "strftime"):
        fecha_validez = fecha_validez.strftime("%d/%m/%Y")
    else:
        fecha_validez = safe_str(fecha_validez)

    hdr_data = [
        [logo_element,
         Paragraph(f"<b>N. Oferta:</b> {num}&nbsp;&nbsp;&nbsp;<b>Rev:</b> {rev}", s_normal)],
        ["", Paragraph(f"<b>Fecha:</b> {fecha}&nbsp;&nbsp;&nbsp;<b>Validez:</b> {fecha_validez}", s_normal)],
        ["", Paragraph(f"<b>Comercial:</b> {comercial}", s_normal)],
    ]
    if emp_dir:
        hdr_data.append(["", Paragraph(f"<b>Dirección:</b> {emp_dir}", s_normal)])
    if emp_tel:
        hdr_data.append(["", Paragraph(f"<b>Teléfono:</b> {emp_tel}", s_normal)])

    t_hdr = Table(hdr_data, colWidths=[95*mm, 75*mm])
    t_hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(t_hdr)
    elements.append(Spacer(1, 4*mm))

    # ── DATOS DEL CLIENTE ─────────────────────────────────
    elements.append(Paragraph("<b>DATOS DEL CLIENTE</b>", ParagraphStyle(
        "sec_hdr", parent=styles["Normal"], fontSize=10, textColor=white,
        backColor=AZUL, alignment=TA_CENTER, spaceAfter=0, spaceBefore=0,
        leading=14, borderPadding=(2, 4, 2, 4))))
    elements.append(Spacer(1, 1*mm))

    cl_data = [
        [Paragraph(f"<b>Empresa:</b> {safe_str(oferta.get('CLIENTE_NOMBRE',''))}", s_small),
         Paragraph(f"<b>Contacto:</b> {safe_str(oferta.get('CLIENTE_CONTACTO',''))}", s_small)],
        [Paragraph(f"<b>CIF/NIF:</b> {safe_str(oferta.get('CLIENTE_CIF',''))}", s_small),
         Paragraph(f"<b>Teléfono:</b> {safe_str(oferta.get('CLIENTE_TELEFONO',''))}", s_small)],
        [Paragraph(f"<b>Dirección:</b> {safe_str(oferta.get('CLIENTE_DIRECCION',''))}", s_small),
         Paragraph(f"<b>Email:</b> {safe_str(oferta.get('CLIENTE_EMAIL',''))}", s_small)],
    ]
    t_cl = Table(cl_data, colWidths=[90*mm, 75*mm])
    t_cl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(t_cl)
    elements.append(Spacer(1, 5*mm))

    # ── TABLA DE PRODUCTOS ────────────────────────────────
    elements.append(Paragraph("<b>DESCRIPCIÓN DE LA OFERTA</b>", ParagraphStyle(
        "sec2", parent=styles["Normal"], fontSize=10, textColor=AZUL, spaceAfter=2*mm)))

    headers = ["Producto", "Artículo", "Dimensiones", "Planta", "Uds",
               "€/m³", "€/pza", "Importe"]
    prod_data = [[Paragraph(f"<b>{h}</b>", ParagraphStyle("hdr_cell",
                  parent=styles["Normal"], fontSize=6, textColor=white,
                  alignment=TA_CENTER)) for h in headers]]

    for ln in lineas:
        if isinstance(ln, dict):
            # PRECIO_M3 y PRECIO_UNITARIO son los campos canónicos (ya ajustados SIN/CON scrap)
            precio_m3 = float(ln.get('PRECIO_M3', ln.get('EUR_M3_CON_SCRAP', 0)) or 0)
            precio_pza = float(ln.get('PRECIO_UNITARIO', ln.get('PRECIO_PIEZA_CON_SCRAP', 0)) or 0)
            total_linea = float(ln.get('TOTAL_LINEA', 0) or 0)
            row = [
                Paragraph(str(ln.get("TIPO_PRODUCTO", ""))[:20], s_small),
                Paragraph(str(ln.get("CALIDAD", ""))[:25], s_small),
                Paragraph(str(ln.get("DESCRIPCION", "")), s_small),
                Paragraph(str(ln.get("PLANTA", "")), s_small),
                Paragraph(str(int(ln.get("CANTIDAD", 0))), s_small),
                Paragraph(f"{precio_m3:.2f}", s_small),
                Paragraph(f"{precio_pza:.4f}", s_small),
                Paragraph(f"{total_linea:,.2f}", s_small),
            ]
            prod_data.append(row)

    col_w = [22*mm, 28*mm, 25*mm, 18*mm, 14*mm, 18*mm, 18*mm, 22*mm]
    t_prod = Table(prod_data, colWidths=col_w, repeatRows=1)
    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), FONDO_HDR),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, GRIS_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
    ]
    for i in range(1, len(prod_data)):
        if i % 2 == 0:
            t_style.append(("BACKGROUND", (0, i), (-1, i), HexColor("#f8f9fa")))
    t_prod.setStyle(TableStyle(t_style))
    elements.append(t_prod)
    elements.append(Spacer(1, 4*mm))

    # ── TOTALES ───────────────────────────────────────────
    subtotal = float(oferta.get("SUBTOTAL", 0))
    portes = float(oferta.get("PORTES", oferta.get("COSTE_TRANSPORTE", 0)))
    imp_plastico = float(oferta.get("IMPUESTO_PLASTICO_TOTAL", oferta.get("IMPUESTO_PLASTICO", 0)))
    desc_pctg = float(oferta.get("DESCUENTO_PCTG", 0))
    desc_val = float(oferta.get("DESCUENTO_VALOR", subtotal * desc_pctg / 100))
    total = float(oferta.get("TOTAL", 0))

    s_tot_l = ParagraphStyle("tot_l", parent=styles["Normal"], fontSize=8)
    s_tot_r = ParagraphStyle("tot_r", parent=styles["Normal"], fontSize=8, alignment=TA_RIGHT)
    s_tot_b = ParagraphStyle("tot_b", parent=styles["Normal"], fontSize=8,
                             alignment=TA_RIGHT, textColor=AZUL)

    tot_data = [
        [Paragraph("<b>Subtotal producto</b>", s_tot_l), Paragraph(f"<b>{subtotal:,.2f} €</b>", s_tot_b)],
    ]
    if desc_pctg > 0 or desc_val > 0:
        tot_data.append([Paragraph(f"Descuento ({desc_pctg:.1f}%)", s_tot_l),
                         Paragraph(f"-{desc_val:,.2f} €", s_tot_r)])
        subtotal_neto = subtotal - desc_val
        tot_data.append([Paragraph("Subtotal con dto.", s_tot_l),
                         Paragraph(f"{subtotal_neto:,.2f} €", s_tot_r)])
    tot_data.append([Paragraph("Portes", s_tot_l), Paragraph(f"{portes:,.2f} €", s_tot_r)])
    if imp_plastico > 0:
        tot_data.append([Paragraph("Impuesto al plástico", s_tot_l), Paragraph(f"{imp_plastico:,.2f} €", s_tot_r)])
    tot_data.append([Paragraph("<b>Total s/IVA</b>", s_tot_l),
                     Paragraph(f"<b>{total:,.2f} €</b>", s_tot_b)])

    t_tot = Table(tot_data, colWidths=[50*mm, 35*mm], hAlign="RIGHT")
    t_tot.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, GRIS_BORDE),
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_CLARO),
        ("BACKGROUND", (0, -1), (-1, -1), AZUL_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(t_tot)
    elements.append(Spacer(1, 2*mm))

    imp_kg = get_config("impuesto_plastico_kg", "0.45")
    elements.append(Paragraph(
        f"<i>Importe del impuesto al plástico ({imp_kg} €/kg), no incluido en el precio. "
        f"Ley 7/2022, de 8 de abril.</i>", ParagraphStyle(
        "imp_note", parent=styles["Normal"], fontSize=6, textColor=HexColor("#666666"))))
    elements.append(Spacer(1, 5*mm))

    # ── CONDICIONES COMERCIALES ───────────────────────────
    cond_pago = safe_str(oferta.get("CONDICIONES_PAGO", ""))
    cond_transp = safe_str(oferta.get("CONDICIONES_TRANSPORTE", ""))
    obs = safe_str(oferta.get("OBSERVACIONES", ""))

    s_cond_label = ParagraphStyle("cond_label", parent=styles["Normal"],
        fontSize=8, textColor=AZUL)

    if cond_pago or cond_transp or obs:
        cond_rows = []
        if cond_pago:
            cond_rows.append([Paragraph("<b>Condiciones de pago:</b>", s_cond_label),
                              Paragraph(cond_pago, s_normal)])
        if cond_transp:
            cond_rows.append([Paragraph("<b>Condiciones de transporte:</b>", s_cond_label),
                              Paragraph(cond_transp, s_normal)])
        if obs:
            cond_rows.append([Paragraph("<b>Observaciones:</b>", s_cond_label),
                              Paragraph(obs, s_normal)])
        t_cond = Table(cond_rows, colWidths=[55*mm, 110*mm])
        t_cond.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_cond)
        elements.append(Spacer(1, 3*mm))

    # ── CONDICIONES LEGALES (nueva página) ──────────────────
    cond_legales = str(get_config("condiciones_legales", "") or "")
    if cond_legales:
        from reportlab.platypus import PageBreak
        elements.append(PageBreak())
        elements.append(Paragraph("<b>CONDICIONES GENERALES DE VENTA</b>", ParagraphStyle(
            "cond_title", parent=styles["Normal"], fontSize=12, textColor=AZUL,
            spaceAfter=4*mm, alignment=TA_CENTER)))
        elements.append(Spacer(1, 3*mm))

        s_cond_heading = ParagraphStyle("cond_h", parent=styles["Normal"],
            fontSize=8, textColor=AZUL, spaceBefore=3*mm, spaceAfter=1*mm,
            leading=10)
        s_cond_body = ParagraphStyle("cond_b", parent=styles["Normal"],
            fontSize=7, textColor=HexColor("#333333"), spaceAfter=1.5*mm,
            leading=9)

        # Normalizar saltos de línea (la BD puede guardar \n literal)
        cond_text = cond_legales.replace("\\n", "\n")
        for raw_line in cond_text.split("\n"):
            line = raw_line.strip()
            if not line:
                elements.append(Spacer(1, 2*mm))
                continue
            # Detectar títulos: líneas que empiezan con número + punto/paréntesis, o todo mayúsculas
            is_title = (len(line) > 2 and ((line[0].isdigit() and line[1] in ".-)") or line.isupper()))
            if is_title:
                elements.append(Paragraph(f"<b>{line}</b>", s_cond_heading))
            else:
                elements.append(Paragraph(line, s_cond_body))
        elements.append(Spacer(1, 3*mm))

    # ── FOOTER EMPRESA ────────────────────────────────────
    emp = get_config("empresa_nombre", "KNAUF MIRET, S.L.")
    dire = get_config("empresa_direccion", "")
    cif = get_config("empresa_cif", "")
    reg = get_config("empresa_registro", "")
    elements.append(Spacer(1, 8*mm))
    elements.append(Paragraph(f"{emp} — {dire} — {cif}", s_footer))
    if reg:
        elements.append(Paragraph(reg, s_footer))

    doc.build(elements)
    return buf.getvalue()

"""
pdf_generator.py — Generación del PDF de oferta con reportlab.
Replica el modelo ODP de Knauf Industries.
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generar_pdf_oferta(oferta, lineas_df, config, logo_bytes=None):
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

    # Estilos personalizados
    s_title = ParagraphStyle("title_knauf", parent=styles["Title"],
                             fontSize=18, textColor=AZUL, spaceAfter=2*mm)
    s_normal = ParagraphStyle("normal_k", parent=styles["Normal"], fontSize=8)
    s_small = ParagraphStyle("small_k", parent=styles["Normal"], fontSize=7)
    s_footer = ParagraphStyle("footer_k", parent=styles["Normal"],
                              fontSize=6, textColor=HexColor("#888888"),
                              alignment=TA_CENTER)

    # ── CABECERA ──────────────────────────────────────────
    num = oferta.get("NUMERO_OFERTA", "")
    rev = oferta.get("REVISION", 1)
    fecha = oferta.get("FECHA", "")
    if hasattr(fecha, "strftime"):
        fecha = fecha.strftime("%d/%m/%Y")
    validez = oferta.get("VALIDEZ", "")
    if hasattr(validez, "strftime"):
        validez = validez.strftime("%d/%m/%Y")
    comercial = oferta.get("COMERCIAL", "")

    hdr_data = [
        [Paragraph("<b>KNAUF INDUSTRIES</b>", s_title),
         Paragraph(f"<b>N. Oferta:</b> {num}&nbsp;&nbsp;&nbsp;<b>Rev:</b> {rev}", s_normal)],
        ["", Paragraph(f"<b>Fecha:</b> {fecha}&nbsp;&nbsp;&nbsp;<b>Validez:</b> {validez}", s_normal)],
        ["", Paragraph(f"<b>Comercial:</b> {comercial}", s_normal)],
    ]
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

    cl = {k: str(oferta.get(k, "")) for k in [
        "CLIENTE_NOMBRE", "CLIENTE_RAZON_SOCIAL", "CLIENTE_DIRECCION",
        "CLIENTE_CP_CIUDAD", "CLIENTE_NIF", "CLIENTE_CONTACTO",
        "CLIENTE_TELEFONO", "CLIENTE_EMAIL"
    ]}
    cl_data = [
        [Paragraph(f"<b>Empresa:</b> {cl['CLIENTE_NOMBRE']}", s_small),
         Paragraph(f"<b>Contacto:</b> {cl['CLIENTE_CONTACTO']}", s_small)],
        [Paragraph(f"<b>Razón Social:</b> {cl['CLIENTE_RAZON_SOCIAL']}", s_small),
         Paragraph(f"<b>Teléfono:</b> {cl['CLIENTE_TELEFONO']}", s_small)],
        [Paragraph(f"<b>Dirección:</b> {cl['CLIENTE_DIRECCION']}", s_small),
         Paragraph(f"<b>Email:</b> {cl['CLIENTE_EMAIL']}", s_small)],
        [Paragraph(f"{cl['CLIENTE_CP_CIUDAD']}", s_small),
         Paragraph(f"<b>NIF:</b> {cl['CLIENTE_NIF']}", s_small)],
    ]
    t_cl = Table(cl_data, colWidths=[95*mm, 75*mm])
    t_cl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, GRIS_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(t_cl)
    elements.append(Spacer(1, 5*mm))

    # ── TABLA DE PRODUCTOS ────────────────────────────────
    elements.append(Paragraph("<b>DESCRIPCIÓN DE LA OFERTA</b>", ParagraphStyle(
        "sec2", parent=styles["Normal"], fontSize=10, textColor=AZUL, spaceAfter=2*mm)))

    headers = ["Producto", "Calidad", "Dimensiones", "Cantidad",
               "€/m³", "m³/pieza", "€/pieza", "Importe"]
    prod_data = [[Paragraph(f"<b>{h}</b>", ParagraphStyle("hdr_cell",
                  parent=styles["Normal"], fontSize=7, textColor=white,
                  alignment=TA_CENTER)) for h in headers]]

    for _, ln in lineas_df.iterrows():
        row = [
            Paragraph(str(ln.get("TIPO_PRODUCTO", "")), s_small),
            Paragraph(str(ln.get("CALIDAD", ""))[:30], s_small),
            Paragraph(str(ln.get("DESCRIPCION", ln.get("DIMENSION", ""))), s_small),
            Paragraph(str(int(ln.get("CANTIDAD", 0))), s_small),
            Paragraph(f"{ln.get('PRECIO_M3', 0):.2f}", s_small),
            Paragraph(f"{ln.get('M3_PIEZA', 0):.4f}", s_small),
            Paragraph(f"{ln.get('PRECIO_UNITARIO', 0):.2f}", s_small),
            Paragraph(f"{ln.get('TOTAL_LINEA', 0):.2f}", s_small),
        ]
        prod_data.append(row)

    col_w = [22*mm, 32*mm, 26*mm, 16*mm, 16*mm, 16*mm, 18*mm, 22*mm]
    t_prod = Table(prod_data, colWidths=col_w, repeatRows=1)
    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), FONDO_HDR),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, GRIS_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
    ]
    for i in range(1, len(prod_data)):
        if i % 2 == 0:
            t_style.append(("BACKGROUND", (0, i), (-1, i), HexColor("#f8f9fa")))
    t_prod.setStyle(TableStyle(t_style))
    elements.append(t_prod)
    elements.append(Spacer(1, 4*mm))

    # ── TOTALES ───────────────────────────────────────────
    subtotal = float(oferta.get("SUBTOTAL", 0))
    transporte = float(oferta.get("COSTE_TRANSPORTE", 0))
    imp_plastico = float(oferta.get("IMPUESTO_PLASTICO", 0))
    desc_pctg = float(oferta.get("DESCUENTO_PCTG", 0))
    desc_val = subtotal * desc_pctg / 100
    total = float(oferta.get("TOTAL", 0))

    s_tot_l = ParagraphStyle("tot_l", parent=styles["Normal"], fontSize=8)
    s_tot_r = ParagraphStyle("tot_r", parent=styles["Normal"], fontSize=8, alignment=TA_RIGHT)
    s_tot_b = ParagraphStyle("tot_b", parent=styles["Normal"], fontSize=8,
                             alignment=TA_RIGHT, textColor=AZUL)

    tot_data = [
        [Paragraph("<b>Subtotal</b>", s_tot_l), Paragraph(f"<b>{subtotal:,.2f} €</b>", s_tot_b)],
        [Paragraph("Coste transporte", s_tot_l), Paragraph(f"{transporte:,.2f} €", s_tot_r)],
        [Paragraph("Subtotal con transporte", s_tot_l), Paragraph(f"{subtotal + transporte:,.2f} €", s_tot_r)],
        [Paragraph("Impuesto al plástico", s_tot_l), Paragraph(f"{imp_plastico:,.2f} €", s_tot_r)],
        [Paragraph(f"Descuento ({desc_pctg:.1f}%)", s_tot_l), Paragraph(f"-{desc_val:,.2f} €", s_tot_r)],
        [Paragraph("<b>Total s/IVA</b>", s_tot_l), Paragraph(f"<b>{total:,.2f} €</b>", s_tot_b)],
    ]
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

    imp_kg = config.get("impuesto_plastico_kg", "0.45")
    elements.append(Paragraph(
        f"<i>Importe del impuesto al plástico ({imp_kg} €/kg), no incluido en el precio. "
        f"Ley 7/2022, de 8 de abril.</i>", ParagraphStyle(
        "imp_note", parent=styles["Normal"], fontSize=6, textColor=HexColor("#666666"))))
    elements.append(Spacer(1, 5*mm))

    # ── CONDICIONES ───────────────────────────────────────
    cond_headers = ["Forma de entrega", "Plazo de entrega", "Cond. de pago", "Plazo de pago"]
    cond_vals = [
        str(oferta.get("FORMA_ENTREGA", ""))[:35],
        str(oferta.get("PLAZO_ENTREGA", ""))[:35],
        str(oferta.get("CONDICIONES_PAGO", ""))[:35],
        str(oferta.get("PLAZO_PAGO", ""))[:35],
    ]
    s_cond = ParagraphStyle("cond", parent=styles["Normal"], fontSize=7, alignment=TA_CENTER)
    cond_data = [
        [Paragraph(f"<b>{h}</b>", ParagraphStyle("ch", parent=s_cond, textColor=white))
         for h in cond_headers],
        [Paragraph(v, s_cond) for v in cond_vals],
    ]
    cw = [42*mm, 42*mm, 43*mm, 43*mm]
    t_cond = Table(cond_data, colWidths=cw)
    t_cond.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FONDO_HDR),
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, GRIS_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_cond)
    elements.append(Spacer(1, 4*mm))

    # ── OBSERVACIONES ─────────────────────────────────────
    obs = oferta.get("OBSERVACIONES", "")
    if obs:
        elements.append(Paragraph(f"<b>OBSERVACIONES:</b> {obs}", s_normal))
        elements.append(Spacer(1, 3*mm))

    # ── FOOTER EMPRESA ────────────────────────────────────
    emp = config.get("empresa_nombre", "KNAUF MIRET, S.L.")
    dire = config.get("empresa_direccion", "")
    cif = config.get("empresa_cif", "")
    reg = config.get("empresa_registro", "")
    elements.append(Spacer(1, 8*mm))
    elements.append(Paragraph(f"{emp} — {dire} — {cif}", s_footer))
    elements.append(Paragraph(reg, s_footer))

    doc.build(elements)
    return buf.getvalue()

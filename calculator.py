"""
calculator.py — Motor de cálculo KTM replicado con fidelidad de fórmula.
Todas las fórmulas corresponden 1:1 con las celdas del Excel KTM.
"""
import math
from data import (
    get_tarifa, get_planta, get_logistica_row, load_logistica,
    get_coste_transporte, load_materias_primas
)


# ── Familias con múltiplos logísticos (de los docx) ──────────────────────────
FAMILIAS_CON_MULTIPLOS = [
    "PANEL_AISLANTE.EPS", "PANEL_AISLANTE.GRAFITO", "PANEL_AISLANTE.SOSTENIBLES",
    "ETIX.EPS", "ETIX.GRAFITO", "ETIX.SOSTENIBLES",
    "BOVEDILLAS.EPS",
    "ALIGERADOS.EPS",
    "RECTIBOARD.EPS", "RECTIBOARD.GRAFITO",
]


def _redondear_bloque(largo, ancho, grueso, planta):
    """
    Replica las fórmulas M4/M5/M6 del KTM:
    - Vilafranca/Valencia: largo redondea a miles (ROUNDDOWN(,-3)), ancho/grueso a cientos
    - Valladolid: largo a cientos (ROUNDDOWN(,-2)), ancho/grueso a cientos
    """
    if planta == "Valladolid":
        largo_r = math.floor(largo / 100) * 100
    else:
        largo_r = math.floor(largo / 1000) * 1000
    ancho_r = math.floor(ancho / 100) * 100
    grueso_r = math.floor(grueso / 100) * 100
    return largo_r, ancho_r, grueso_r


def _get_precio_mp_base(materia_prima):
    """Obtiene el precio actual de la materia prima (€/kg)."""
    df = load_materias_primas()
    if df.empty:
        return 0.0
    match = df[df["TIPO"] == materia_prima]
    if match.empty:
        return 0.0
    return float(match.iloc[0].get("PRECIO_BASE_KG", 0) or 0)


# Precios base originales (referencia fija del KTM, para calcular el incremento)
_PRECIOS_BASE_ORIGINALES = {
    "EPS_Blanco": 1.45,
    "EPS_Grafito": 1.75,
    "EPS_SOSTENIBLES": 3.00,
}


def calcular_linea(familia, articulo, planta_nombre, densidad,
                   largo_pieza, ancho_pieza, espesor_pieza,
                   cantidad_pedida, margen_pctg=0.0, materia_prima="EPS_Blanco"):
    """
    Motor de cálculo KTM — réplica exacta de las fórmulas del Excel.
    
    Fórmulas KTM replicadas:
    - J12: piezas_bloque = INT(L/l) × INT(A/a) × INT(G/e)
    - N7: m3_piezas_neto = m3_pieza × piezas_bloque
    - N8: m3_bloque_bruto = (L_bruto × A_bruto × G_bruto) / 1e9
    - M35: incremento_mp = (precio_actual - precio_base) × densidad
    - R35: precio_exworks = incremento_mp + tarifa_base_planta
    - TARIFAS J6: precio_con_margen = tarifa_base × (1 + margen%)
    - N13: pieza_con_scrap = (m3_bloque × €/m3) / piezas
    - N14: pieza_sin_scrap = (m3_neto × €/m3) / piezas
    """
    largo_pieza = float(largo_pieza)
    ancho_pieza = float(ancho_pieza)
    espesor_pieza = float(espesor_pieza)
    cantidad_pedida = int(cantidad_pedida)
    margen_pctg = float(margen_pctg)
    densidad = float(densidad)

    # ── 1. Datos de la planta y Bloque (Corte vs Fabricación) ─────────────
    planta = get_planta(planta_nombre)
    if planta is None:
        return {"error": f"Planta '{planta_nombre}' no encontrada"}

    largo_bloque_raw = float(planta["LARGO_MAX"])
    ancho_bloque_raw = float(planta["ANCHO_MAX"])
    grueso_bloque_raw = float(planta["GRUESO_MAX"])

    # Vilafranca (Ejemplo ETIX): Fabricación: 6110 x 1215 x 1050 | Corte: 6000 x 1200 x 1000
    if planta_nombre == "Valladolid":
        l_fab, w_fab, h_fab = 5080, 1250, 530
    elif planta_nombre == "Valencia":
        l_fab, w_fab, h_fab = 4040, 1220, 1030
    else: # Vilafranca / Otros
        l_fab, w_fab, h_fab = 6110, 1215, 1050

    vol_bloque_fab = (l_fab * w_fab * h_fab) / 1_000_000_000

    # ── 2. Redondear bloque para CORTE (KTM: M4/M5/M6) ──────────────────
    largo_b, ancho_b, grueso_b = _redondear_bloque(
        largo_bloque_raw, ancho_bloque_raw, grueso_bloque_raw, planta_nombre
    )
    vol_bloque_net = (largo_b * ancho_b * grueso_b) / 1_000_000_000

    # ── 3. Piezas por bloque (KTM: J12) sobre el bloque de CORTE ────────
    pzas_largo = int(largo_b / largo_pieza)
    pzas_ancho = int(ancho_b / ancho_pieza)
    pzas_alto = int(grueso_b / espesor_pieza)
    pzas_bloque = pzas_largo * pzas_ancho * pzas_alto

    if pzas_bloque == 0:
        return {"error": "❌ Las dimensiones no permiten cortar piezas del bloque"}

    # ── 4. Volúmenes (KTM: N7, N8, N9) ───────────────────────────────────
    m3_pieza = (largo_pieza * ancho_pieza * espesor_pieza) / 1_000_000_000
    m3_piezas_neto = m3_pieza * pzas_bloque           # N7 (Total piezas)
    
    # ── 5. Scrap % (KTM: J13) ────────────────────────────────────────────
    # Basado en el bloque de CORTE (6000x1200...)
    scrap_ratio = (vol_bloque_net - m3_piezas_neto) / vol_bloque_net if vol_bloque_net > 0 else 0
    scrap_pctg = scrap_ratio * 100

    # ── 6. Incremento materia prima (KTM: M35) ───────────────────────────
    precio_mp_actual = _get_precio_mp_base(materia_prima)
    precio_mp_original = _PRECIOS_BASE_ORIGINALES.get(materia_prima, precio_mp_actual)
    incremento_mp = (precio_mp_actual - precio_mp_original) * densidad

    # ── 7. Tarifa base de planta (KTM: N35) ─────────────────────────────
    tarifa_base = get_tarifa(familia, articulo, planta_nombre)
    if tarifa_base <= 0:
        return {"error": f"❌ No hay tarifa para {familia} / {articulo} en {planta_nombre}"}

    # ── 8. Precio Ex Works €/m³ y Margen ───────────────────────────────
    precio_exworks_m3_neto = (incremento_mp + tarifa_base) * (1 + margen_pctg / 100)

    # ── 9. Aplicación de Merma y Seguridad (Metodología KTM) ───────────
    # KTM: El precio se encarece por la merma (dividiendo por 1-scrap)
    # y por la diferencia entre el bloque que se fabrica (fab) y el que se corta (net).
    factor_seguridad = vol_bloque_fab / vol_bloque_net
    
    # Precio €/m³ CON Scrap real
    eur_m3_con_scrap = (precio_exworks_m3_neto / (1 - scrap_ratio)) * factor_seguridad
    eur_m3_sin_scrap = precio_exworks_m3_neto * factor_seguridad

    # ── 10. Precio por Pieza (KTM: N13) ──────────────────────────────────
    # N13 = (m3_bloque_fabricacion × €/m3_base) / piezas_bloque
    precio_pieza_con_scrap = (vol_bloque_fab * precio_exworks_m3_neto) / (pzas_bloque * (1 - scrap_ratio))
    precio_pieza_sin_scrap = m3_pieza * eur_m3_sin_scrap

    # ── 13. Ajuste a múltiplos logísticos ─────────────────────────────────
    pzas_paquete = 0
    cantidad_ajustada = cantidad_pedida

    if familia in FAMILIAS_CON_MULTIPLOS:
        producto_log = _familia_to_logistica(familia)
        if producto_log:
            dim_str = f"{int(largo_pieza)}X{int(ancho_pieza)}"
            pzas_paquete, pzas_bloque_log = get_logistica_row(producto_log, dim_str, espesor_pieza)
            if pzas_paquete > 0:
                # Para ETIX y PANEL_AISLANTE: múltiplos de BLOQUE LOGÍSTICO (de la tabla)
                # Para otras familias: usamos paquete
                multiplo_final = pzas_paquete
                if "ETIX" in familia or "PANEL_AISLANTE" in familia:
                    multiplo_final = pzas_bloque_log if pzas_bloque_log > 0 else pzas_paquete
                
                paquetes = max(1, math.ceil(cantidad_pedida / multiplo_final))
                cantidad_ajustada = paquetes * multiplo_final
                pzas_paquete = multiplo_final # Para que la UI muestre el múltiplo correcto

    # ── 14. Transporte (referencia) ───────────────────────────────────────
    coste_transp_m3, coste_grupaje_m3 = get_coste_transporte(planta_nombre)

    # ── 15. Total línea ──────────────────────────────────────────────────
    total_linea = precio_pieza_con_scrap * cantidad_ajustada

    # ── 16. Descripción ──────────────────────────────────────────────────
    desc = f"{int(largo_pieza)}×{int(ancho_pieza)}×{int(espesor_pieza)} mm"

    return {
        "TIPO_PRODUCTO": familia,
        "CALIDAD": articulo,
        "MATERIA_PRIMA": materia_prima,
        "DENSIDAD": densidad,
        "DESCRIPCION": desc,
        "PLANTA": planta_nombre,
        "DIMENSION": desc,
        "ESPESOR": espesor_pieza,

        # Bloque
        "BLOQUE_BRUTO": f"{int(largo_bloque_raw)}×{int(ancho_bloque_raw)}×{int(grueso_bloque_raw)}",
        "BLOQUE_REDONDEADO": f"{int(largo_b)}×{int(ancho_b)}×{int(grueso_b)}",

        # Cantidades
        "CANTIDAD_PEDIDA": cantidad_pedida,
        "CANTIDAD": cantidad_ajustada,
        "PZAS_BLOQUE": pzas_bloque,
        "PZAS_LARGO": pzas_largo,
        "PZAS_ANCHO": pzas_ancho,
        "PZAS_ALTO": pzas_alto,
        "PZAS_PAQUETE": pzas_paquete,

        # Volúmenes
        "M3_PIEZA": round(m3_pieza, 6),
        "M3_PIEZAS_NETO": round(m3_piezas_neto, 6),
        "M3_BLOQUE_BRUTO": round(vol_bloque_fab, 6),
        "SCRAP_PCTG": round(scrap_pctg, 2),

        # Materia prima
        "INCREMENTO_MP": round(incremento_mp, 4),
        "PRECIO_MP_ACTUAL": precio_mp_actual,
        "PRECIO_MP_ORIGINAL": precio_mp_original,

        # Precios €/m³
        "TARIFA_BASE_PLANTA": round(tarifa_base, 4),
        "PRECIO_EXWORKS_M3": round(precio_exworks_m3_neto, 4),
        "MARGEN_PCTG": margen_pctg,
        "PRECIO_CON_MARGEN_M3": round(precio_exworks_m3_neto, 4),
        "EUR_M3_CON_SCRAP": round(eur_m3_con_scrap, 4),
        "EUR_M3_SIN_SCRAP": round(eur_m3_sin_scrap, 4),

        # Precios por pieza
        "PRECIO_PIEZA_CON_SCRAP": round(precio_pieza_con_scrap, 4),
        "PRECIO_PIEZA_SIN_SCRAP": round(precio_pieza_sin_scrap, 4),

        # Para compatibilidad con save_oferta
        "PRECIO_M3": round(eur_m3_con_scrap, 4),
        "PRECIO_UNITARIO": round(precio_pieza_con_scrap, 4),
        "TOTAL_LINEA": round(total_linea, 2),

        # Transporte (referencia de planta)
        "TRANSPORTE_M3_PLANTA": round(coste_transp_m3, 2),
        "GRUPAJE_M3_PLANTA": round(coste_grupaje_m3, 2),

        # Info
        "CODIGO_ARTICULO": "",
        "IMPUESTO_PLASTICO": 0,
        "AJUSTE_INFO": _info_ajuste(cantidad_pedida, cantidad_ajustada, pzas_paquete),
        "BLOQUE_INFO": (
            f"Bloque Fab {int(l_fab)}×{int(w_fab)}×{int(h_fab)} / Corte {int(largo_b)}×{int(ancho_b)}×{int(grueso_b)} → "
            f"{pzas_bloque} pzas ({pzas_largo}×{pzas_ancho}×{pzas_alto}) | "
            f"Scrap: {round(scrap_pctg, 1)}%"
        ),
    }


def _familia_to_logistica(familia):
    """Mapea familia KTM a producto en tabla LOGISTICA."""
    mapping = {
        "PANEL_AISLANTE.EPS": "PLANCHA",
        "PANEL_AISLANTE.GRAFITO": "PLANCHA",
        "PANEL_AISLANTE.SOSTENIBLES": "PLANCHA",
        "ETIX.EPS": "PLANCHA",
        "ETIX.GRAFITO": "PLANCHA",
        "ETIX.SOSTENIBLES": "PLANCHA",
        "BOVEDILLAS.EPS": "BOVEDILLA",
        "ALIGERADOS.EPS": "CASETON",
        "RECTIBOARD.EPS": "PLANCHA",
        "RECTIBOARD.GRAFITO": "PLANCHA",
    }
    return mapping.get(familia)


def get_dimensiones_disponibles(producto):
    df = load_logistica()
    dims = df[df["PRODUCTO"] == producto]["DIMENSION"].unique().tolist()
    return sorted([d for d in dims if d])


def get_espesores_disponibles(producto, dimension):
    df = load_logistica()
    flt = df[(df["PRODUCTO"] == producto) & (df["DIMENSION"] == dimension)]
    return sorted(flt["ESPESOR"].unique().tolist())


def _info_ajuste(pedida, ajustada, multiplo):
    if pedida == ajustada:
        if multiplo > 0:
            return f"✅ {ajustada} piezas ({ajustada // multiplo} paquetes de {multiplo})"
        return f"✅ {ajustada} piezas"
    return f"⚠️ Ajustado: {pedida} → {ajustada} (múltiplo de {multiplo})"

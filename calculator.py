"""
calculator.py — Motor de cálculo de precios y cantidades.
"""
import math
from data import get_precio_m3, get_logistica_row, get_planta, load_logistica

PRODUCTOS_ESTANDAR = ["PLANCHA", "SATE"]
PRODUCTOS_MEDIDA = ["CASETON", "BOVEDILLA", "CILINDROS", "TIRAS"]
TODOS_PRODUCTOS = PRODUCTOS_ESTANDAR + PRODUCTOS_MEDIDA


def calcular_linea_estandar(producto, calidad, dimension, espesor,
                            cantidad_pedida, grupo_compra, planta_nombre):
    espesor = float(espesor)
    cantidad_pedida = int(cantidad_pedida)
    pzas_paq, pzas_blq = get_logistica_row(producto, dimension, espesor)

    if pzas_paq > 0:
        cantidad_ajustada = int(math.floor(cantidad_pedida / pzas_paq)) * pzas_paq
    else:
        cantidad_ajustada = cantidad_pedida
    if cantidad_ajustada <= 0 and pzas_paq > 0:
        cantidad_ajustada = pzas_paq

    largo_mm, ancho_mm = _parse_dimension(dimension)
    m3_pieza = (largo_mm * ancho_mm * espesor) / 1_000_000_000

    precio_m3 = get_precio_m3(producto, calidad, grupo_compra)
    precio_unitario = precio_m3 * m3_pieza
    total = precio_unitario * cantidad_ajustada
    desc = f"{dimension} x {int(espesor)}mm"

    return {
        "TIPO_PRODUCTO": producto, "CALIDAD": calidad,
        "DIMENSION": dimension, "ESPESOR": espesor,
        "CANTIDAD": cantidad_ajustada, "CANTIDAD_PEDIDA": cantidad_pedida,
        "PZAS_PAQUETE": pzas_paq, "PZAS_BLOQUE": pzas_blq,
        "PRECIO_M3": round(precio_m3, 4), "M3_PIEZA": round(m3_pieza, 6),
        "PRECIO_UNITARIO": round(precio_unitario, 4),
        "TOTAL_LINEA": round(total, 2),
        "DESCRIPCION": desc, "CODIGO_ARTICULO": "", "IMPUESTO_PLASTICO": 0,
        "AJUSTE_INFO": _info_ajuste(cantidad_pedida, cantidad_ajustada, pzas_paq),
    }


def calcular_linea_medida(producto, calidad, largo_mm, ancho_mm, alto_mm,
                          cantidad_pedida, grupo_compra, planta_nombre):
    largo_mm = float(largo_mm)
    ancho_mm = float(ancho_mm)
    alto_mm = float(alto_mm)
    cantidad_pedida = int(cantidad_pedida)

    planta = get_planta(planta_nombre)
    if planta is None:
        return {"error": f"Planta '{planta_nombre}' no encontrada"}

    largo_max = float(planta["LARGO_MAX"])
    ancho_max = float(planta["ANCHO_MAX"])
    grueso_max = float(planta["GRUESO_MAX"])
    min_m3 = float(planta["MIN_M3"])

    if not (largo_mm <= largo_max and ancho_mm <= ancho_max and alto_mm <= grueso_max):
        return {"error": f"❌ NO CABE. Máx bloque: {int(largo_max)}x{int(ancho_max)}x{int(grueso_max)} mm"}

    pzas_largo = int(largo_max / largo_mm)
    pzas_ancho = int(ancho_max / ancho_mm)
    pzas_alto = int(grueso_max / alto_mm)
    pzas_bloque = pzas_largo * pzas_ancho * pzas_alto

    if pzas_bloque == 0:
        return {"error": "❌ Las dimensiones no permiten cortar piezas del bloque."}

    m3_pieza = (largo_mm * ancho_mm * alto_mm) / 1_000_000_000
    pzas_min_logistico = math.ceil(min_m3 / m3_pieza) if m3_pieza > 0 else 1

    pzas_paq = 0
    if producto == "BOVEDILLA":
        pzas_paq, _ = get_logistica_row("BOVEDILLA", "", alto_mm)

    cantidad_ajustada = cantidad_pedida
    if pzas_paq > 0:
        cantidad_ajustada = int(math.floor(cantidad_pedida / pzas_paq)) * pzas_paq
        if cantidad_ajustada <= 0:
            cantidad_ajustada = pzas_paq

    precio_m3 = get_precio_m3(producto, calidad, grupo_compra)
    precio_unitario = precio_m3 * m3_pieza
    total = precio_unitario * cantidad_ajustada
    desc = f"{int(largo_mm)}x{int(ancho_mm)}x{int(alto_mm)}"

    return {
        "TIPO_PRODUCTO": producto, "CALIDAD": calidad,
        "DIMENSION": desc, "ESPESOR": alto_mm,
        "CANTIDAD": cantidad_ajustada, "CANTIDAD_PEDIDA": cantidad_pedida,
        "PZAS_PAQUETE": pzas_paq, "PZAS_BLOQUE": pzas_bloque,
        "PRECIO_M3": round(precio_m3, 4), "M3_PIEZA": round(m3_pieza, 6),
        "PRECIO_UNITARIO": round(precio_unitario, 4),
        "TOTAL_LINEA": round(total, 2),
        "DESCRIPCION": desc, "CODIGO_ARTICULO": "", "IMPUESTO_PLASTICO": 0,
        "PZAS_MIN_LOGISTICO": pzas_min_logistico, "CABE": True,
        "AJUSTE_INFO": _info_ajuste(cantidad_pedida, cantidad_ajustada, pzas_paq),
        "BLOQUE_INFO": f"{int(largo_max)}x{int(ancho_max)}x{int(grueso_max)} mm → {pzas_bloque} pzas/bloque",
    }


def get_dimensiones_disponibles(producto):
    df = load_logistica()
    dims = df[df["PRODUCTO"] == producto]["DIMENSION"].unique().tolist()
    return sorted([d for d in dims if d])


def get_espesores_disponibles(producto, dimension):
    df = load_logistica()
    flt = df[(df["PRODUCTO"] == producto) & (df["DIMENSION"] == dimension)]
    return sorted(flt["ESPESOR"].unique().tolist())


def _parse_dimension(dim_str):
    if not dim_str or "x" not in dim_str.lower():
        return (0, 0)
    parts = dim_str.lower().split("x")
    try:
        return (float(parts[0]), float(parts[1]))
    except (ValueError, IndexError):
        return (0, 0)


def _info_ajuste(pedida, ajustada, multiplo):
    if pedida == ajustada:
        if multiplo > 0:
            return f"✅ {ajustada} piezas ({ajustada // multiplo} paquetes de {multiplo})"
        return f"✅ {ajustada} piezas"
    return f"⚠️ Ajustado: {pedida} → {ajustada} (múltiplo de {multiplo})"

"""
data.py — Capa de datos Snowflake para App Ofertas v2 (KTM integrado).
Usa snowflake-connector-python (mismo patrón que Forecast).
"""
import streamlit as st
import pandas as pd
import math
from datetime import datetime, date

# ── Tablas ────────────────────────────────────────────────────────────────────
SCHEMA = "OFERTAS_DB.APP"
T_TARIFAS     = f"{SCHEMA}.TARIFAS"
T_CLIENTES    = f"{SCHEMA}.CLIENTES"
T_TRANSPORTE  = f"{SCHEMA}.TRANSPORTE"
T_MATERIAS    = f"{SCHEMA}.MATERIAS_PRIMAS"
T_LOGISTICA   = f"{SCHEMA}.LOGISTICA"
T_PLANTAS     = f"{SCHEMA}.PLANTAS"
T_OFERTAS     = f"{SCHEMA}.OFERTAS"
T_LINEAS      = f"{SCHEMA}.OFERTA_LINEAS"
T_USUARIOS    = f"{SCHEMA}.USUARIOS"
T_CONFIG      = f"{SCHEMA}.CONFIG"

# Familias de producto del KTM
FAMILIAS_PRODUCTO = {
    "BLOQUES": ["BLOQUES.EPS", "BLOQUES.GRAFITO", "BLOQUES.SOSTENIBLES"],
    "PANELES": ["PANEL_AISLANTE.EPS", "PANEL_AISLANTE.GRAFITO", "PANEL_AISLANTE.SOSTENIBLES"],
    "ALIGERADOS": ["ALIGERADOS.EPS"],
    "BOVEDILLAS": ["BOVEDILLAS.EPS"],
    "PERLA": ["PERLA.EPS"],
    "LAMINADOS <250mm": [
        "LAMINADOS_EPS_Menor_250_mm", "LAMINADOS_GRAFITO_Menor_250_mm",
        "LAMINADOS_SOSTENIBLES_Menor_250_mm"],
    "LAMINADOS 250-500mm": [
        "LAMINADOS_EPS_500_A_250_mm", "LAMINADOS_GRAFITO_500_A_250_mm",
        "LAMINADOS_SOSTENIBLES_500_A_250_mm"],
    "LAMINADOS 500-1000mm": [
        "LAMINADOS_EPS_1000_A_500_mm", "LAMINADOS_GRAFITO_1000_A_500_mm",
        "LAMINADOS_SOSTENIBLES_1000_A_500_mm"],
    "LAMINADOS >1000mm": [
        "LAMINADOS_EPS_Mayor_1000_mm", "LAMINADOS_GRAFITO_Mayor_1000_mm",
        "LAMINADOS_SOSTENIBLES_Mayor_1000_mm"],
    "MECANIZADOS <250mm": [
        "MECANIZADOS_EPS_Menor_250_mm", "MECANIZADOS_GRAFITO_Menor_250_mm",
        "MECANIZADOS_SOSTENIBLES_Menor_250_mm"],
    "MECANIZADOS 250-500mm": [
        "MECANIZADOS_EPS_500_A_250_mm", "MECANIZADOS_GRAFITO_500_A_250_mm",
        "MECANIZADOS_SOSTENIBLES_500_A_250_mm"],
    "MECANIZADOS 500-1000mm": [
        "MECANIZADOS_EPS_1000_A_500_mm", "MECANIZADOS_GRAFITO_1000_A_500_mm",
        "MECANIZADOS_SOSTENIBLES_1000_A_500_mm"],
    "MECANIZADOS >1000mm": [
        "MECANIZADOS_EPS_Mayor_1000_mm", "MECANIZADOS_GRAFITO_Mayor_1000_mm",
        "MECANIZADOS_SOSTENIBLES_Mayor_1000_mm"],
    "RECTIBOARD": ["RECTIBOARD.EPS", "RECTIBOARD.GRAFITO"],
    "Knauf ETIX": ["ETIX.EPS"],
    "Knauf ETIX Grafit": ["ETIX.GRAFITO"],
}

TIPOS_MATERIA_PRIMA = ["EPS_Blanco", "EPS_Grafito", "EPS_SOSTENIBLES"]

PLANTAS = ["Vilafranca", "Valencia", "Valladolid"]


# ── Conexión Snowflake ────────────────────────────────────────────────────────

def _get_connection():
    """Crea o reutiliza conexión a Snowflake (mismo patrón que Forecast)."""
    if '_sf_conn' in st.session_state and st.session_state['_sf_conn'] is not None:
        conn = st.session_state['_sf_conn']
        try:
            conn.cursor().execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            st.session_state['_sf_conn'] = None

    import snowflake.connector
    try:
        conn = snowflake.connector.connect(
            account   = st.secrets["SNOWFLAKE_ACCOUNT"],
            user      = st.secrets["SNOWFLAKE_USER"],
            password  = st.secrets["SNOWFLAKE_PASSWORD"],
            warehouse = st.secrets.get("SNOWFLAKE_WAREHOUSE", "OFERTAS_WH"),
            database  = st.secrets.get("SNOWFLAKE_DATABASE", "OFERTAS_DB"),
            schema    = st.secrets.get("SNOWFLAKE_SCHEMA", "APP"),
        )
        st.session_state['_sf_conn'] = conn
        return conn
    except Exception as e:
        st.error(f"❌ Error de conexión a Snowflake: `{type(e).__name__}: {e}`")
        return None


def _query(sql):
    """Ejecuta SQL y devuelve DataFrame."""
    conn = _get_connection()
    if conn is None:
        return pd.DataFrame()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.error(f"❌ Error SQL: `{e}`")
        return pd.DataFrame()


def _exec(sql):
    """Ejecuta SQL sin devolver datos."""
    conn = _get_connection()
    if conn is None:
        raise ConnectionError("No hay conexión a Snowflake")
    conn.cursor().execute(sql)


def _esc(val):
    """Escapa comillas simples para SQL."""
    if val is None:
        return ""
    return str(val).replace("'", "''")


# ── CONFIG ────────────────────────────────────────────────────────────────────

def get_config(clave, default=""):
    df = _query(f"SELECT VALOR FROM {T_CONFIG} WHERE CLAVE = '{_esc(clave)}'")
    return df.iloc[0]["VALOR"] if len(df) > 0 else default


def set_config(clave, valor):
    _exec(f"""
        MERGE INTO {T_CONFIG} t USING (SELECT '{_esc(clave)}' AS CLAVE) s ON t.CLAVE = s.CLAVE
        WHEN MATCHED THEN UPDATE SET VALOR = '{_esc(valor)}'
        WHEN NOT MATCHED THEN INSERT (CLAVE, VALOR) VALUES ('{_esc(clave)}', '{_esc(valor)}')
    """)


# ── USUARIOS ──────────────────────────────────────────────────────────────────

def _get_admin_password():
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def load_users():
    """Devuelve dict {email: {password, nombre, rol}}."""
    users = {}
    pwd = _get_admin_password()
    if pwd:
        users['vbrrsg@gmail.com'] = {
            'password': pwd, 'nombre': 'Victor Borrás', 'rol': 'admin'
        }

    df = _query(f"SELECT EMAIL, PASSWORD, NOMBRE, ROL FROM {T_USUARIOS}")
    if not df.empty:
        for _, r in df.iterrows():
            email = str(r["EMAIL"]).strip().lower()
            users[email] = {
                "password": str(r["PASSWORD"]).strip(),
                "nombre": str(r["NOMBRE"]),
                "rol": str(r.get("ROL", "comercial")),
            }
    return users


def save_users_from_df(df_users):
    """Reemplaza comerciales en USUARIOS."""
    _exec(f"DELETE FROM {T_USUARIOS} WHERE ROL = 'comercial'")
    batch = []
    for _, r in df_users.iterrows():
        email = str(r.get("Email", r.get("EMAIL", ""))).strip().lower()
        pwd = str(r.get("Password", r.get("PASSWORD", ""))).strip()
        nombre = str(r.get("Nombre", r.get("NOMBRE", ""))).strip()
        if email and pwd and '@' in email and email != 'nan':
            batch.append(f"('{_esc(email)}', '{_esc(pwd)}', '{_esc(nombre)}', 'comercial')")
        if len(batch) >= 100:
            _exec(f"INSERT INTO {T_USUARIOS} (EMAIL, PASSWORD, NOMBRE, ROL) VALUES {', '.join(batch)}")
            batch = []
    if batch:
        _exec(f"INSERT INTO {T_USUARIOS} (EMAIL, PASSWORD, NOMBRE, ROL) VALUES {', '.join(batch)}")

    _exec(f"""
        INSERT INTO {T_USUARIOS} (EMAIL, PASSWORD, NOMBRE, ROL)
        SELECT 'vbrrsg@gmail.com','Albope5@','Victor Borrás','admin'
        WHERE NOT EXISTS (SELECT 1 FROM {T_USUARIOS} WHERE EMAIL='vbrrsg@gmail.com')
    """)
    load_users.clear()


# ── TARIFAS ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def load_tarifas():
    return _query(f"SELECT * FROM {T_TARIFAS} ORDER BY FAMILIA, DENSIDAD")


def save_tarifas_from_df(df):
    """Reemplaza todas las tarifas desde un DataFrame."""
    _exec(f"TRUNCATE TABLE {T_TARIFAS}")
    batch = []
    for _, r in df.iterrows():
        familia = _esc(r.get("FAMILIA", ""))
        articulo = _esc(r.get("ARTICULO", ""))
        mp = _esc(r.get("MATERIA_PRIMA", ""))
        dens = r.get("DENSIDAD", 0) or 0
        lam = r.get("LAMBDA", 0) or 0
        pv = r.get("PRECIO_VILAFRANCA", 0) or 0
        pva = r.get("PRECIO_VALENCIA", 0) or 0
        pvl = r.get("PRECIO_VALLADOLID", 0) or 0
        batch.append(
            f"('{familia}', '{articulo}', '{mp}', {dens}, {lam}, {pv}, {pva}, {pvl}, CURRENT_TIMESTAMP())"
        )
        if len(batch) >= 100:
            _exec(f"""INSERT INTO {T_TARIFAS}
                (FAMILIA, ARTICULO, MATERIA_PRIMA, DENSIDAD, LAMBDA,
                 PRECIO_VILAFRANCA, PRECIO_VALENCIA, PRECIO_VALLADOLID, UPDATED_AT)
                VALUES {', '.join(batch)}""")
            batch = []
    if batch:
        _exec(f"""INSERT INTO {T_TARIFAS}
            (FAMILIA, ARTICULO, MATERIA_PRIMA, DENSIDAD, LAMBDA,
             PRECIO_VILAFRANCA, PRECIO_VALENCIA, PRECIO_VALLADOLID, UPDATED_AT)
            VALUES {', '.join(batch)}""")
    load_tarifas.clear()


def get_tarifa(familia, articulo, planta):
    """Devuelve precio €/m³ para una familia+artículo+planta."""
    df = load_tarifas()
    match = df[(df["FAMILIA"] == familia) & (df["ARTICULO"] == articulo)]
    if match.empty:
        return 0.0
    row = match.iloc[0]
    col_map = {
        "Vilafranca": "PRECIO_VILAFRANCA",
        "Valencia": "PRECIO_VALENCIA",
        "Valladolid": "PRECIO_VALLADOLID",
    }
    col = col_map.get(planta, "PRECIO_VILAFRANCA")
    return float(row.get(col, 0) or 0)


def get_articulos_familia(familia):
    """Devuelve lista de artículos disponibles para una familia."""
    df = load_tarifas()
    arts = df[df["FAMILIA"] == familia]["ARTICULO"].unique().tolist()
    return sorted(arts)


def get_densidades_familia(familia):
    """Devuelve densidades disponibles para una familia."""
    df = load_tarifas()
    return sorted(df[df["FAMILIA"] == familia]["DENSIDAD"].unique().tolist())


def get_familias_por_materia(materia_prima):
    """Devuelve familias disponibles para un tipo de materia prima."""
    df = load_tarifas()
    return sorted(df[df["MATERIA_PRIMA"] == materia_prima]["FAMILIA"].unique().tolist())


# ── CLIENTES ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def load_clientes():
    return _query(f"SELECT * FROM {T_CLIENTES} ORDER BY EMPRESA")


def save_clientes_from_df(df):
    """Reemplaza clientes desde un DataFrame de Excel."""
    _exec(f"TRUNCATE TABLE {T_CLIENTES}")
    batch = []
    for _, r in df.iterrows():
        empresa = _esc(r.get("EMPRESA", r.get("Empresa", r.get("empresa", ""))))
        if not empresa or empresa == "nan":
            continue
        cif = _esc(r.get("CIF", r.get("Cif", "")))
        nombre = _esc(r.get("CONTACTO_NOMBRE", r.get("Nombre", r.get("NOMBRE", ""))))
        apellido = _esc(r.get("CONTACTO_APELLIDO", r.get("Apellido", r.get("APELLIDO", ""))))
        email = _esc(r.get("EMAIL", r.get("Email", r.get("email", ""))))
        tel = _esc(r.get("TELEFONO", r.get("Telefono", "")))
        movil = _esc(r.get("MOVIL", r.get("Movil", "")))
        direccion = _esc(r.get("DIRECCION", r.get("Direccion", "")))
        cp = _esc(r.get("CP_CIUDAD", r.get("CP", "")))
        comercial = _esc(r.get("COMERCIAL_ASIGNADO", r.get("Comercial", "")))
        mercado = _esc(r.get("MERCADO", r.get("Mercado", "")))
        batch.append(
            f"('{empresa}', '{cif}', '{nombre}', '{apellido}', '{email}', "
            f"'{tel}', '{movil}', '{direccion}', '{cp}', '{comercial}', '{mercado}', CURRENT_TIMESTAMP())"
        )
        if len(batch) >= 100:
            _exec(f"""INSERT INTO {T_CLIENTES}
                (EMPRESA, CIF, CONTACTO_NOMBRE, CONTACTO_APELLIDO, EMAIL,
                 TELEFONO, MOVIL, DIRECCION, CP_CIUDAD, COMERCIAL_ASIGNADO, MERCADO, UPDATED_AT)
                VALUES {', '.join(batch)}""")
            batch = []
    if batch:
        _exec(f"""INSERT INTO {T_CLIENTES}
            (EMPRESA, CIF, CONTACTO_NOMBRE, CONTACTO_APELLIDO, EMAIL,
             TELEFONO, MOVIL, DIRECCION, CP_CIUDAD, COMERCIAL_ASIGNADO, MERCADO, UPDATED_AT)
            VALUES {', '.join(batch)}""")
    load_clientes.clear()


def buscar_cliente(texto):
    """Busca clientes por nombre de empresa (parcial)."""
    df = load_clientes()
    if df.empty:
        return pd.DataFrame()
    mask = df["EMPRESA"].str.contains(texto.upper(), case=False, na=False)
    return df[mask].head(20)


# ── TRANSPORTE ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def load_transporte():
    return _query(f"SELECT * FROM {T_TRANSPORTE} ORDER BY PLANTA")


def save_transporte(planta, coste_m3, coste_grupaje_m3):
    _exec(f"""
        MERGE INTO {T_TRANSPORTE} t USING (SELECT '{_esc(planta)}' AS PLANTA) s ON t.PLANTA = s.PLANTA
        WHEN MATCHED THEN UPDATE SET COSTE_M3 = {coste_m3}, COSTE_GRUPAJE_M3 = {coste_grupaje_m3}, UPDATED_AT = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (PLANTA, COSTE_M3, COSTE_GRUPAJE_M3) VALUES ('{_esc(planta)}', {coste_m3}, {coste_grupaje_m3})
    """)
    load_transporte.clear()


def get_coste_transporte(planta):
    """Devuelve (coste_m3, coste_grupaje_m3) para una planta."""
    df = load_transporte()
    match = df[df["PLANTA"] == planta]
    if match.empty:
        return (0.0, 0.0)
    row = match.iloc[0]
    return (float(row.get("COSTE_M3", 0) or 0), float(row.get("COSTE_GRUPAJE_M3", 0) or 0))


# ── MATERIAS PRIMAS ───────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def load_materias_primas():
    return _query(f"SELECT * FROM {T_MATERIAS} ORDER BY TIPO")


def save_materia_prima(tipo, precio_kg):
    _exec(f"""
        MERGE INTO {T_MATERIAS} t USING (SELECT '{_esc(tipo)}' AS TIPO) s ON t.TIPO = s.TIPO
        WHEN MATCHED THEN UPDATE SET PRECIO_BASE_KG = {precio_kg}, UPDATED_AT = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (TIPO, PRECIO_BASE_KG) VALUES ('{_esc(tipo)}', {precio_kg})
    """)
    load_materias_primas.clear()


# ── LOGISTICA ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def load_logistica():
    return _query(f"SELECT * FROM {T_LOGISTICA} ORDER BY PRODUCTO, DIMENSION, ESPESOR")


def save_logistica_from_df(df):
    _exec(f"TRUNCATE TABLE {T_LOGISTICA}")
    batch = []
    for _, r in df.iterrows():
        batch.append(
            f"('{_esc(r['PRODUCTO'])}', '{_esc(r.get('DIMENSION',''))}', "
            f"{r.get('ESPESOR',0) or 0}, {r.get('PZAS_PAQUETE',0) or 0}, "
            f"{r.get('PZAS_BLOQUE',0) or 0})"
        )
        if len(batch) >= 100:
            _exec(f"INSERT INTO {T_LOGISTICA} VALUES {', '.join(batch)}")
            batch = []
    if batch:
        _exec(f"INSERT INTO {T_LOGISTICA} VALUES {', '.join(batch)}")
    load_logistica.clear()


def get_logistica_row(producto, dimension, espesor):
    df = load_logistica()
    flt = df[
        (df["PRODUCTO"] == producto) &
        (df["DIMENSION"] == (dimension or "")) &
        (df["ESPESOR"] == float(espesor))
    ]
    if flt.empty:
        return (0, 0)
    row = flt.iloc[0]
    return (int(row["PZAS_PAQUETE"]), int(row["PZAS_BLOQUE"]))


# ── PLANTAS ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def load_plantas():
    return _query(f"SELECT * FROM {T_PLANTAS} ORDER BY PLANTA")


def get_planta(nombre):
    df = load_plantas()
    match = df[df["PLANTA"] == nombre]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


# ── OFERTAS ───────────────────────────────────────────────────────────────────

def next_oferta_number():
    hoy = datetime.now()
    prefix = f"ODP-{hoy.strftime('%y%m%d')}-"
    cnt = int(get_config("contador_ofertas", "0")) + 1
    set_config("contador_ofertas", str(cnt))
    return f"{prefix}{cnt:06d}"


def save_oferta(oferta_dict, lineas_df):
    cols = list(oferta_dict.keys())
    vals = []
    for c in cols:
        v = oferta_dict[c]
        if v is None:
            vals.append("NULL")
        elif isinstance(v, (int, float)):
            vals.append(str(v))
        elif isinstance(v, (date, datetime)):
            vals.append(f"'{v}'")
        else:
            vals.append(f"'{_esc(v)}'")
    col_str = ", ".join(cols)
    val_str = ", ".join(vals)
    _exec(f"INSERT INTO {T_OFERTAS} ({col_str}) VALUES ({val_str})")

    id_df = _query(f"SELECT MAX(ID) AS ID FROM {T_OFERTAS}")
    oferta_id = int(id_df.iloc[0]["ID"])

    batch = []
    for _, ln in lineas_df.iterrows():
        batch.append(
            f"({oferta_id}, "
            f"'{_esc(ln.get('CODIGO_ARTICULO',''))}', "
            f"'{_esc(ln.get('DESCRIPCION',''))}', "
            f"'{_esc(ln.get('TIPO_PRODUCTO',''))}', "
            f"'{_esc(ln.get('CALIDAD',''))}', "
            f"'{_esc(ln.get('DIMENSION',''))}', "
            f"{ln.get('ESPESOR',0) or 0}, "
            f"{ln.get('CANTIDAD',0) or 0}, "
            f"{ln.get('PRECIO_M3',0) or 0}, "
            f"{ln.get('M3_PIEZA',0) or 0}, "
            f"{ln.get('PRECIO_UNITARIO',0) or 0}, "
            f"{ln.get('IMPUESTO_PLASTICO',0) or 0}, "
            f"{ln.get('TOTAL_LINEA',0) or 0})"
        )
    if batch:
        _exec(f"""INSERT INTO {T_LINEAS}
            (OFERTA_ID, CODIGO_ARTICULO, DESCRIPCION, TIPO_PRODUCTO, CALIDAD,
             DIMENSION, ESPESOR, CANTIDAD, PRECIO_M3, M3_PIEZA,
             PRECIO_UNITARIO, IMPUESTO_PLASTICO, TOTAL_LINEA)
            VALUES {', '.join(batch)}""")
    return oferta_id


def load_ofertas(comercial=None):
    if comercial:
        return _query(f"SELECT * FROM {T_OFERTAS} WHERE COMERCIAL = '{_esc(comercial)}' ORDER BY CREATED_AT DESC")
    return _query(f"SELECT * FROM {T_OFERTAS} ORDER BY CREATED_AT DESC")


def load_oferta_lineas(oferta_id):
    return _query(f"SELECT * FROM {T_LINEAS} WHERE OFERTA_ID = {oferta_id} ORDER BY ID")


def load_oferta_detail(oferta_id):
    of = _query(f"SELECT * FROM {T_OFERTAS} WHERE ID = {oferta_id}")
    ln = load_oferta_lineas(oferta_id)
    if of.empty:
        return None, None
    return of.iloc[0].to_dict(), ln


def get_max_revision(numero_oferta_base):
    df = _query(f"SELECT MAX(REVISION) AS MAX_REV FROM {T_OFERTAS} WHERE NUMERO_OFERTA = '{_esc(numero_oferta_base)}'")
    if df.empty or df.iloc[0]["MAX_REV"] is None:
        return 0
    return int(df.iloc[0]["MAX_REV"])

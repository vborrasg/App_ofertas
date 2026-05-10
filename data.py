"""
data.py — Capa de datos Snowflake para App Ofertas.
Usa snowflake-connector-python (mismo patrón que Forecast).
"""
import streamlit as st
import pandas as pd
import math
from datetime import datetime, date

# ── Tablas ────────────────────────────────────────────────────────────────────
SCHEMA = "OFERTAS_DB.APP"
T_PRECIOS    = f"{SCHEMA}.PRECIOS"
T_LOGISTICA  = f"{SCHEMA}.LOGISTICA"
T_PLANTAS    = f"{SCHEMA}.PLANTAS"
T_CALIDADES  = f"{SCHEMA}.CALIDADES"
T_OFERTAS    = f"{SCHEMA}.OFERTAS"
T_LINEAS     = f"{SCHEMA}.OFERTA_LINEAS"
T_USUARIOS   = f"{SCHEMA}.USUARIOS"
T_CONFIG     = f"{SCHEMA}.CONFIG"

GRUPOS_COMPRA = [
    "MINIMO_M3", "BIGMAT", "GAMMA", "DAVSA",
    "EMCCAT", "ESTRATEGIAS_BIGMAT", "IBRICKS", "IDAPLAC"
]


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

    # Mantener admin
    _exec(f"""
        INSERT INTO {T_USUARIOS} (EMAIL, PASSWORD, NOMBRE, ROL)
        SELECT 'vbrrsg@gmail.com','Albope5@','Victor Borrás','admin'
        WHERE NOT EXISTS (SELECT 1 FROM {T_USUARIOS} WHERE EMAIL='vbrrsg@gmail.com')
    """)
    load_users.clear()


# ── PRECIOS ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def load_precios():
    return _query(f"SELECT * FROM {T_PRECIOS} ORDER BY PRODUCTO, CALIDAD")


def save_precios_from_df(df):
    _exec(f"TRUNCATE TABLE {T_PRECIOS}")
    batch = []
    for _, r in df.iterrows():
        vals = (
            f"'{_esc(r['PRODUCTO'])}', '{_esc(r['CALIDAD'])}', "
            f"{r.get('MINIMO_M3',0) or 0}, {r.get('BIGMAT',0) or 0}, "
            f"{r.get('GAMMA',0) or 0}, {r.get('DAVSA',0) or 0}, "
            f"{r.get('EMCCAT',0) or 0}, {r.get('ESTRATEGIAS_BIGMAT',0) or 0}, "
            f"{r.get('IBRICKS',0) or 0}, {r.get('IDAPLAC',0) or 0}"
        )
        batch.append(f"({vals})")
        if len(batch) >= 100:
            _exec(f"INSERT INTO {T_PRECIOS} VALUES {', '.join(batch)}")
            batch = []
    if batch:
        _exec(f"INSERT INTO {T_PRECIOS} VALUES {', '.join(batch)}")
    load_precios.clear()


def get_precio_m3(producto, calidad, grupo_compra):
    df = load_precios()
    match = df[(df["PRODUCTO"] == producto) & (df["CALIDAD"] == calidad)]
    if match.empty:
        return 0.0
    row = match.iloc[0]
    col = grupo_compra.upper().replace(" ", "_") if grupo_compra else "MINIMO_M3"
    if col not in row.index:
        col = "MINIMO_M3"
    precio = float(row[col]) if row[col] else 0.0
    if col == "MINIMO_M3":
        inc = float(get_config("incremento_no_grupo", "0") or 0)
        precio += inc
    return precio


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


# ── CALIDADES ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def load_calidades():
    return _query(f"SELECT * FROM {T_CALIDADES} ORDER BY PRODUCTO, CALIDAD")


def get_calidades_producto(producto):
    df = load_calidades()
    return sorted(df[df["PRODUCTO"] == producto]["CALIDAD"].unique().tolist())


def save_calidades_from_df(df):
    _exec(f"TRUNCATE TABLE {T_CALIDADES}")
    batch = []
    for _, r in df.iterrows():
        batch.append(f"('{_esc(r['PRODUCTO'])}', '{_esc(r['CALIDAD'])}')")
        if len(batch) >= 100:
            _exec(f"INSERT INTO {T_CALIDADES} VALUES {', '.join(batch)}")
            batch = []
    if batch:
        _exec(f"INSERT INTO {T_CALIDADES} VALUES {', '.join(batch)}")
    load_calidades.clear()


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

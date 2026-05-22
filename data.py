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
    "KTM ETIX": ["ETIX.EPS"],
    "KTM ETIX Grafit": ["ETIX.GRAFITO"],
}

TIPOS_MATERIA_PRIMA = ["EPS_Blanco", "EPS_Grafito", "EPS_SOSTENIBLES"]

PLANTAS = ["Vilafranca", "Valencia", "Valladolid"]


# ── Conexión Snowflake ────────────────────────────────────────────────────────

def run_db_migrations(conn):
    """Ejecuta migraciones silenciosas para asegurar que las columnas necesarias existen en la base de datos."""
    import os
    import pandas as pd
    try:
        cur = conn.cursor()
        
        # 1. Columnas faltantes en OFERTAS
        cols = [
            "COMERCIAL_NOMBRE VARCHAR", "CLIENTE_CIF VARCHAR", "CLIENTE_CONTACTO VARCHAR",
            "CLIENTE_EMAIL VARCHAR", "CLIENTE_TELEFONO VARCHAR", "CLIENTE_DIRECCION VARCHAR",
            "PROYECTO_OBRA VARCHAR", "GRUPO_COMPRA VARCHAR"
        ]
        for col in cols:
            try:
                cur.execute(f"ALTER TABLE OFERTAS ADD COLUMN {col}")
            except Exception:
                pass # Ignorar si ya existe o no tiene permisos

        # 2. Columna faltante en TRANSPORTE
        try:
            cur.execute("ALTER TABLE TRANSPORTE ADD COLUMN MINIMO_TRANSPORTE FLOAT")
        except Exception:
            pass

        # 3. Crear tabla PRECIOS_GRUPOS_COMPRA si no existe
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS PRECIOS_GRUPOS_COMPRA (
                    ID NUMBER AUTOINCREMENT PRIMARY KEY,
                    ARTICULO VARCHAR(100) NOT NULL,
                    CALIDAD VARCHAR(150) NOT NULL,
                    GRUPO_COMPRA VARCHAR(100) NOT NULL,
                    PRECIO FLOAT,
                    UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
                )
            """)
            try:
                cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON PRECIOS_GRUPOS_COMPRA TO USER FORECAST_APP")
            except Exception:
                pass
        except Exception:
            pass

        # 4. Si la tabla PRECIOS_GRUPOS_COMPRA está vacía, cargar desde Excel
        try:
            cur.execute("SELECT COUNT(*) AS CNT FROM PRECIOS_GRUPOS_COMPRA")
            count_val = int(cur.fetchone()[0])
        except Exception:
            count_val = 0

        if count_val == 0:
            excel_path = os.path.join(os.path.dirname(__file__), "Precios grupos de compra_revisado_vbg.xlsx")
            if not os.path.exists(excel_path):
                excel_path = os.path.join(os.path.dirname(__file__), "../Precios grupos de compra_revisado_vbg.xlsx")
            
            if os.path.exists(excel_path):
                df_gp = pd.read_excel(excel_path, sheet_name="Hoja1")
                grupos = ["BIG MAT", "ESTRAT. BIG MAT", "EMCCAT", "GRUP GAMMA", "IDAPLAC", "DAVSA", "GRUP IBRICKS"]
                batch = []
                for _, r in df_gp.iterrows():
                    articulo = str(r.get("ARTÍCULO", r.get("ARTICULO", ""))).strip()
                    calidad = str(r.get("CALIDAD", "")).strip()
                    if not articulo or not calidad:
                        continue
                    
                    for grupo in grupos:
                        if grupo in df_gp.columns:
                            val = r[grupo]
                            if pd.isna(val) or str(val).strip() == "*":
                                precio_val = "NULL"
                            else:
                                try:
                                    precio_val = str(float(val))
                                except ValueError:
                                    precio_val = "NULL"
                            
                            art_esc = articulo.replace("'", "''")
                            cal_esc = calidad.replace("'", "''")
                            grp_esc = grupo.replace("'", "''")
                            batch.append(f"('{art_esc}', '{cal_esc}', '{grp_esc}', {precio_val})")
                
                if batch:
                    cur.execute("TRUNCATE TABLE PRECIOS_GRUPOS_COMPRA")
                    sql_gp = f"INSERT INTO PRECIOS_GRUPOS_COMPRA (ARTICULO, CALIDAD, GRUPO_COMPRA, PRECIO) VALUES {', '.join(batch)}"
                    cur.execute(sql_gp)
        cur.close()
    except Exception as e:
        print(f"Error en run_db_migrations: {e}")


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
        
        # Ejecutar migraciones una sola vez por sesión
        if not st.session_state.get('_db_migrated', False):
            try:
                run_db_migrations(conn)
                st.session_state['_db_migrated'] = True
            except Exception as em:
                print(f"Error al ejecutar migraciones en la app: {em}")
                
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


def save_transporte(planta, coste_m3, coste_grupaje_m3, minimo_transporte=0):
    _exec(f"""
        MERGE INTO {T_TRANSPORTE} t USING (SELECT '{_esc(planta)}' AS PLANTA) s ON t.PLANTA = s.PLANTA
        WHEN MATCHED THEN UPDATE SET COSTE_M3 = {coste_m3}, COSTE_GRUPAJE_M3 = {coste_grupaje_m3}, MINIMO_TRANSPORTE = {minimo_transporte}, UPDATED_AT = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (PLANTA, COSTE_M3, COSTE_GRUPAJE_M3, MINIMO_TRANSPORTE) VALUES ('{_esc(planta)}', {coste_m3}, {coste_grupaje_m3}, {minimo_transporte})
    """)
    load_transporte.clear()


def get_coste_transporte(planta):
    """Devuelve (coste_m3, coste_grupaje_m3, minimo_transporte) para una planta."""
    df = load_transporte()
    match = df[df["PLANTA"] == planta]
    if match.empty:
        return (0.0, 0.0, 0.0)
    row = match.iloc[0]
    return (
        float(row.get("COSTE_M3", 0) or 0),
        float(row.get("COSTE_GRUPAJE_M3", 0) or 0),
        float(row.get("MINIMO_TRANSPORTE", 0) or 0),
    )


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
    of_copy = oferta_dict.copy()

    # Obtener las columnas reales en Snowflake para evitar errores de compilación
    columnas_reales = set()
    try:
        desc_df = _query(f"SELECT * FROM {T_OFERTAS} WHERE 1=0")
        if not desc_df.empty or len(desc_df.columns) > 0:
            columnas_reales = set(desc_df.columns)
    except Exception as e:
        print(f"Error al describir columnas de {T_OFERTAS}: {e}")
    
    # Fallback de columnas si la base de datos no responde o retorna vacío
    if not columnas_reales:
        columnas_reales = {
            'ID', 'NUMERO_OFERTA', 'REVISION', 'COMERCIAL', 'FECHA', 'VALIDEZ', 'GRUPO_COMPRA', 
            'PLANTA', 'CLIENTE_NOMBRE', 'CLIENTE_RAZON_SOCIAL', 'CLIENTE_DIRECCION', 'CLIENTE_CP_CIUDAD', 
            'CLIENTE_NIF', 'CLIENTE_CONTACTO', 'CLIENTE_TELEFONO', 'CLIENTE_EMAIL', 'FORMA_ENTREGA', 
            'PLAZO_ENTREGA', 'CONDICIONES_PAGO', 'PLAZO_PAGO', 'OBSERVACIONES', 'SUBTOTAL', 
            'COSTE_TRANSPORTE', 'IMPUESTO_PLASTICO', 'DESCUENTO_PCTG', 'TOTAL', 'ESTADO', 'CREATED_AT', 
            'COMERCIAL_NOMBRE', 'CLIENTE_CIF', 'PORTES', 'IMPUESTO_PLASTICO_TOTAL', 'DESCUENTO_VALOR', 
            'FECHA_VALIDEZ', 'CONDICIONES_TRANSPORTE', 'TIPO_PRECIO'
        }

    # Si pudimos leer las columnas reales, limpiamos las no existentes
    if columnas_reales:
        obs_extras = []
        for col in list(of_copy.keys()):
            if col not in columnas_reales:
                val = of_copy.pop(col)
                if val and str(val).strip():
                    if col == "PROYECTO_OBRA":
                        obs_extras.append(f"[Proyecto/Obra: {str(val).strip()}]")
                    elif col == "GRUPO_COMPRA":
                        obs_extras.append(f"[Grupo Compra: {str(val).strip()}]")
                    elif col == "COMERCIAL_NOMBRE":
                        obs_extras.append(f"[Nombre Comercial: {str(val).strip()}]")
                    elif col.startswith("CLIENTE_"):
                        label = col.replace("CLIENTE_", "").capitalize()
                        obs_extras.append(f"[Cliente {label}: {str(val).strip()}]")
                    else:
                        obs_extras.append(f"[{col}: {str(val).strip()}]")
        
        if obs_extras:
            obs_actual = of_copy.get("OBSERVACIONES", "") or ""
            linea_adicional = "\n".join(obs_extras)
            if obs_actual:
                of_copy["OBSERVACIONES"] = f"{linea_adicional}\n{obs_actual}"
            else:
                of_copy["OBSERVACIONES"] = linea_adicional

    cols = list(of_copy.keys())
    vals = []
    for c in cols:
        v = of_copy[c]
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

    # Obtener el ID de la oferta recién insertada de manera totalmente segura y thread-safe.
    # Evitamos usar MAX(ID) ya que Snowflake no garantiza secuencias continuas/monótonas y
    # puede retornar IDs inconsistentes si hay múltiples inserciones o problemas de caché de secuencias.
    numero_oferta = of_copy.get("NUMERO_OFERTA") or oferta_dict.get("NUMERO_OFERTA")
    revision = of_copy.get("REVISION") if of_copy.get("REVISION") is not None else oferta_dict.get("REVISION", 0)
    
    id_df = pd.DataFrame()
    if numero_oferta:
        id_df = _query(f"SELECT ID FROM {T_OFERTAS} WHERE NUMERO_OFERTA = '{_esc(numero_oferta)}' AND REVISION = {int(revision)}")
        
    if id_df.empty:
        # Fallback de de emergencia a MAX(ID) por compatibilidad
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


def update_oferta_estado(oferta_id, nuevo_estado):
    """Actualiza el estado de una oferta (Borrador, Pendiente Validación, Validada, Rechazada)."""
    _exec(f"UPDATE {T_OFERTAS} SET ESTADO = '{_esc(nuevo_estado)}' WHERE ID = {int(oferta_id)}")
    st.cache_data.clear()


def load_ofertas_pendientes():
    """Devuelve las ofertas pendientes de validación (sin scrap)."""
    return _query(f"SELECT * FROM {T_OFERTAS} WHERE ESTADO = 'Pendiente Validación' ORDER BY CREATED_AT DESC")


def send_validation_email(oferta_dict):
    """Envía un email al aprobador cuando se crea una oferta SIN scrap."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import sys

    approver_email = "victor.borras@knauf.com"

    try:
        smtp_user = st.secrets["SMTP_USER"]
        smtp_pass = st.secrets["SMTP_PASSWORD"]
        smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(st.secrets.get("SMTP_PORT", "587"))
    except Exception:
        print(f"[DEV] Email validación para {approver_email} — Oferta {oferta_dict.get('NUMERO_OFERTA', '?')}", file=sys.stderr)
        return False

    try:
        numero = oferta_dict.get("NUMERO_OFERTA", "?")
        cliente = oferta_dict.get("CLIENTE_NOMBRE", "?")
        comercial = oferta_dict.get("COMERCIAL_NOMBRE", "?")
        total = oferta_dict.get("TOTAL", 0)

        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = approver_email
        msg["Subject"] = f"🔔 Validación requerida — Oferta {numero} (SIN Scrap)"
        body = f"""
        <html><body style="font-family:Arial;padding:20px;">
        <h2 style="color:#c0392b;">⚠️ Oferta SIN Scrap pendiente de validación</h2>
        <table style="border-collapse:collapse;width:100%;max-width:500px;">
            <tr><td style="padding:8px;font-weight:bold;background:#f8f9fa;">Nº Oferta</td>
                <td style="padding:8px;">{numero}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;background:#f8f9fa;">Cliente</td>
                <td style="padding:8px;">{cliente}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;background:#f8f9fa;">Comercial</td>
                <td style="padding:8px;">{comercial}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;background:#f8f9fa;">Total</td>
                <td style="padding:8px;font-weight:bold;color:#c0392b;">{total:,.2f} €</td></tr>
            <tr><td style="padding:8px;font-weight:bold;background:#f8f9fa;">Tipo de precio</td>
                <td style="padding:8px;color:#c0392b;font-weight:bold;">SIN SCRAP</td></tr>
        </table>
        <p style="margin-top:20px;">Accede a la aplicación para validar o rechazar esta oferta.</p>
        <hr><p style="color:#888;font-size:12px;">App Ofertas — KTM</p>
        </body></html>
        """
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[ERROR SMTP validación] {e}", file=sys.stderr)
        return False


# ── GRUPOS DE COMPRA (PANDAS CACHED LOADER) ───────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def load_precios_grupos():
    """Carga y normaliza el Excel de precios de grupos de compra."""
    import os
    import pandas as pd
    excel_path = os.path.join(os.path.dirname(__file__), "Precios grupos de compra_revisado_vbg.xlsx")
    if not os.path.exists(excel_path):
        return pd.DataFrame()
    try:
        df = pd.read_excel(excel_path, sheet_name="Hoja1")
        # Limpiar columnas
        df.columns = [c.strip() for c in df.columns]
        # Normalizar ARTÍCULO y CALIDAD
        df["ARTÍCULO"] = df["ARTÍCULO"].astype(str).str.strip().str.upper()
        df["CALIDAD"] = df["CALIDAD"].astype(str).str.strip()
        
        # Reemplazar '*' y valores no numéricos por None en las columnas de grupo
        grupos = ["BIG MAT", "ESTRAT. BIG MAT", "EMCCAT", "GRUP GAMMA", "IDAPLAC", "DAVSA", "GRUP IBRICKS"]
        for g in grupos:
            if g in df.columns:
                df[g] = df[g].apply(lambda x: None if str(x).strip() == "*" or pd.isna(x) else float(str(x).replace(",", ".")))
        return df
    except Exception as e:
        import sys
        print(f"[ERROR load_precios_grupos] {e}", file=sys.stderr)
        return pd.DataFrame()


def get_productos_grupo(grupo):
    """Devuelve los artículos únicos que tienen un precio válido para el grupo seleccionado."""
    if grupo == "Ninguno":
        return []
    df = load_precios_grupos()
    if df.empty or grupo not in df.columns:
        return []
    
    # Filtrar filas donde el precio para este grupo no sea nulo/None
    df_filtered = df[df[grupo].notna()]
    return sorted(df_filtered["ARTÍCULO"].unique().tolist())


def get_calidades_producto_grupo(grupo, producto):
    """Devuelve las calidades únicas para un artículo que tienen precio válido para el grupo."""
    if grupo == "Ninguno":
        return []
    df = load_precios_grupos()
    if df.empty or grupo not in df.columns:
        return []
    
    df_filtered = df[(df["ARTÍCULO"] == producto.upper()) & (df[grupo].notna())]
    return sorted(df_filtered["CALIDAD"].unique().tolist())


def get_precio_grupo(grupo, producto, calidad):
    """Devuelve el precio float para un grupo, producto y calidad. Retorna None si no hay precio."""
    if grupo == "Ninguno":
        return None
    df = load_precios_grupos()
    if df.empty or grupo not in df.columns:
        return None
    
    match = df[(df["ARTÍCULO"] == producto.upper()) & (df["CALIDAD"] == calidad)]
    if match.empty:
        return None
    
    val = match.iloc[0][grupo]
    if pd.isna(val):
        return None
    return float(val)


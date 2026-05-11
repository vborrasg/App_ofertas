import snowflake.connector
import toml
import os

def fix():
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit/secrets.toml")
    with open(secrets_path, "r") as f:
        config = toml.load(f)

    print("Conectando a Snowflake para reparar tablas...")
    ctx = snowflake.connector.connect(
        user=config["SNOWFLAKE_USER"],
        password=config["SNOWFLAKE_PASSWORD"],
        account=config["SNOWFLAKE_ACCOUNT"],
        warehouse=config["SNOWFLAKE_WAREHOUSE"],
        database=config["SNOWFLAKE_DATABASE"],
        schema=config["SNOWFLAKE_SCHEMA"]
    )
    cs = ctx.cursor()
    try:
        # ── 1. Columnas faltantes en OFERTAS ──
        cols = [
            "COMERCIAL_NOMBRE VARCHAR", "CLIENTE_CIF VARCHAR", "CLIENTE_CONTACTO VARCHAR",
            "CLIENTE_EMAIL VARCHAR", "CLIENTE_TELEFONO VARCHAR", "CLIENTE_DIRECCION VARCHAR"
        ]
        for col in cols:
            try:
                cs.execute(f"ALTER TABLE OFERTAS ADD COLUMN {col}")
                print(f"✅ Columna añadida: {col}")
            except Exception as e:
                print(f"ℹ️ {col.split()[0]}: ya existe o error menor")

        # ── 1b. Añadir MINIMO_TRANSPORTE a TRANSPORTE ──
        print("\nActualizando tabla TRANSPORTE...")
        try:
            cs.execute("ALTER TABLE TRANSPORTE ADD COLUMN MINIMO_TRANSPORTE FLOAT")
            print("✅ Columna MINIMO_TRANSPORTE añadida")
        except Exception as e:
            print(f"ℹ️ MINIMO_TRANSPORTE: {e}")

        # Valores iniciales (solo si la columna existe)
        for planta, minimo in [("Vilafranca", 110), ("Valencia", 140), ("Valladolid", 150)]:
            try:
                cs.execute(f"""
                    MERGE INTO TRANSPORTE t USING (SELECT '{planta}' AS PLANTA) s ON t.PLANTA = s.PLANTA
                    WHEN MATCHED AND (t.MINIMO_TRANSPORTE IS NULL OR t.MINIMO_TRANSPORTE = 0)
                        THEN UPDATE SET MINIMO_TRANSPORTE = {minimo}
                    WHEN NOT MATCHED THEN INSERT (PLANTA, COSTE_M3, COSTE_GRUPAJE_M3, MINIMO_TRANSPORTE)
                        VALUES ('{planta}', 0, 0, {minimo})
                """)
                print(f"  ✅ {planta}: mínimo = {minimo}€")
            except Exception as e:
                print(f"  ⚠️ {planta}: {e}")

        # ── 2. Renombrar familias KNAUF_TECK -> ETIX en TARIFAS ──
        print("\nRenombrando familias en TARIFAS...")
        cs.execute("UPDATE TARIFAS SET FAMILIA = 'ETIX.EPS' WHERE FAMILIA = 'KNAUF_TECK.EPS'")
        print(f"  Filas KNAUF_TECK.EPS -> ETIX.EPS: {cs.rowcount}")
        cs.execute("UPDATE TARIFAS SET FAMILIA = 'ETIX.GRAFITO' WHERE FAMILIA = 'ETIX.GRAFITO'")
        print(f"  Filas ETIX.GRAFITO verificadas: {cs.rowcount}")

        # ── 3. Subir múltiplos ETIX (1000x500 y 1000x600) ──
        print("\nSubiendo múltiplos logísticos ETIX...")
        cs.execute("DELETE FROM LOGISTICA WHERE DIMENSION IN ('1000X600', '1000X500')")
        sql = """INSERT INTO LOGISTICA (PRODUCTO, DIMENSION, ESPESOR, PZAS_PAQUETE, PZAS_BLOQUE) VALUES
        ('PLANCHA', '1000X600', 10, 96, 960), ('PLANCHA', '1000X600', 20, 50, 600), ('PLANCHA', '1000X600', 30, 32, 400),
        ('PLANCHA', '1000X600', 40, 24, 300), ('PLANCHA', '1000X600', 50, 20, 240), ('PLANCHA', '1000X600', 60, 16, 200),
        ('PLANCHA', '1000X600', 70, 14, 170), ('PLANCHA', '1000X600', 80, 12, 150), ('PLANCHA', '1000X600', 90, 10, 130),
        ('PLANCHA', '1000X600', 100, 10, 120), ('PLANCHA', '1000X600', 110, 10, 100), ('PLANCHA', '1000X600', 120, 8, 100),
        ('PLANCHA', '1000X600', 140, 6, 80), ('PLANCHA', '1000X600', 150, 6, 80), ('PLANCHA', '1000X600', 160, 6, 70),
        ('PLANCHA', '1000X600', 180, 6, 60), ('PLANCHA', '1000X600', 200, 6, 60), ('PLANCHA', '1000X600', 220, 4, 50),
        ('PLANCHA', '1000X600', 240, 4, 50), ('PLANCHA', '1000X500', 10, 96, 1152), ('PLANCHA', '1000X500', 20, 50, 720),
        ('PLANCHA', '1000X500', 30, 32, 480), ('PLANCHA', '1000X500', 40, 24, 360), ('PLANCHA', '1000X500', 50, 20, 288),
        ('PLANCHA', '1000X500', 60, 16, 240), ('PLANCHA', '1000X500', 70, 14, 204), ('PLANCHA', '1000X500', 80, 12, 180),
        ('PLANCHA', '1000X500', 90, 10, 156), ('PLANCHA', '1000X500', 100, 10, 144), ('PLANCHA', '1000X500', 110, 10, 120),
        ('PLANCHA', '1000X500', 120, 8, 120), ('PLANCHA', '1000X500', 130, 8, 108), ('PLANCHA', '1000X500', 140, 6, 96),
        ('PLANCHA', '1000X500', 150, 6, 96), ('PLANCHA', '1000X500', 160, 6, 84), ('PLANCHA', '1000X500', 170, 6, 84),
        ('PLANCHA', '1000X500', 180, 6, 72), ('PLANCHA', '1000X500', 190, 6, 72), ('PLANCHA', '1000X500', 200, 6, 72),
        ('PLANCHA', '1000X500', 210, 4, 60), ('PLANCHA', '1000X500', 220, 4, 60), ('PLANCHA', '1000X500', 240, 4, 60),
        ('PLANCHA', '1000X500', 250, 4, 48), ('PLANCHA', '1000X500', 280, 4, 48), ('PLANCHA', '1000X500', 300, 4, 48)"""
        cs.execute(sql)
        print(f"✅ Múltiplos ETIX subidos correctamente")

        # ── 4. Subir múltiplos PANEL AISLANTE (2000x1000 y 2000x1200) ──
        print("\nSubiendo múltiplos logísticos PANEL AISLANTE...")
        cs.execute("DELETE FROM LOGISTICA WHERE DIMENSION IN ('2000X1000', '2000X1200')")
        sql2 = """INSERT INTO LOGISTICA (PRODUCTO, DIMENSION, ESPESOR, PZAS_PAQUETE, PZAS_BLOQUE) VALUES
        ('PLANCHA', '2000X1000', 10, 48, 357), ('PLANCHA', '2000X1000', 15, 32, 234),
        ('PLANCHA', '2000X1000', 20, 25, 180), ('PLANCHA', '2000X1000', 25, 20, 144),
        ('PLANCHA', '2000X1000', 30, 16, 120), ('PLANCHA', '2000X1000', 35, 14, 102),
        ('PLANCHA', '2000X1000', 40, 12, 90), ('PLANCHA', '2000X1000', 45, 11, 78),
        ('PLANCHA', '2000X1000', 50, 10, 72), ('PLANCHA', '2000X1000', 60, 8, 60),
        ('PLANCHA', '2000X1000', 70, 7, 51), ('PLANCHA', '2000X1000', 80, 6, 45),
        ('PLANCHA', '2000X1000', 90, 5, 39), ('PLANCHA', '2000X1000', 100, 5, 36),
        ('PLANCHA', '2000X1000', 110, 4, 30), ('PLANCHA', '2000X1000', 120, 4, 30),
        ('PLANCHA', '2000X1000', 130, 3, 27), ('PLANCHA', '2000X1000', 140, 3, 24),
        ('PLANCHA', '2000X1000', 150, 3, 24), ('PLANCHA', '2000X1000', 160, 3, 21),
        ('PLANCHA', '2000X1000', 170, 2, 21), ('PLANCHA', '2000X1000', 180, 2, 18),
        ('PLANCHA', '2000X1000', 190, 2, 18), ('PLANCHA', '2000X1000', 200, 2, 18),
        ('PLANCHA', '2000X1000', 210, 2, 15), ('PLANCHA', '2000X1000', 220, 2, 15),
        ('PLANCHA', '2000X1000', 230, 2, 15), ('PLANCHA', '2000X1000', 240, 2, 15),
        ('PLANCHA', '2000X1000', 250, 2, 12), ('PLANCHA', '2000X1000', 260, 2, 12),
        ('PLANCHA', '2000X1000', 270, 2, 12), ('PLANCHA', '2000X1000', 280, 2, 12),
        ('PLANCHA', '2000X1000', 290, 2, 12), ('PLANCHA', '2000X1000', 300, 2, 12),
        ('PLANCHA', '2000X1200', 10, 48, 240), ('PLANCHA', '2000X1200', 15, 32, 198),
        ('PLANCHA', '2000X1200', 20, 25, 150), ('PLANCHA', '2000X1200', 25, 20, 120),
        ('PLANCHA', '2000X1200', 30, 16, 99), ('PLANCHA', '2000X1200', 35, 14, 84),
        ('PLANCHA', '2000X1200', 40, 12, 75), ('PLANCHA', '2000X1200', 45, 11, 66),
        ('PLANCHA', '2000X1200', 50, 10, 60), ('PLANCHA', '2000X1200', 60, 8, 48),
        ('PLANCHA', '2000X1200', 70, 7, 42), ('PLANCHA', '2000X1200', 80, 6, 36),
        ('PLANCHA', '2000X1200', 90, 5, 33), ('PLANCHA', '2000X1200', 100, 5, 30),
        ('PLANCHA', '2000X1200', 110, 4, 27), ('PLANCHA', '2000X1200', 120, 4, 24),
        ('PLANCHA', '2000X1200', 130, 3, 21), ('PLANCHA', '2000X1200', 140, 3, 21),
        ('PLANCHA', '2000X1200', 150, 3, 18), ('PLANCHA', '2000X1200', 160, 3, 18),
        ('PLANCHA', '2000X1200', 170, 2, 15), ('PLANCHA', '2000X1200', 180, 2, 15),
        ('PLANCHA', '2000X1200', 190, 2, 15), ('PLANCHA', '2000X1200', 200, 2, 15),
        ('PLANCHA', '2000X1200', 210, 2, 12), ('PLANCHA', '2000X1200', 220, 2, 12),
        ('PLANCHA', '2000X1200', 230, 2, 12), ('PLANCHA', '2000X1200', 240, 2, 12),
        ('PLANCHA', '2000X1200', 250, 2, 12), ('PLANCHA', '2000X1200', 260, 2, 9),
        ('PLANCHA', '2000X1200', 270, 2, 9), ('PLANCHA', '2000X1200', 280, 2, 9),
        ('PLANCHA', '2000X1200', 290, 2, 9), ('PLANCHA', '2000X1200', 300, 2, 9)"""
        cs.execute(sql2)
        print(f"✅ Múltiplos PANEL AISLANTE subidos correctamente")

        print("\n✅ Base de datos sincronizada al 100%.")
    finally:
        cs.close()
        ctx.close()

if __name__ == "__main__":
    fix()

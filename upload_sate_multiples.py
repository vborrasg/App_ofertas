import snowflake.connector
import toml
import os

def upload():
    # Cargar credenciales desde el archivo de la app
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit/secrets.toml")
    with open(secrets_path, "r") as f:
        config = toml.load(f)

    print("Conectando a Snowflake...")
    ctx = snowflake.connector.connect(
        user=config["snowflake"]["user"],
        password=config["snowflake"]["password"],
        account=config["snowflake"]["account"],
        warehouse=config["snowflake"]["warehouse"],
        database=config["snowflake"]["database"],
        schema=config["snowflake"]["schema"]
    )
    cs = ctx.cursor()

    try:
        print("Limpiando datos antiguos de SATE...")
        cs.execute("DELETE FROM LOGISTICA WHERE DIMENSION IN ('1000X600', '1000X500')")
        
        print("Insertando nuevos múltiplos...")
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
        print("✅ Múltiplos SATE subidos correctamente.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cs.close()
        ctx.close()

if __name__ == "__main__":
    upload()

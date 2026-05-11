import snowflake.connector
import toml
import os

def fix():
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit/secrets.toml")
    with open(secrets_path, "r") as f:
        config = toml.load(f)

    print("Conectando a Snowflake para reparar tablas...")
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
        cols = [
            "COMERCIAL_NOMBRE VARCHAR", "CLIENTE_CIF VARCHAR", "CLIENTE_CONTACTO VARCHAR",
            "CLIENTE_EMAIL VARCHAR", "CLIENTE_TELEFONO VARCHAR", "CLIENTE_DIRECCION VARCHAR"
        ]
        for col in cols:
            try:
                cs.execute(f"ALTER TABLE OFERTAS ADD COLUMN {col}")
                print(f"✅ Columna añadida/verificada: {col}")
            except Exception as e:
                print(f"ℹ️ {col.split()[0]}: {e}")
        print("✅ Proceso finalizado.")
    finally:
        cs.close()
        ctx.close()

if __name__ == "__main__":
    fix()

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.append(str(Path(__file__).resolve().parent.parent))

from utils.neo4j_conn import get_driver, verificar_conexion

uri = os.getenv("NEO4J_URI")
print(f"URI usado:     {uri}")
print(f"SSL_CERT_FILE: {os.environ.get('SSL_CERT_FILE')}")

user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
if uri is None or user is None or password is None:
    raise RuntimeError("Faltan las variables NEO4J_URI, NEO4J_USER o NEO4J_PASSWORD")

driver = get_driver(uri, user, password)
try:
    verificar_conexion(driver)
    with driver.session() as session:
        n = session.run(
            "MATCH (c:CeldaH3) RETURN count(c) AS n"
        ).single(strict=True)["n"]
    print(f"OK: conectó y leyó datos ({n} celdas H3)")
finally:
    driver.close()
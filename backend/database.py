"""
Conexión a Neo4j para el backend. Lee credenciales del .env que ya existe
en la raíz del proyecto (RedPrimavera/.env), y delega la creación del
driver a utils/neo4j_conn.py -- que ya resuelve el workaround de SSL con
certifi, así que no lo duplicamos aquí.

IMPORTANTE sobre cómo correr esto: para que `from utils.neo4j_conn import
get_driver` funcione, uvicorn debe correr desde la RAÍZ del proyecto
(RedPrimavera/), no desde dentro de backend/. Ver el comando exacto abajo
en el README.
"""

import os

from dotenv import load_dotenv

from utils.neo4j_conn import get_driver as _get_driver

load_dotenv()  # busca .env en el directorio desde donde se corre uvicorn (la raíz)

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

_driver = None


def get_driver():
    """Driver único (singleton) para toda la vida de la aplicación."""
    global _driver
    if _driver is None:
        _driver = _get_driver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    return _driver


def get_session():
    """Dependency de FastAPI: una sesión de Neo4j por request, cerrada al final."""
    driver = get_driver()
    session = driver.session()
    try:
        yield session
    finally:
        session.close()


def cerrar_driver():
    """Se llama al apagar la aplicación (shutdown de FastAPI)."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None

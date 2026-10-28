import os
import certifi
from neo4j import GraphDatabase

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

def get_driver(uri: str, user: str, password: str):
    """Crea el driver de Neo4j respetando el esquema del URI tal cual viene
    (neo4j+s://, neo4j+ssc://, neo4j://, bolt://, ...). No se reescribe ni
    se inyecta configuración TLS manual: el propio esquema decide cifrado
    y verificación de certificado.
    """
    return GraphDatabase.driver(
        uri,
        auth=(user, password),
        max_connection_lifetime=200,   # renueva conexiones con más de ~3 min de vida
        liveness_check_timeout=30,     # si una conexión estuvo quieta >30 s, la prueba antes de usarla
    )

def verificar_conexion(driver) -> None:
    """Confirma que el driver realmente puede autenticar y hablar con Neo4j
    (y, para neo4j+s:///neo4j+ssc://, que el TLS se negoció bien). Útil para
    diagnosticar el error de certificados en vez de asumir que "conecta" ya
    significa "está cifrado y verificado".
    """
    driver.verify_connectivity()
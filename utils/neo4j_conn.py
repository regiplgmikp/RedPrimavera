import os
import certifi
from neo4j import GraphDatabase

os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

def get_driver(uri: str, user: str, password: str):
    """Crea el driver de Neo4j respetando el esquema del URI tal cual viene
    (neo4j+s://, neo4j+ssc://, neo4j://, bolt://, ...). No se reescribe ni
    se inyecta configuración TLS manual: el propio esquema decide cifrado
    y verificación de certificado.
    """
    return GraphDatabase.driver(uri, auth=(user, password))

def verificar_conexion(driver) -> None:
    """Confirma que el driver realmente puede autenticar y hablar con Neo4j
    (y, para neo4j+s:///neo4j+ssc://, que el TLS se negoció bien). Útil para
    diagnosticar el error de certificados en vez de asumir que "conecta" ya
    significa "está cifrado y verificado".
    """
    driver.verify_connectivity()
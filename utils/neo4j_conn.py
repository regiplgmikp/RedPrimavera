import ssl
import certifi
from neo4j import GraphDatabase

def get_driver(uri: str, user: str, password: str):
    # Si la URL viene con neo4j+s:// o neo4j+ssc://, normalizamos a neo4j://
    # para permitir inyectar el ssl_context de certifi sin ConfigurationError
    base_uri = uri.replace("neo4j+s://", "neo4j://").replace("neo4j+ssc://", "neo4j://")
    
    if "databases.neo4j.io" in base_uri or uri.startswith("neo4j+s://"):
        context = ssl.create_default_context(cafile=certifi.where())
        return GraphDatabase.driver(
            base_uri,
            auth=(user, password),
            ssl_context=context
        )
        
    return GraphDatabase.driver(uri, auth=(user, password))
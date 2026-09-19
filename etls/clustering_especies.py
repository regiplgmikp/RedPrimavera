"""
Clustering de especies por co-ocurrencia espacial (red COOCURRE_CON), corrido
localmente con networkx en vez de Aura Graph Analytics (hubo problemás pues aura desactivaba la opción automáticamente, por ello
se recurruó a esto).

Requisitos (en tu venv, ya deberías tener neo4j instalado; falta networkx):
    pip install networkx

Uso:
    python clustering_especies.py \
        --uri neo4j+s://e75ace21.databases.neo4j.io \
        --password TU_PASSWORD
"""

import argparse

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
load_dotenv()

try:
    import networkx as nx
except ImportError:
    raise SystemExit("Falta networkx. Instala con: pip install networkx")


def leer_red_cooccurrencia(driver):
    """Trae todas las relaciones COOCURRE_CON como (especie1, especie2, peso)."""
    query = """
    MATCH (e1:Especie)-[r:COOCURRE_CON]-(e2:Especie)
    WHERE e1.nombre_cientifico < e2.nombre_cientifico
    RETURN e1.nombre_cientifico AS especie1,
           e2.nombre_cientifico AS especie2,
           r.peso AS peso
    """
    with driver.session() as session:
        result = session.run(query)
        return [(r["especie1"], r["especie2"], r["peso"]) for r in result]


def construir_grafo(aristas):
    G = nx.Graph()
    for e1, e2, peso in aristas:
        G.add_edge(e1, e2, weight=peso if peso is not None else 1)
    return G


def correr_louvain(G):
    """
    Louvain nativo de networkx (disponible desde networkx >= 2.8, sin
    necesidad del paquete externo python-louvain). Devuelve una lista de
    sets (comunidades), cada uno con los nombres científicos que quedaron
    agrupados juntos.
    """
    comunidades = nx.community.louvain_communities(G, weight="weight", seed=42)
    modularidad = nx.community.modularity(G, comunidades, weight="weight")
    return comunidades, modularidad


def escribir_clusters(driver, comunidades):
    registros = []
    for cluster_id, especies in enumerate(comunidades):
        for nombre in especies:
            registros.append({"nombre_cientifico": nombre, "cluster_id": cluster_id})

    query = """
    UNWIND $batch AS row
    MATCH (e:Especie {nombre_cientifico: row.nombre_cientifico})
    SET e.cluster_especies = row.cluster_id
    """
    with driver.session() as session:
        session.run(query, batch=registros)
    return len(registros)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    args = parser.parse_args()

    if not args.password:
        raise SystemExit("Error: No se encontró la contraseña en el .env ni en los argumentos.")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    print("Leyendo la red de co-ocurrencia (COOCURRE_CON) desde Neo4j ...")
    aristas = leer_red_cooccurrencia(driver)
    print(f"  {len(aristas)} relaciones leídas")

    print("Construyendo grafo en networkx ...")
    G = construir_grafo(aristas)
    print(f"  {G.number_of_nodes()} nodos (especies), {G.number_of_edges()} aristas")

    print("Corriendo Louvain ...")
    comunidades, modularidad = correr_louvain(G)
    print(f"  {len(comunidades)} clústeres encontrados")
    print(f"  Modularidad: {modularidad:.4f}  (más cerca de 1 = mejor separados)")

    print("\nTamaño de cada clúster:")
    for i, c in enumerate(comunidades):
        print(f"  Clúster {i}: {len(c)} especies")

    print("\nEjemplo del clúster más grande:")
    mayor = max(comunidades, key=len)
    for nombre in list(mayor)[:10]:
        print(f"  - {nombre}")

    print("\nEscribiendo cluster_especies de vuelta a Neo4j ...")
    n = escribir_clusters(driver, comunidades)
    print(f"  {n} nodos Especie actualizados")

    driver.close()
    print("\nListo. En Bloom: categoría Especie -> Rule-based -> cluster_especies -> Unique values")


if __name__ == "__main__":
    main()

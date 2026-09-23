"""Genera el grid H3 completo del Bosque La Primavera y sus adyacencias.

Requisitos:
        - Python con h3, neo4j y python-dotenv instalados.
        - Un GeoJSON de tipo Polygon o MultiPolygon con el limite del bosque.
        - Una instancia de Neo4j accesible y NEO4J_URI, NEO4J_USER y
            NEO4J_PASSWORD en el entorno o en un archivo .env.

Qué hace:
        - Convierte el poligono a celdas H3 para cada resolucion solicitada,
            incluyendo celdas que aun no tienen observaciones.
        - Crea o actualiza nodos CeldaH3 y relaciones ADYACENTE_A entre vecinas
            de la misma resolucion mediante operaciones por lotes.

Notas:
        - El GeoJSON usa coordenadas [longitud, latitud]; el script hace la
            conversion al orden que necesita h3-py.
        - Es idempotente mediante MERGE y puede ejecutarse despues del ETL de
            observaciones para completar el grid sin perder datos existentes.
        - Conviene ejecutarlo antes de etl_gee_ndvi.py y de cargar caminos.
"""

import argparse
import json
import sys
from pathlib import Path
import os
from dotenv import load_dotenv
# Carga las variables del archivo .env a os.environ
load_dotenv()
# Permite importar desde la raíz del proyecto sin importar desde dónde ejecutes el comando
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver
from dotenv import load_dotenv
# Carga las variables del archivo .env a os.environ
load_dotenv()


try:
    import h3
except ImportError:
    sys.exit("Falta h3. Instala con: pip install h3 --break-system-packages")

try:
    from neo4j import GraphDatabase
except ImportError:
    sys.exit("Falta el driver neo4j. Instala con: pip install neo4j --break-system-packages")


BATCH_SIZE = 500


def chunks(lista, tam):
    for i in range(0, len(lista), tam):
        yield lista[i : i + tam]


def cargar_ring_latlon(path_geojson: str):
    """
    Devuelve el anillo exterior del polígono como lista de (lat, lon),
    que es el orden que espera h3.LatLngPoly (h3-py v4), a diferencia de
    GeoJSON que usa (lon, lat).
    """
    with open(path_geojson, "r", encoding="utf-8") as f:
        gj = json.load(f)
    geom = gj["features"][0]["geometry"]
    if geom["type"] == "Polygon":
        ring_lonlat = geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        ring_lonlat = geom["coordinates"][0][0]
    else:
        raise ValueError(f"Tipo de geometría no soportado: {geom['type']}")

    return [(lat, lon) for lon, lat in ring_lonlat]


def generar_celdas(ring_latlon, resolucion: int) -> set:
    """
    Genera el conjunto de celdas H3 que cubren el polígono en la resolución
    dada. Intenta usar polygon_to_cells_experimental con contain='overlap'
    (cubre también celdas que solo tocan el borde, evitando huecos visuales
    en el mapa); si esa función no está disponible en la versión instalada
    de h3-py, cae de vuelta a polygon_to_cells estándar (basado en centroide).
    """
    poly = h3.LatLngPoly(ring_latlon)

    if hasattr(h3, "polygon_to_cells_experimental"):
        try:
            celdas = h3.polygon_to_cells_experimental(poly, resolucion, contain="overlap")
            return set(celdas)
        except Exception as e:
            print(f"  polygon_to_cells_experimental falló ({e}), usando polygon_to_cells estándar")

    celdas = h3.polygon_to_cells(poly, resolucion)
    return set(celdas)


def cargar_celdas_a_neo4j(uri, user, password, celdas: set, resolucion: int):
    driver = get_driver(uri, user, password)
    registros = [{"h3_id": h3_id, "resolucion": resolucion} for h3_id in celdas]

    with driver.session() as session:
        for lote in chunks(registros, BATCH_SIZE):
            session.run(
                """
                UNWIND $batch AS row
                MERGE (c:CeldaH3 {h3_id: row.h3_id, resolucion: row.resolucion})
                """,
                batch=lote,
            )
    driver.close()
    print(f"  {len(registros)} celdas CeldaH3 (resolución {resolucion}) aseguradas en Neo4j")


def generar_adyacencias(uri, user, password, celdas: set, resolucion: int):
    """
    Crea ADYACENTE_A entre cada celda y sus vecinos de anillo k=1 (grid_disk),
    limitado a pares donde ambas celdas pertenecen al grid generado (evita
    crear relaciones hacia celdas fuera del área de interés).
    """
    pares = []
    for h3_id in celdas:
        for vecino in h3.grid_disk(h3_id, 1):
            if vecino != h3_id and vecino in celdas:
                pares.append({"a": h3_id, "b": vecino, "res": resolucion})

    driver = get_driver(uri, user, password)
    with driver.session() as session:
        for lote in chunks(pares, BATCH_SIZE):
            session.run(
                """
                UNWIND $batch AS par
                MATCH (a:CeldaH3 {h3_id: par.a, resolucion: par.res})
                MATCH (b:CeldaH3 {h3_id: par.b, resolucion: par.res})
                MERGE (a)-[:ADYACENTE_A {resolucion: par.res}]->(b)
                """,
                batch=lote,
            )
    driver.close()
    print(f"  {len(pares)} relaciones ADYACENTE_A (resolución {resolucion}) aseguradas")


def resumen_area(celdas: set, resolucion: int):
    area_por_celda_km2 = {
        4: 1770.3, 5: 252.9, 6: 36.1, 7: 5.16,
        8: 0.737, 9: 0.105, 10: 0.0150, 11: 0.00214,
    }.get(resolucion)
    n = len(celdas)
    if area_por_celda_km2:
        print(f"  Resolución {resolucion}: {n} celdas, ~{n * area_por_celda_km2:.1f} km² cubiertos "
              f"(BLP real: ~305 km²)")
    else:
        print(f"  Resolución {resolucion}: {n} celdas")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geojson", required=True, help="GeoJSON del límite del BLP (ej. La_Primavera.geojson)")
    parser.add_argument("--resoluciones", type=int, nargs="+", default=[8, 9])
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    args = parser.parse_args()

    print(f"Cargando polígono desde {args.geojson} ...")
    ring_latlon = cargar_ring_latlon(args.geojson)
    print(f"  {len(ring_latlon)} vértices")

    for res in args.resoluciones:
        print(f"\n--- Resolución {res} ---")
        print("Generando celdas H3 que cubren el polígono ...")
        celdas = generar_celdas(ring_latlon, res)
        resumen_area(celdas, res)

        print("Cargando celdas a Neo4j ...")
        cargar_celdas_a_neo4j(args.uri, args.user, args.password, celdas, res)

        print("Generando relaciones ADYACENTE_A ...")
        generar_adyacencias(args.uri, args.user, args.password, celdas, res)

    print("\nListo. Rejilla H3 completa cargada para todas las resoluciones solicitadas.")
    print("Nota: si ya habías corrido 02_etl_especies_observaciones.py antes, las celdas")
    print("con observaciones ya existentes se conservan intactas (MERGE es idempotente);")
    print("este script solo agrega las celdas y adyacencias que faltaban.")


if __name__ == "__main__":
    main()

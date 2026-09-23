"""Carga especies y observaciones de iNaturalist/Naturalista en Neo4j.

Requisitos:
        - Python con pandas, h3, neo4j y python-dotenv instalados.
        - Un CSV exportado de iNaturalist con sus columnas de observaciones.
        - Una instancia de Neo4j accesible y NEO4J_URI, NEO4J_USER y
            NEO4J_PASSWORD en el entorno o en un archivo .env.
        - Los constraints de schema/schema.cypher creados previamente.

Qué hace:
        - Limpia y filtra las observaciones con calidad "research".
        - Clasifica cada observacion en nucleo, zona_mab o fuera cuando se
            proporcionan los GeoJSON de las zonas.
        - Calcula la celda H3 de cada observacion para las resoluciones solicitadas.
        - Crea o actualiza nodos Especie, Observacion y CeldaH3, junto con las
            relaciones PERTENECE_A y UBICADA_EN, usando cargas por lotes.

Notas:
        - --geojson-blp y --geojson-mab son opcionales; sin ellos no se asigna
            la zona espacial completa.
        - nombre_cientifico identifica a cada Especie y taxon_id queda como
            propiedad para cruces posteriores con catalogos taxonomicos.
        - Es idempotente para los identificadores existentes porque usa MERGE.
"""
import argparse
import json
import sys
from typing import Iterable
import pandas as pd
import os
from pathlib import Path
# Permite importar desde la raíz del proyecto sin importar desde dónde ejecutes el comando
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver
from dotenv import load_dotenv
# Carga las variables del archivo .env a os.environ
load_dotenv()


try:
    import h3
except ImportError:
    sys.exit("Falta la librería h3. Instala con: pip install h3 --break-system-packages")

try:
    from neo4j import GraphDatabase
except ImportError:
    sys.exit("Falta el driver neo4j. Instala con: pip install neo4j --break-system-packages")


MAPA_CATEGORIA = {
    "Plantae": "flora",
    "Fungi": "hongos",
}
CATEGORIA_DEFAULT = "fauna"

BATCH_SIZE = 500


def cargar_poligono_geojson(path_geojson: str) -> list:
    """
    Carga el anillo exterior (lista de [lon, lat]) del primer Feature de un
    GeoJSON de tipo Polygon. Suficiente para el límite del BLP, que es un
    polígono simple (un solo anillo, ver 232-ANP_ITRF08_19162026 -> La Primavera).
    """
    with open(path_geojson, "r", encoding="utf-8") as f:
        gj = json.load(f)
    geom = gj["features"][0]["geometry"]
    if geom["type"] == "Polygon":
        return geom["coordinates"][0]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"][0][0]
    raise ValueError(f"Tipo de geometría no soportado: {geom['type']}")


def punto_en_poligono(lon: float, lat: float, ring: list) -> bool:
    """
    Ray casting en Python puro (sin shapely). Suficiente para un polígono
    simple como el límite del BLP; para geometrías más complejas (con huecos)
    usar shapely/geopandas.
    """
    n = len(ring)
    inside = False
    x1, y1 = ring[0]
    xinters = None
    for i in range(1, n + 1):
        x2, y2 = ring[i % n]
        if lat > min(y1, y2):
            if lat <= max(y1, y2):
                if lon <= max(x1, x2):
                    if y1 != y2:
                        xinters = (lat - y1) * (x2 - x1) / (y2 - y1) + x1
                    if x1 == x2 or lon <= xinters:
                        inside = not inside
        x1, y1 = x2, y2
    return inside


def categoria_desde_iconic(iconic_taxon_name: str) -> str:
    if pd.isna(iconic_taxon_name):
        return "desconocida"
    return MAPA_CATEGORIA.get(iconic_taxon_name, CATEGORIA_DEFAULT)


ZONA_NUCLEO = "nucleo"
ZONA_MAB = "zona_mab"
ZONA_FUERA = "fuera"


def clasificar_zona(lon: float, lat: float, ring_nucleo: list, ring_mab: list = None) -> str:
    """
    Clasifica un punto en una de tres zonas concéntricas:
      - "nucleo":   dentro del polígono del APFF La Primavera (CONANP/DOF).
      - "zona_mab": fuera del núcleo pero dentro de la zonificación de la
                    Reserva de la Biósfera (UNESCO MAB, 2011).
      - "fuera":    fuera de cualquier designación oficial (interfaz urbana).

    Nota sobre el nombre "zona_mab": el archivo fuente se llama
    LimiteAreaAmortiguamiento_MABIO_UTM_v1 pero su atributo interno declara
    ZON_GRAL='ZTRANSICION'. En el esquema UNESCO MAB, amortiguamiento y
    transición son anillos DISTINTOS, así que se usa un nombre neutral hasta
    confirmar con la fuente cuál es. Si se confirma, cambiar por
    "amortiguamiento" o "transicion" según corresponda.
    """
    if punto_en_poligono(lon, lat, ring_nucleo):
        return ZONA_NUCLEO
    if ring_mab is not None and punto_en_poligono(lon, lat, ring_mab):
        return ZONA_MAB
    return ZONA_FUERA


def cargar_csv(path_csv: str, ring_nucleo: list = None, ring_mab: list = None) -> pd.DataFrame:
    df = pd.read_csv(path_csv, low_memory=False)

    if "quality_grade" in df.columns:
        antes = len(df)
        df = df[df["quality_grade"] == "research"].copy()
        if len(df) < antes:
            print(f"Filtrado por quality_grade=research: {antes} -> {len(df)} filas")

    df = df.dropna(subset=["latitude", "longitude", "scientific_name", "taxon_id"])
    df["categoria"] = df["iconic_taxon_name"].apply(categoria_desde_iconic)

    if ring_nucleo is not None:
        df["zona"] = df.apply(
            lambda row: clasificar_zona(
                row["longitude"], row["latitude"], ring_nucleo, ring_mab
            ),
            axis=1,
        )
        print("\nDistribución por zona:")
        conteo = df["zona"].value_counts()
        for zona, n in conteo.items():
            print(f"  {zona:12s} {n:6d}  ({n/len(df)*100:5.1f}%)")
        if ring_mab is None:
            print("  (sin capa MAB: todo lo que no es núcleo se marcó como 'fuera')")
        print()
    else:
        df["zona"] = None
        print("AVISO: no se proporcionó polígono del BLP; zona quedará null para todas las filas.")

    return df


def calcular_celdas_h3(df: pd.DataFrame, resoluciones: Iterable[int]) -> pd.DataFrame:
    for res in resoluciones:
        col = f"h3_res{res}"
        df[col] = df.apply(
            lambda row: h3.latlng_to_cell(row["latitude"], row["longitude"], res),
            axis=1,
        )
    return df


def chunks(lista, tam):
    for i in range(0, len(lista), tam):
        yield lista[i : i + tam]


def construir_registros(df: pd.DataFrame, resoluciones: list) -> list:
    registros = []
    for _, row in df.iterrows():
        celdas = [
            {"h3_id": row[f"h3_res{res}"], "resolucion": res} for res in resoluciones
        ]
        registros.append(
            {
                "obs_id": str(row["id"]),
                "uuid": row.get("uuid"),
                "fecha": str(row["observed_on"]) if pd.notna(row.get("observed_on")) else None,
                "fuente": "iNaturalist",
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"]),
                "categoria": row["categoria"],
                "zona": row["zona"],
                "url": row.get("url"),
                "image_url": row.get("image_url") if pd.notna(row.get("image_url")) else None,
                "taxon_id": str(row["taxon_id"]),
                "nombre_cientifico": row["scientific_name"],
                "nombre_comun": row.get("common_name") if pd.notna(row.get("common_name")) else None,
                "reino_iconico": row.get("iconic_taxon_name"),
                "celdas": celdas,
            }
        )
    return registros


CYPHER_CARGA_LOTE = """
UNWIND $batch AS row

MERGE (e:Especie {nombre_cientifico: row.nombre_cientifico})
  ON CREATE SET
    e.estatus_conservacion = null,
    e.endemica = null
  SET
    e.taxon_id = row.taxon_id,
    e.nombre_comun = row.nombre_comun,
    e.reino_iconico = row.reino_iconico

MERGE (o:Observacion {id: row.obs_id})
  SET
    o.uuid = row.uuid,
    o.fecha = row.fecha,
    o.fuente = row.fuente,
    o.lat = row.lat,
    o.lon = row.lon,
    o.categoria = row.categoria,
    o.zona = row.zona,
    o.url = row.url,
    o.image_url = row.image_url

MERGE (o)-[:PERTENECE_A]->(e)

WITH o, row
UNWIND row.celdas AS celda
  MERGE (c:CeldaH3 {h3_id: celda.h3_id, resolucion: celda.resolucion})
  MERGE (o)-[:UBICADA_EN]->(c)
"""


def cargar_a_neo4j(uri, user, password, registros, resoluciones):
    driver = get_driver(uri, user, password)
    total = len(registros)
    cargados = 0

    with driver.session() as session:
        for lote in chunks(registros, BATCH_SIZE):
            session.run(CYPHER_CARGA_LOTE, batch=lote)
            cargados += len(lote)
            print(f"  {cargados}/{total} observaciones cargadas", end="\r")

    driver.close()
    print(f"\nListo. {total} observaciones y sus especies/celdas cargadas.")


def generar_adyacencias_h3(uri, user, password, resoluciones):
    """
    Crea relaciones ADYACENTE_A entre celdas H3 ya presentes en la base,
    para cada resolución, usando el anillo de vecinos k=1 de h3.
    NOTA: esto solo conecta celdas que YA existen (las que tienen al
    menos una observación). Cuando tengas el polígono límite del BLP,
    conviene regenerar la rejilla completa con h3.polygon_to_cells y
    volver a correr esta función para cubrir también celdas sin
    observaciones (necesarias para el grid continuo del mapa).
    """
    driver = get_driver(uri, user, password)

    with driver.session() as session:
        for res in resoluciones:
            result = session.run(
                "MATCH (c:CeldaH3 {resolucion: $res}) RETURN c.h3_id AS h3_id",
                res=res,
            )
            celdas_existentes = {r["h3_id"] for r in result}
            print(f"Resolución {res}: {len(celdas_existentes)} celdas con observaciones")

            pares = []
            for h3_id in celdas_existentes:
                vecinos = h3.grid_disk(h3_id, 1)
                for vecino in vecinos:
                    if vecino != h3_id and vecino in celdas_existentes:
                        pares.append({"a": h3_id, "b": vecino, "res": res})

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
            print(f"  {len(pares)} relaciones ADYACENTE_A creadas en resolución {res}")

    driver.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Ruta al CSV de Naturalista/iNaturalist")
    parser.add_argument(
        "--geojson-blp",
        default=None,
        help="Ruta al GeoJSON del límite del APFF La Primavera (núcleo). "
        "Si se omite, zona queda null para todas las observaciones.",
    )
    parser.add_argument(
        "--geojson-mab",
        default=None,
        help="Ruta al GeoJSON de la zonificación de la Reserva de la Biósfera "
        "(ej. AreaTransicion.geojson). Opcional: si se omite, todo lo que no sea "
        "núcleo se clasifica como 'fuera'.",
    )
    # Como debe quedar:
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument(
        "--resoluciones",
        type=int,
        nargs="+",
        default=[8, 9],
        help="Resoluciones H3 a calcular (default: 8 9)",
    )
    args = parser.parse_args()

    ring_nucleo = None
    if args.geojson_blp:
        print(f"Cargando polígono núcleo (APFF) desde {args.geojson_blp} ...")
        ring_nucleo = cargar_poligono_geojson(args.geojson_blp)

    ring_mab = None
    if args.geojson_mab:
        print(f"Cargando zonificación MAB desde {args.geojson_mab} ...")
        ring_mab = cargar_poligono_geojson(args.geojson_mab)

    print(f"Leyendo {args.csv} ...")
    df = cargar_csv(args.csv, ring_nucleo, ring_mab)
    print(f"{len(df)} observaciones válidas tras limpieza")

    print(f"Calculando celdas H3 en resoluciones {args.resoluciones} ...")
    df = calcular_celdas_h3(df, args.resoluciones)

    registros = construir_registros(df, args.resoluciones)

    print("Cargando a Neo4j ...")
    cargar_a_neo4j(args.uri, args.user, args.password, registros, args.resoluciones)

    print("Generando adyacencias H3 entre celdas con observaciones ...")
    generar_adyacencias_h3(args.uri, args.user, args.password, args.resoluciones)


if __name__ == "__main__":
    main()
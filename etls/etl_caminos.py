"""Carga caminos geoespaciales y calcula su cercania a celdas H3 en Neo4j.

Requisitos:
        - Python con geopandas, shapely, h3, neo4j y python-dotenv instalados.
        - Un archivo de caminos .shp o .geojson legible por GeoPandas.
        - El GeoJSON del limite del Bosque La Primavera.
        - Una instancia de Neo4j accesible y NEO4J_URI, NEO4J_USER y
            NEO4J_PASSWORD en el entorno o en un archivo .env.
        - El grid H3 de la resolucion seleccionada creado previamente.

Qué hace:
        - Normaliza los caminos a EPSG:4326 y conserva solo los que quedan
            completamente dentro del poligono del bosque.
        - Clasifica los caminos usando la columna highway cuando existe; si no,
            aplica el valor de --tipo.
        - Crea o actualiza nodos Camino y relaciones CERCANA_A desde cada celda
            H3 al camino mas proximo, guardando la distancia en metros.

Notas:
        - Los caminos que cruzan el borde o quedan fuera del poligono se descartan.
        - --tipo solo aplica cuando el archivo no contiene la columna highway.
        - Si el archivo no tiene CRS, se asume EPSG:4326.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Permite importar desde la carpeta utils/ en la raíz del proyecto
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver

# Carga variables de entorno (.env)
load_dotenv()

try:
    import geopandas as gpd
except ImportError:
    sys.exit("Falta geopandas. Instala con: pip install geopandas")

try:
    from shapely.geometry import Point, shape
except ImportError:
    sys.exit("Falta shapely. Instala con: pip install shapely")

try:
    import h3
except ImportError:
    sys.exit("Falta h3. Instala con: pip install h3")


BATCH_SIZE = 500
TIPOS_INTERNO = {"path", "track", "footway", "bridleway", "steps"}
CRS_METRICO_JALISCO = "EPSG:32613"


def chunks(lista, tam):
    for i in range(0, len(lista), tam):
        yield lista[i : i + tam]


def cargar_poligono_blp(path_geojson: str):
    with open(path_geojson, "r", encoding="utf-8") as f:
        gj = json.load(f)
    return shape(gj["features"][0]["geometry"])


def cargar_caminos(path_input: str, tipo_default: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path_input)
    if gdf.crs is None:
        print("AVISO: el archivo no trae CRS definido, asumiendo EPSG:4326.")
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    gdf = gdf.reset_index(drop=True)

    if "highway" in gdf.columns:
        gdf["tipo"] = gdf["highway"].apply(
            lambda h: "interno" if h in TIPOS_INTERNO else "vialidad"
        )
        print("Clasificación automática por columna 'highway' (OSM/Overpass).")
        print(gdf["tipo"].value_counts().to_string())
    else:
        gdf["tipo"] = tipo_default
        print(f"Sin columna 'highway'; usando --tipo={tipo_default} para todas las filas.")

    gdf["camino_id"] = [
        f"{row['tipo']}_{i}" for i, row in enumerate(gdf.to_dict(orient="records"))
    ]
    return gdf


def filtrar_cerca_del_poligono(gdf: gpd.GeoDataFrame, poligono, margen_km: float) -> gpd.GeoDataFrame:
    """Conserva los caminos que tocan el polígono ampliado con un margen (en km).
    Un camino que cruza el borde del bosque se conserva completo: son justo los
    accesos que explican la exposición de las celdas del límite."""
    antes = len(gdf)
    zona = (
        gpd.GeoSeries([poligono], crs="EPSG:4326")
        .to_crs(CRS_METRICO_JALISCO)
        .buffer(margen_km * 1000)
        .to_crs("EPSG:4326")
        .iloc[0]
    )
    cerca = gdf[gdf.geometry.intersects(zona)].reset_index(drop=True)
    print(
        f"Filtro de cobertura: {len(cerca)}/{antes} caminos dentro del polígono o a menos de "
        f"{margen_km:g} km de su borde ({antes - len(cerca)} descartados por quedar más lejos)"
    )
    return cerca


def cargar_caminos_a_neo4j(uri, user, password, gdf: gpd.GeoDataFrame):
    driver = get_driver(uri, user, password)
    registros = []
    for _, row in gdf.iterrows():
        registros.append(
            {
                "id": row["camino_id"],
                "tipo": row["tipo"],
                "geometria_wkt": row["geometry"].wkt,
            }
        )

    with driver.session() as session:
        for lote in chunks(registros, BATCH_SIZE):
            session.run(
                """
                UNWIND $batch AS row
                MERGE (c:Camino {id: row.id})
                SET c.tipo = row.tipo, c.geometria_wkt = row.geometria_wkt
                """,
                batch=lote,
            )
    driver.close()
    print(f"{len(registros)} caminos cargados como nodos Camino.")


def calcular_cercania_a_celdas(uri, user, password, gdf: gpd.GeoDataFrame, resolucion: int):
    """
    Se proyecta todo a un CRS métrico (UTM 13N) y se usa la distancia
    real al punto más cercano de la geometría completa (sjoin_narest, que internamente
    usa un índice espacial).
    """
    driver = get_driver(uri, user, password)

    with driver.session() as session:
        result = session.run(
            "MATCH (c:CeldaH3 {resolucion: $res}) RETURN c.h3_id AS h3_id",
            res=resolucion,
        )
        celdas = [r["h3_id"] for r in result]

    print(f"Calculando distancia a caminos para {len(celdas)} celdas (resolución {resolucion}) ...")

    puntos_celda = gpd.GeoDataFrame(
        {"h3_id": celdas},
        geometry=[
            Point(lon, lat)
            for lat, lon in (h3.cell_to_latlng(h3_id) for h3_id in celdas)
        ],
        crs="EPSG:4326",
    ).to_crs(CRS_METRICO_JALISCO)

    caminos_metrico = gdf[["camino_id", "geometry"]].to_crs(CRS_METRICO_JALISCO)

    cercanos = gpd.sjoin_nearest(
        puntos_celda, caminos_metrico, distance_col="distancia_m", how="left"
    )
    # Si dos caminos empatan en distancia, sjoin_nearest puede duplicar la
    # fila de la celda; nos quedamos con una sola coincidencia por celda.
    cercanos = cercanos.drop_duplicates(subset="h3_id", keep="first")

    registros = [
        {
            "h3_id": row["h3_id"],
            "resolucion": resolucion,
            "camino_id": row["camino_id"],
            "distancia_m": float(row["distancia_m"]),
        }
        for _, row in cercanos.iterrows()
    ]

    with driver.session() as session:
        for lote in chunks(registros, BATCH_SIZE):
            session.run(
                """
                UNWIND $batch AS row
                MATCH (c:CeldaH3 {h3_id: row.h3_id, resolucion: row.resolucion})
                MATCH (cam:Camino {id: row.camino_id})
                MERGE (c)-[r:CERCANA_A]->(cam)
                SET r.distancia_m = row.distancia_m
                """,
                batch=lote,
            )
    driver.close()
    print("Relaciones CERCANA_A creadas con el camino más próximo.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Ruta al .shp o .geojson de caminos")
    parser.add_argument(
        "--geojson-blp",
        required=True,
        help="GeoJSON del límite del BLP (La_Primavera.geojson)",
    )
    parser.add_argument(
        "--tipo",
        default="interno",
        choices=["interno", "vialidad"],
        help="Solo se usa si el archivo NO trae columna 'highway'",
    )
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--resolucion", type=int, default=8)
    parser.add_argument(
        "--margen-km",
        type=float,
        default=5.0,
        help="Margen alrededor del polígono en el que se conservan caminos (default 5 km; 0 = solo los que tocan el polígono)",
    )
    args = parser.parse_args()

    print(f"Cargando polígono del BLP desde {args.geojson_blp} ...")
    poligono = cargar_poligono_blp(args.geojson_blp)

    gdf = cargar_caminos(args.input, args.tipo)
    print(f"{len(gdf)} features leídas de {args.input}")

    gdf = filtrar_cerca_del_poligono(gdf, poligono, args.margen_km)
    if len(gdf) == 0:
        sys.exit("No quedó ningún camino cerca del polígono. Nada que cargar.")

    cargar_caminos_a_neo4j(args.uri, args.user, args.password, gdf)
    calcular_cercania_a_celdas(args.uri, args.user, args.password, gdf, args.resolucion)


if __name__ == "__main__":
    main()